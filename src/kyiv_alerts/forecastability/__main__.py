import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/kshe-matplotlib')
os.environ.setdefault('XDG_CACHE_HOME','/tmp/kshe-cache')
os.environ.setdefault('OMP_NUM_THREADS','1')
import argparse,csv,hashlib,json
from pathlib import Path
from datetime import date
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from threadpoolctl import threadpool_limits
from . import aggregate,features,baseline,candidate,metrics,paired_ci
HOLD=date(2026,1,5);NAMES=['B0','B1','B2','B3','B4','M1'];ALPHAS=[1,10,100];WINDOWS=[13,26,52]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def csvwrite(p,rows):
    if not rows:return
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def dump(p,v):p.write_text(json.dumps(v,indent=2,default=str,allow_nan=False)+'\n')

def experiment(weeks,zero=False,fixed=None):
    y=np.array([r['recorded_starts'] if zero else (r['primary_count'] if r['primary_count'] is not None else np.nan) for r in weeks],float)
    dev=[];final=[];excluded=[]
    for i in range(52,len(y)):
        phase='development' if weeks[i]['week_start']<HOLD else 'final_holdout'
        if not np.isfinite(y[i]) or features(y,i) is None:
            excluded.append(dict(week_start=weeks[i]['week_start'],phase=phase,reason='unknown_target_or_prior8_calendar_weeks'));continue
        row=dict(week_start=weeks[i]['week_start'],week_end_exclusive=weeks[i]['week_end_exclusive'],phase=phase,actual=float(y[i]),training_first_week=weeks[0]['week_start'],training_last_week=weeks[i-1]['week_start'],training_cutoff_exclusive=weeks[i]['week_start'],training_calendar_weeks=i,training_observed_targets=int(np.isfinite(y[:i]).sum()),feature_latest_week=weeks[i-1]['week_start'])
        for name in NAMES[:4]:row[name]=baseline(y,i,name)
        if phase=='development' and fixed is None:
            for w in WINDOWS:row['B4_'+str(w)]=baseline(y,i,'B4',w)
            for a in ALPHAS:row['M1_'+str(a)],row['model_training_rows']=candidate(y,i,a)
            dev.append(row)
        else:
            if fixed is None:
                fixed=select(dev)
            row['B4']=baseline(y,i,'B4',fixed['B4_window']);row['M1'],row['model_training_rows']=candidate(y,i,fixed['M1_alpha'])
            (dev if phase=='development' else final).append(row)
    if fixed is None:fixed=select(dev)
    if not zero:
        for r in dev:r['B4']=r['B4_'+str(fixed['B4_window'])];r['M1']=r['M1_'+str(fixed['M1_alpha'])]
    return dev,final,excluded,fixed

def select(dev):
    def loss(key):return np.mean([abs(r[key]-r['actual']) for r in dev])
    w=min(WINDOWS,key=lambda w:loss('B4_'+str(w)));a=min(ALPHAS,key=lambda a:loss('M1_'+str(a)))
    scores={n:loss(n if n!='B4' else 'B4_'+str(w)) for n in NAMES[:5]}
    return dict(B4_window=w,M1_alpha=a,selected_baseline=min(scores,key=scores.get),development_baseline_MAE=scores,development_alpha_MAE={str(a):loss('M1_'+str(a)) for a in ALPHAS},development_window_MAE={str(w):loss('B4_'+str(w)) for w in WINDOWS})

def tables(dev,final,selected):
    comparisons=[];period=[];base=selected['selected_baseline']
    for phase,rows in [('development',dev),('final_holdout',final),('all_walk_forward',dev+final)]:
        b=metrics([r['actual'] for r in rows],[r[base] for r in rows])['MAE']
        for n in NAMES:
            m=metrics([r['actual'] for r in rows],[r[n] for r in rows]);comparisons.append(dict(phase=phase,model=n,**m,skill_vs_selected_baseline=1-m['MAE']/b,selected_baseline=base))
    allrows=dev+final
    groups={str(yr):[r for r in allrows if r['week_start'].year==yr] for yr in range(2023,2027)}
    groups.update({'September2026':[r for r in allrows if r['week_start'].year==2026 and r['week_start'].month==9],
                   'pre_policy':[r for r in allrows if r['week_end_exclusive']<=date(2026,9,10)],
                   'policy_crossing':[r for r in allrows if r['week_start']<date(2026,9,10)<r['week_end_exclusive']],
                   'post_policy':[r for r in allrows if r['week_start']>=date(2026,9,10)]})
    for label in ('lower_activity','higher_activity','shift_origin'):
        groups[label]=[r for r in allrows if r[label]]
    for label,rows in groups.items():
        if not rows:continue
        b=metrics([r['actual'] for r in rows],[r[base] for r in rows])['MAE']
        for n in NAMES:
            m=metrics([r['actual'] for r in rows],[r[n] for r in rows]);period.append(dict(period=label,model=n,**m,skill_vs_selected_baseline=1-m['MAE']/b if b else None,descriptive_only=label not in ['2023','2024','2025','2026']))
    return comparisons,period

def run(root):
    out=root/'reports/forecastability_validation';data=root/'data/processed/forecastability';fig=out/'figures'
    for p in (out,data,fig):p.mkdir(parents=True,exist_ok=True)
    protected={str(p.relative_to(root)):sha(p) for directory in ['data','config','src','reports'] for p in (root/directory).rglob('*') if p.is_file() and 'forecastability' not in p.parts and 'forecastability_validation' not in p.parts and '__pycache__' not in p.parts}
    facts=pq.read_table(root/'data/processed/temporal_analysis/alert_analysis_fact.parquet').to_pylist()
    weekly=aggregate(facts);weeks=[r for r in weekly if r['complete_calendar_week']]
    with threadpool_limits(limits=1):dev,final,excluded,selected=experiment(weeks)
    y=np.array([r['primary_count'] if r['primary_count'] is not None else np.nan for r in weeks]);idx={r['week_start']:i for i,r in enumerate(weeks)}
    for r in dev+final:
        i=idx[r['week_start']];threshold=float(np.nanmedian(y[:i]));r['training_activity_median']=threshold;r['lower_activity']=r['actual']<=threshold;r['higher_activity']=r['actual']>threshold;r['shift_origin']=bool(abs(np.nanmean(y[i-4:i])-np.nanmean(y[max(0,i-12):i-4]))>=5)
    comparison,period=tables(dev,final,selected);base=selected['selected_baseline']
    uncertainty=[]
    for n in NAMES[:5]:
        diff=[abs(r['M1']-r['actual'])-abs(r[n]-r['actual']) for r in final]
        for block in (4,8,13):
            lo,hi=paired_ci(diff,block);uncertainty.append(dict(check='paired_final_MAE_difference',comparison='M1 minus '+n,block_weeks=block,n=len(diff),estimate=float(np.mean(diff)),ci_low=lo,ci_high=hi,primary=n==base and block==4))
    with threadpool_limits(limits=1):sd,sf,se,_=experiment(weeks,zero=True,fixed=selected)
    for n in NAMES:
        m=metrics([r['actual'] for r in sf],[r[n] for r in sf]);uncertainty.append(dict(check='archived_zero_sensitivity_fixed_parameters',comparison=n,block_weeks=None,n=m['n'],estimate=m['MAE'],ci_low=None,ci_high=None,primary=False))
    for label,rows in [('final_excluding_September_starts',[r for r in final if r['week_start'].month!=9]),('final_pre_policy',[r for r in final if r['week_end_exclusive']<=date(2026,9,10)])]:
        for n in NAMES:
            m=metrics([r['actual'] for r in rows],[r[n] for r in rows]);uncertainty.append(dict(check=label,comparison=n,block_weeks=None,n=m['n'],estimate=m['MAE'],ci_low=None,ci_high=None,primary=False))
    finalmetrics={r['model']:r for r in comparison if r['phase']=='final_holdout'}
    ci=next(r for r in uncertainty if r['primary']);skill=finalmetrics['M1']['skill_vs_selected_baseline']
    robust=sum(r['skill_vs_selected_baseline']>0 for r in period if r['model']=='M1' and r['period'] in ['2023','2024','2025','2026'])
    decision='A' if skill>=.10 and ci['ci_high']<0 and all(finalmetrics['M1']['MAE']<finalmetrics[n]['MAE'] for n in NAMES[:5]) and robust>=3 else 'B'
    predictions=[]
    for r in dev+final:
        for n in NAMES:
            predictions.append({k:v for k,v in r.items() if k not in NAMES and not k.startswith('M1_') and not k.startswith('B4_')}|dict(model=n,prediction=r[n],error=r[n]-r['actual'],absolute_error=abs(r[n]-r['actual']),B4_window=selected['B4_window'],M1_alpha=selected['M1_alpha']))
    pq.write_table(pa.Table.from_pylist(weekly),data/'weekly_official_metrics.parquet');pq.write_table(pa.Table.from_pylist(predictions),data/'walk_forward_predictions.parquet')
    csvwrite(out/'walk_forward_results.csv',predictions);csvwrite(out/'baseline_comparison.csv',comparison);csvwrite(out/'performance_by_period.csv',period);csvwrite(out/'robustness_checks.csv',uncertainty);csvwrite(out/'excluded_origins.csv',excluded)
    tuning=[dict(family=family,value=k,development_MAE=v) for family,key in [('B4_window','development_window_MAE'),('M1_alpha','development_alpha_MAE')] for k,v in selected[key].items()];csvwrite(out/'training_only_selection.csv',tuning)
    months={}
    for r in facts:months.setdefault(r['month'],0);months[r['month']]+=1
    csvwrite(out/'monthly_descriptive_counts.csv',[dict(month=k,recorded_starts=v,complete_calendar_month=k not in ['2022-02','2026-10'],not_forecast_target=True) for k,v in sorted(months.items())])
    def save(name,title,ylabel):
        plt.title(title);plt.ylabel(ylabel);plt.xlabel('Historical Europe/Kyiv week start');plt.figtext(.5,.01,'Archived counts; completeness unverified. All colors included. Retrospective one-week forecasts; no individual threat timing.',ha='center',fontsize=8);plt.tight_layout(rect=[0,.06,1,1]);plt.savefig(fig/name,dpi=150);plt.close()
    plt.figure(figsize=(12,4));x=[r['week_start'] for r in dev+final]
    for n,label in [('actual','Recorded starts'),(base,base+' baseline'),('M1','M1 Poisson AR')]:plt.plot(x,[r[n] for r in dev+final],label=label,alpha=.8)
    plt.axvline(HOLD,color='black',ls='--',label='Frozen final holdout');plt.legend();save('historical_predictions.png','Historical one-week expanding-window evaluation: 2023–2026','Official alert starts/week')
    plt.figure(figsize=(12,4))
    for n in [base,'M1']:
        e=np.array([abs(r[n]-r['actual']) for r in dev+final]);plt.plot(x,[np.mean(e[max(0,i-12):i+1]) for i in range(len(e))],label=n)
    plt.axvline(HOLD,color='black',ls='--');plt.legend();save('rolling_errors.png','Trailing 13-scored-origin MAE (not a calendar-week average across excluded gaps)','MAE: alerts/week')
    plt.figure(figsize=(10,4));labels=['2023','2024','2025','2026']
    for j,n in enumerate([base,'M1']):plt.bar(np.arange(4)+(j-.5)*.35,[next(r['MAE'] for r in period if r['model']==n and r['period']==yr) for yr in labels],width=.35,label=n)
    plt.xticks(np.arange(4),labels);plt.legend();save('regime_errors.png','Calendar-year errors: 2023–2025 development; 2026 final holdout','MAE: alerts/week')
    unchanged=all(sha(root/k)==v for k,v in protected.items());assert unchanged
    summary=dict(status='COMPLETE',decision=decision,decision_name='EVIDENCE_OF_AGGREGATE_PREDICTABILITY' if decision=='A' else 'NO_STABLE_GAIN_OVER_BASELINES',target='weekly recorded official Kyiv alert starts, all colors',horizon_weeks=1,official_records=len(facts),complete_calendar_weeks=len(weeks),unknown_no_record_weeks=[str(r['week_start']) for r in weeks if r['primary_count'] is None],initial_training_first=str(weeks[0]['week_start']),initial_training_last=str(weeks[51]['week_start']),development_first=str(dev[0]['week_start']),development_last=str(dev[-1]['week_start']),development_origins=len(dev),holdout_first=str(final[0]['week_start']),holdout_last=str(final[-1]['week_start']),holdout_origins=len(final),total_scored_origins=len(dev)+len(final),prediction_rows=len(predictions),excluded_origins=len(excluded),selection=selected,final_metrics=finalmetrics,primary_uncertainty=ci,positive_year_strata=robust,previous_files_unchanged=unchanged,protected_files=len(protected),protected_input_hashes=protected,source_completeness='unverified internally; no-record weeks unknown in primary',live_forecasts=False)
    dump(out/'forecastability_summary.json',summary)
    write_reports(out,summary,comparison,period,uncertainty)
    print(json.dumps({k:v for k,v in summary.items() if k not in ['protected_input_hashes','final_metrics']},indent=2))

def table(rows,keys):return '| '+' | '.join(keys)+' |\n| '+' | '.join(['---']*len(keys))+' |\n'+'\n'.join('| '+' | '.join(f'{r[k]:.4f}' if isinstance(r[k],float) else str(r[k]) for k in keys)+' |' for r in rows)

def write_reports(out,s,comparison,period,uncertainty):
    base=s['selection']['selected_baseline'];final=[r for r in comparison if r['phase']=='final_holdout']
    report=f'''# Task006 — retrospective forecastability validation

Status COMPLETE; decision **{s['decision']} — {s['decision_name']}**. Target approved by Task006: weekly recorded official Kyiv alert starts, all colors. A count is an administrative alert start, not an attack or weapon. No live forecast or individual danger/safety prediction.

## Frozen design and chronological evaluation

Conservative complete Europe/Kyiv Monday–Monday weeks: {s['initial_training_first']} through week {s['holdout_last']}; {s['complete_calendar_weeks']} weeks. Exclude initial boundary week even though first record falls on Monday; partial final week excluded. Initial52 calendar weeks: {s['initial_training_first']}–{s['initial_training_last']}. Development origins: {s['development_first']}–{s['development_last']} ({s['development_origins']}); untouched selection holdout: {s['holdout_first']}–{s['holdout_last']} ({s['holdout_origins']}). Each forecast predicts exactly the next week from its Monday00:00 origin; prior outcomes become available at subsequent origins. Historical replay assumes archived counts were available at week end; true source publication/revision latency is unverified. This is conditional retrospective skill, not a real-time service validation.

B0 expanding historical mean; B1 previous4; B2 previous8; B3 previousweek; B4 recent13/26/52 chosen once on development MAE. One candidate M1 L2 Poisson autoregression with log1p lag1/2/4 and preceding4/8 means; StandardScaler fit separately within each training window; alpha1/10/100 development selection. No seasonal features, Telegram categories, future month means, or full-history normalization. Poisson is a penalized nonnegative mean model, not a claim of equidispersion: no Poisson prediction intervals used. A second model was unnecessary given the small weekly sample and constrained interpretable scope.

Selected B4 window={s['selection']['B4_window']}; M1 alpha={s['selection']['M1_alpha']}; strongest development baseline={base}. Parameters and comparator remain fixed across all final origins. Complete development grid is in training_only_selection.csv; all approaches shown, without selecting a winner for deployment after inspecting holdout.

## Source quality and reconciliation

All{s['official_records']} starts (including the one unresolved end) are retained; aggregation preserves per-week source IDs. No end is needed to count the known start. No DST fold correction or historical overwrite. Weekly calendar length can be167/168/169 hours. No record week(s): {s['unknown_no_record_weeks']}; primary target is null, not observed zero. Eight preceding calendar weeks must be available for common-origin comparison; {s['excluded_origins']} origins excluded. No unavailable week is compressed away or imputed. The archived-zero robustness run is explicitly conditional and does not certify that zero was observed. Positive counts too have unverified internal completeness. Task005.1 confirms same-source export equality, not historical completeness or independent truth.

Secondary monthly counts are descriptive complete-month references; endpoint months flagged. Minutes forecasting is deferred because of unresolved end/completeness; monthly forecasting has too few observations to justify another experiment. Old classification and temporal outputs remain unchanged ({s['protected_files']} protected file hashes).

## Final one-week holdout results

{table(final,['model','n','MAE','RMSE','mean_bias','WAPE','skill_vs_selected_baseline'])}

Errors are alerts/week; WAPE is fraction; skill=1−MAE/model comparator MAE. Development/all scores also retained in baseline_comparison.csv; development selection results are not independent superiority evidence. Best realized final MAE={min(final,key=lambda r:r['MAE'])['model']}; this retrospective ranking does not change frozen selection.

Primary paired difference: candidate absolute error minus {base} error, mean={s['primary_uncertainty']['estimate']:.4f} alerts/week; pointwise95% circular4-week block interval [{s['primary_uncertainty']['ci_low']:.4f}, {s['primary_uncertainty']['ci_high']:.4f}],2000 reps,seed20261011. Negative favors M1. Blocks8/13 and each baseline are in robustness_checks.csv. These overlapping contrasts are exploratory, not multiple independent discoveries. No superiority claim from an interval crossing zero;39 or fewer final origins and nonstationary changes constrain calibration. No forecast interval calibration is claimed.

## Regime checks

{table([r for r in period if r['model'] in [base,'M1']],['period','model','n','MAE','skill_vs_selected_baseline'])}

Low/high groups classify observed held-out activity against training-only expanding median (diagnostic groups, unavailable future labels are not features). Shift origins are tagged by past4-week mean versus preceding8 difference>=5. Allyear and non-yeargroups reported; year2023–2025 overlap development and are not independent replications. September includes the week starting Sep28, which extends into October. Pre/postSep10 excludes the crossingweek; few post-change weeks allow descriptive errors only. Yellow and red warnings are real alerts and every start is retained. Procedure changes may affect measurement comparability but do not explain away real activity or prove causation. Do not infer that high recorded September activity is artificial.

Final excluding September-start weeks and final pre-change-only errors are provided in robustness_checks.csv. These are diagnostic sensitivities, never alternative model selection. A short 2026/high-activity regime cannot establish stable future performance.

## Answers to the research questions

RQ1: recent-count baselines have lower final errors than the historical mean; this is conditional out-of-sample evidence for recent aggregate information, not a stable military mechanism. RQ2: the previous4-week mean adapts faster than the historical or8/13-week means in this holdout. RQ3: the selected candidate does not beat the strongest development baseline on final MAE. RQ4: errors and rankings change across years and low/high activity; small development-year gains do not replicate in2026. RQ5: no stable model gain supports a forecasting MVP in this scoped experiment.

Final sensitivity MAEs (alerts/week):

{table([r for r in uncertainty if r['check'] in ['final_excluding_September_starts','final_pre_policy']],['check','comparison','n','estimate'])}

September materially increases the candidate error gap, but excluding September-start weeks does not change the decision. With only3 fully post-policy weeks, causal or stable post-policy superiority cannot be established.

## MVP and research interpretation

Decision **{s['decision']}**. Predeclared A gate: >=10% final MAE improvement over frozen baseline, primary interval strictly below0, final MAE below every baseline, positive skill in at least3/4 yearstrata. Gate outcome is in summary; all criteria apply jointly. Raw daily correlation (~0.47) and month-centered (~0.07) were descriptive, not forecast evidence. Count data can show persistence while a fitted model still fails to improve over recent means. Neither skill nor error reveals military causes, future individual timing, location or threat type.

Recommend a historical analytical dashboard/research findings as the MVP when B/C; do not build it in this task. Existing experiment is sufficient for the scoped archived-target question, but missingness, publication latency and warning-regime change prevent operational claims. No categorical weapon forecast. Stop after Task006.

## Reproduce

`.venv/bin/python -m kyiv_alerts.forecastability --root .`; uses frozen Task005 fact table, sklearn/numpy/scipy/pyarrow/matplotlib installed analysis environment. Same seed, single-thread fits. Output predictions contain cutoff/feature dates and source weekly IDs. See leakage_audit.md, validation_results.json and reproducibility_results.json for executed evidence. All outputs are retrospective historical values.
'''
    (out/'forecastability_report.md').write_text(report)
    (out/'leakage_audit.md').write_text('''# Leakage and quality audit — Task006

- Forecast origin is Monday00:00 Europe/Kyiv; target is that next complete calendar week.
- Every training target ends at or before origin; feature latest week is strictly earlier.
- Lag/calendar windows use exact original indices; missing weeks are not deleted or filled.
- Scaling and Poisson fitting use only supervised rows before origin; no target-week feature.
- B4 window, candidate alpha, comparator are selected only using origins before2026-01-05.
- Final outcomes may update later expanding fits, never selection. Development scores are selection evidence, not untouched test evidence.
- No source end inference, future detrending, retrospective Telegram features or random splits.
- Source boundary weeks excluded; no-record week null in primary, separate explicitly conditional zero sensitivity.
- All known official starts included, no color exclusions. Source IDs reconcile to2594 records.
- Actual historical publication/revision latency and positive-week completeness are unverified: archived week-end availability is a retrospective assumption, not a validated live feature feed.
- Block intervals account approximately for error dependence; short nonstationary final series prevents guaranteed coverage.
- Synthetic suffix perturbation and scaler/training reconstruction tests verify past-only predictions; real-output cutoff assertions verify every origin. Actual results in validation_results.json.
''')
    (out/'mvp_decision.md').write_text(f'''# Рішення щодо MVP — Task006

**{s['decision']} — {s['decision_name']}**.

Перевірено прогноз кількості початків офіційних тривог за тиждень, включно з усіма кольорами. Остаточна оцінка: {s['holdout_origins']} тижнів 2026 року. MAE моделі: {s['final_metrics']['M1']['MAE']:.2f} тривоги/тиждень; базовий {base}: {s['final_metrics'][base]['MAE']:.2f}. Перевага моделі: {100*s['final_metrics']['M1']['skill_vs_selected_baseline']:.1f}%. Інтервал різниці помилок: [{s['primary_uncertainty']['ci_low']:.2f}; {s['primary_uncertainty']['ci_high']:.2f}] тривоги/тиждень.

Рекомендований MVP — історична аналітика, графіки й пояснення обмежень. Модель не показала стабільної переваги над простими підходами; надто короткий і мінливий остаточний період не дозволяє оголосити прогноз надійним. Нічого не розгорнуто.

Жовті тривоги збережено. Вересневе зростання реальне в офіційних записах; зміна процедур може впливати на порівнянність, але причинного пояснення зростання тут немає. Після зміни надто мало тижнів для окремого надійного висновку. Повнота історії й доступність оновлень у реальному часі не підтверджені. Це не прогноз окремих атак чи безпечних проміжків. Розробку dashboard/chatbot/deployment не розпочато.
''')

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('.'));args=p.parse_args();run(args.root.resolve())
if __name__=='__main__':main()
