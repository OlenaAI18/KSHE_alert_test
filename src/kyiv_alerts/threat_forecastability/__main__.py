import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/kshe-matplotlib')
os.environ.setdefault('XDG_CACHE_HOME','/tmp/kshe-cache')
import argparse,csv,json,hashlib
from pathlib import Path
from datetime import datetime,date,timedelta
from collections import Counter
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import yaml
from threadpoolctl import threadpool_limits
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from . import CATEGORIES,KYIV,eligible,build_weeks,asof_series,features,walk,metrics,difference_ci

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2,default=str,allow_nan=False)+'\n')
def csvwrite(p,rows,keys=None):
    keys=keys or (list(dict.fromkeys(k for r in rows for k in r)) if rows else ['category','status','reason'])
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys,lineterminator='\n');w.writeheader();w.writerows(rows)

def load(root):
    versions={v:pq.read_table(root/f'data/processed/classification_v1_{v[-1]}/alert_threat_features.parquet').to_pylist() for v in ['v15','v16']}
    markers={v:pq.read_table(root/f'data/processed/classification_v1_{v[-1]}/message_threat_markers.parquet').to_pylist() for v in versions}
    for v,rs in versions.items():
        flags={(r['alert_id'],c) for r in rs for c in CATEGORIES if r[c]}
        accepted={(r['alert_id'],r['category']) for r in markers[v] if r['accepted_for_aggregation']}
        assert flags==accepted,'Accepted marker/category flag reconciliation failed'
    messages=pq.read_table(root/'data/interim/telegram_messages.parquet',columns=['message_id','message_time','edited_at']).to_pylist()
    assert not any(m['edited_at'] for m in messages),'Edited message release not modeled; block rather than guess'
    times={r['message_id']:r['message_time'] for r in messages};start=min(t for t in times.values() if t);end=max(r['end_time'] for r in versions['v16'] if r['end_time'])
    weeks,strength,terms=build_weeks(versions,times,markers,start,end)
    return versions,weeks,strength,terms

def quality(versions,weeks,config):
    result=[];period=[];sets={}
    for version,rs in versions.items():
        for category in CATEGORIES:
            sets[(version,category)]={r['alert_id'] for r in rs if eligible(r) and r[category]}
        for scope in ['year','month']:
            grouped={}
            for r in rs:
                local=r['start_time'].astimezone(KYIV);key=str(local.year) if scope=='year' else local.strftime('%Y-%m');grouped.setdefault(key,[]).append(r)
            for p,rows in sorted(grouped.items()):
                e=[r for r in rows if eligible(r)];n=len(e);classified=sum(not r['unknown'] for r in e)
                for c in CATEGORIES:period.append(dict(version=version,scope=scope,period=p,category=c,official_alerts=len(rows),eligible_alerts=n,unknown_alerts=sum(r['unknown'] for r in e),classified_alerts=classified,classification_coverage=classified/n if n else None,observed_category_alerts=sum(bool(r[c]) for r in e) if n else None,partial_source_period=p in ['2023','2026','2023-08','2026-10']))
    observed=[w for w in weeks if w['observed']]
    annual=[r['classification_coverage'] for r in period if r['version']=='v16' and r['scope']=='year' and r['category']==CATEGORIES[0] and r['eligible_alerts']>=10]
    covrange=max(annual)-min(annual);weakfrac=sum(w['versions']['v16']['coverage']<.60 for w in observed)/len(observed)
    for c in CATEGORIES:
        a,b=sets[('v15',c)],sets[('v16',c)];j=len(a&b)/len(a|b) if a|b else 0
        possible=[]
        for i in range(52,len(weeks)):
            origin=datetime.combine(weeks[i]['week_start'],datetime.min.time(),KYIV)
            if weeks[i]['observed'] and features(asof_series(weeks,'v16',c,origin),i) is not None:
                if weeks[i]['week_start']<date(2026,1,5) and weeks[i]['available_at']>datetime(2026,1,5,tzinfo=KYIV):continue
                possible.append(weeks[i])
        dev=[w for w in possible if w['week_start']<date(2026,1,5)];final=[w for w in possible if w['week_start']>=date(2026,1,5)]
        devpos=sum(w['versions']['v16']['counts'][c] for w in dev);finalpos=sum(w['versions']['v16']['counts'][c] for w in final)
        dn=sum(w['versions']['v16']['counts'][c]>0 for w in dev);fn=sum(w['versions']['v16']['counts'][c]>0 for w in final)
        checks={'history':len(observed)>=config['minimum_complete_observed_weeks'],'total_positive_alerts':len(b)>=config['minimum_total_positive_alerts'],'development_positive_alerts':devpos>=config['minimum_development_positive_alerts'],'final_positive_alerts':finalpos>=config['minimum_final_positive_alerts'],'development_nonzero_weeks':dn>=config['minimum_development_nonzero_weeks'],'final_nonzero_weeks':fn>=config['minimum_final_nonzero_weeks'],'development_origins':len(dev)>=config['minimum_development_scored_origins'],'final_origins':len(final)>=config['minimum_final_scored_origins'],'version_stability':j>=config['minimum_v15_v16_alert_jaccard'],'annual_coverage_variation':covrange<=config['maximum_annual_coverage_range'],'weekly_coverage_variation':weakfrac<=config['maximum_fraction_weeks_below_60_percent_classification']}
        e=[r for r in versions['v16'] if eligible(r)]
        result.append(dict(category=c,total_labeled_alerts_v16=len(b),total_labeled_alerts_v15=len(a),complete_calendar_weeks=len(weeks),complete_observed_weeks=len(observed),weeks_no_detected_category=sum(w['versions']['v16']['counts'][c]==0 for w in observed),nonzero_observed_weeks=sum(w['versions']['v16']['counts'][c]>0 for w in observed),eligible_alerts=len(e),unknown_alerts=sum(r['unknown'] for r in e),development_origins=len(dev),final_origins=len(final),development_first_possible_scored_origin=dev[0]['week_start'] if dev else None,development_last_possible_scored_origin=dev[-1]['week_start'] if dev else None,final_first_possible_scored_origin=final[0]['week_start'] if final else None,final_last_possible_scored_origin=final[-1]['week_start'] if final else None,development_positive_alerts=devpos,final_positive_alerts=finalpos,development_nonzero_weeks=dn,final_nonzero_weeks=fn,v15_v16_jaccard=j,added_alerts=len(b-a),removed_alerts=len(a-b),annual_classification_coverage_range=covrange,fraction_weeks_coverage_below_60_percent=weakfrac,gate_pass=all(checks.values()),gate_status='PASS_FOR_EXPLORATORY_REPORTED_MARKER_TEST' if all(checks.values()) else 'INSUFFICIENT_DATA_FOR_RELIABLE_FORECAST_TEST',failed_checks=';'.join(k for k,v in checks.items() if not v),target='observed_reported_category_alert_count_not_true_threats'))
    return result,period

def summarize(rows,model,base):
    m=metrics([r['actual'] for r in rows],[r[model] for r in rows]);m.pop('WAPE');b=metrics([r['actual'] for r in rows],[r[base] for r in rows])['MAE']
    return dict(**m,skill_vs_selected_baseline=1-m['MAE']/b if b else None,positive_alerts=sum(r['actual'] for r in rows),nonzero_weeks=sum(r['actual']>0 for r in rows))

def contrast(rows,method,base,config,block=4):
    diff=[abs(r[method]-r['actual'])-abs(r[base]-r['actual']) for r in rows]
    lo,hi=difference_ci(diff,block=block,reps=config['bootstrap_repetitions'],alpha=config['familywise_alpha']/config['planned_contrasts'],dates=[r['week_start'] for r in rows])
    p_lo,p_hi=difference_ci(diff,block=block,reps=config['bootstrap_repetitions'],dates=[r['week_start'] for r in rows])
    return dict(method=method,comparator=base,n=len(rows),block_weeks=block,mean_absolute_error_difference=float(np.mean(diff)),pointwise_ci_low=p_lo,pointwise_ci_high=p_hi,simultaneous_ci_low=lo,simultaneous_ci_high=hi,planned_family_size=config['planned_contrasts'])

def evaluate(weeks,q,period,config):
    scores=[];pred=[];rob=[];decisions=[];sensitivity=[];selection=[]
    weakmonths={r['period'] for r in period if r['version']=='v16' and r['scope']=='month' and r['category']==CATEGORIES[0] and r['eligible_alerts']>=10 and r['classification_coverage']<.60}
    for gate in q:
        c=gate['category']
        if not gate['gate_pass']:
            decisions.append(dict(category=c,decision='INSUFFICIENT_DATA_FOR_RELIABLE_FORECAST_TEST',gate=gate['gate_status'],development_weeks=0,final_weeks=0,selected_baseline=None,baseline_MAE=None,candidate_MAE=None,candidate_tested=False,stable_gain=False,reason=gate['failed_checks'],scope='no forecast forced for failed gate'));continue
        base_rows=walk(weeks,c);dev=[r for r in base_rows if r['phase']=='development'];final=[r for r in base_rows if r['phase']=='final_holdout']
        losses={n:metrics([r['actual'] for r in dev],[r[n] for r in dev])['MAE'] for n in ['B0','B1','B2','B3']};selected=min(losses,key=losses.get)
        recent=min(['B1','B2','B3'],key=losses.get);dev_diff=[abs(r[recent]-r['actual'])-abs(r['B0']-r['actual']) for r in dev]
        dci=difference_ci(dev_diff,reps=config['bootstrap_repetitions'],dates=[r['week_start'] for r in dev]);gain=1-losses[recent]/losses['B0'] if losses['B0'] else 0
        enabled=gain>=config['model_development_minimum_recent_vs_mean_MAE_gain'] and dci[1]<0
        rows=walk(weeks,c,model=True) if enabled else base_rows
        dev=[r for r in rows if r['phase']=='development'];final=[r for r in rows if r['phase']=='final_holdout']
        models=['B0','B1','B2','B3','Z0']+(['M1'] if enabled else [])
        selection.append(dict(category=c,selected_baseline=selected,development_MAE=json.dumps(losses,sort_keys=True),model_enabled=enabled,development_recent_vs_mean_gain=gain,development_difference_ci_low=dci[0],development_difference_ci_high=dci[1],candidate_alpha=10 if enabled else None))
        for phase,rs in [('development',dev),('final_holdout',final)]:
            for n in models:scores.append(dict(category=c,version='v16',phase=phase,model=n,selected_baseline=selected,**summarize(rs,n,selected)))
        for r in rows:
            for n in models:pred.append({k:v for k,v in r.items() if k not in models}|dict(model=n,prediction=r[n],absolute_error=abs(r[n]-r['actual']),selected_baseline=selected))
        for label,rs in [('2024',[r for r in rows if r['week_start'].year==2024]),('2025',[r for r in rows if r['week_start'].year==2025]),('2026',final),('September2026',[r for r in final if r['week_start'].month==9]),('final_non_weak_months',[r for r in final if r['week_start'].strftime('%Y-%m') not in weakmonths]),('final_pre_policy',[r for r in final if r['week_end_exclusive']<=date(2026,9,10)]),('final_post_policy',[r for r in final if r['week_start']>=date(2026,9,10)])]:
            if not rs:continue
            for n in models:
                m=summarize(rs,n,selected);rob.append(dict(category=c,kind='period_metrics',label=label,method=n,comparator=selected,n=m['n'],block_weeks=None,MAE=m['MAE'],RMSE=m['RMSE'],bias=m['mean_bias'],skill=m['skill_vs_selected_baseline'],mean_absolute_error_difference=None,pointwise_ci_low=None,pointwise_ci_high=None,simultaneous_ci_low=None,simultaneous_ci_high=None,planned_family_size=config['planned_contrasts']))
        cs=[]
        for method,comp in [(selected,'B0')]+([('M1',selected)] if enabled else []):
            for block in config['bootstrap_blocks']:
                co=contrast(final,method,comp,config,block);cs.append(co);rob.append(dict(category=c,kind='paired_final_contrast',label='final_holdout',MAE=None,RMSE=None,bias=None,skill=None,**co))
        old=walk(weeks,c,version='v15',model=enabled);idx={r['week_start']:r for r in old};common=[r for r in final if r['week_start'] in idx];oldfinal=[idx[r['week_start']] for r in common]
        assert len(common)==len(final),'Version origins not comparable'
        for n in models:
            for v,rs in [('v16',common),('v15',oldfinal)]:sensitivity.append(dict(category=c,version=v,phase='matched_final_holdout',model=n,selected_v16_baseline=selected,parameters_retuned=False,**summarize(rs,n,selected)))
        def gain_over(rs,n,b):
            a=metrics([r['actual'] for r in rs],[r[n] for r in rs])['MAE'];den=metrics([r['actual'] for r in rs],[r[b] for r in rs])['MAE'];return 1-a/den if den else 0
        clean=[r for r in final if r['week_start'].strftime('%Y-%m') not in weakmonths]
        def qualifies(n,b):
            co=next(r for r in cs if r['method']==n and r['comparator']==b and r['block_weeks']==4)
            return gain_over(final,n,b)>=.10 and co['simultaneous_ci_high']<0 and gain_over(dev,n,b)>0 and gain_over(oldfinal,n,b)>0 and len(clean)>=20 and gain_over(clean,n,b)>0
        signal=qualifies(selected,'B0') or (enabled and qualifies('M1',selected))
        tentative=(gain_over(final,selected,'B0')>=.10) or (enabled and gain_over(final,'M1',selected)>=.10)
        decision='EVIDENCE_OF_PREDICTIVE_SIGNAL' if signal else ('INCONCLUSIVE' if tentative else 'NO_STABLE_GAIN_OVER_BASELINES')
        decisions.append(dict(category=c,decision=decision,gate=gate['gate_status'],development_weeks=len(dev),final_weeks=len(final),selected_baseline=selected,baseline_MAE=metrics([r['actual'] for r in final],[r[selected] for r in final])['MAE'],candidate_MAE=metrics([r['actual'] for r in final],[r['M1'] for r in final])['MAE'] if enabled else None,candidate_tested=enabled,stable_gain=signal,reason='simultaneous interval/version/weak-month stability gates applied; findings exploratory due retrospective taxonomy',scope='reported markers only; not physical predictability'))
    return scores,pred,rob,decisions,sensitivity,selection,weakmonths

def run(root,quality_only=False):
    out=root/'reports/threat_forecastability';data=root/'data/processed/threat_forecastability_v1';fig=out/'figures'
    for p in (out,data,fig):p.mkdir(parents=True,exist_ok=True)
    protected={str(p.relative_to(root)):digest(p) for d in ['data','src','config','tests','reports'] for p in (root/d).rglob('*') if p.is_file() and not any(part in ['threat_forecastability','threat_forecastability_v1','__pycache__'] or part.endswith('.egg-info') for part in p.parts) and p.name not in ['threat_forecastability_v1.yaml','test_threat_forecastability.py']}
    config=yaml.safe_load((root/'config/threat_forecastability_v1.yaml').read_text());versions,weeks,strength,terms=load(root);q,period=quality(versions,weeks,config)
    for row in q:
        c=row['category'];row['accepted_marker_occurrences']=sum(n for (v,category,e,u),n in strength.items() if v=='v16' and category==c);row['uncertain_marker_occurrences']=sum(n for (v,category,e,u),n in strength.items() if v=='v16' and category==c and u);row['inferred_shorthand_occurrences']=sum(n for (v,category,yr,t,i),n in terms.items() if v=='v16' and category==c and i)
    threshold_sensitivity=[]
    for row in q:
        fails=set(row['failed_checks'].split(';'))-{''}
        threshold_sensitivity.append(dict(category=row['category'],primary_gate_pass=row['gate_pass'],Jaccard=row['v15_v16_jaccard'],would_pass_at_Jaccard_065=(not (fails-{'version_stability'}) and row['v15_v16_jaccard']>=.65),forecasts_rerun=False,interpretation='data gate sensitivity only; no post-score threshold relaxation'))
    csvwrite(out/'gate_threshold_sensitivity.csv',threshold_sensitivity)
    csvwrite(out/'category_data_quality.csv',q);csvwrite(out/'category_month_year_counts.csv',period)
    csvwrite(out/'category_evidence_strength.csv',[dict(version=v,category=c,evidence_strength=e,uncertain=u,accepted_marker_occurrences=n) for (v,c,e,u),n in sorted(strength.items())])
    csvwrite(out/'terminology_reporting_by_year.csv',[dict(version=v,category=c,year=yr,subtype=t,inferred_shorthand=i,accepted_marker_occurrences=n) for (v,c,yr,t,i),n in sorted(terms.items())])
    flat=[]
    for w in weeks:
        for v,r in w['versions'].items():
            for c in CATEGORIES:flat.append(dict(version=v,category=c,week_start=w['week_start'],week_end_exclusive=w['week_end_exclusive'],available_at=w['available_at'],complete_observed_week=w['observed'],unavailable_reason=w['unavailable_reason'],observed_category_count=r['counts'][c] if w['observed'] else None,eligible_alerts=r['eligible'],unknown_alerts=r['unknown'],classified_alerts=r['classified'],classification_coverage=r['coverage'],linked_messages=r['linked_messages'],text_messages=r['text_messages'],official_alert_ids=r['alert_ids'],category_alert_ids=r['category_ids'][c]))
    pq.write_table(pa.Table.from_pylist(flat),data/'weekly_reported_category_metrics.parquet')
    csvwrite(out/'weekly_coverage_availability.csv',[{k:v for k,v in r.items() if k not in ['official_alert_ids','category_alert_ids']} for r in flat])
    exclusions=[]
    for i in range(52,len(weeks)):
        w=weeks[i];origin=datetime.combine(w['week_start'],datetime.min.time(),KYIV)
        missing=[str(past['week_start']) for past in weeks[i-8:i] if not past['observed'] or past['available_at']>origin]
        reasons=[]
        if not w['observed']:reasons.append(w['unavailable_reason'])
        if missing:reasons.append('prior8_calendar_week_labels_unavailable_at_origin')
        if w['week_start']<date(2026,1,5) and w['available_at']>datetime(2026,1,5,tzinfo=KYIV):reasons.append('development_target_not_finalized_before_holdout')
        if reasons:exclusions.append(dict(week_start=w['week_start'],origin=origin,target_available_at=w['available_at'],phase='development' if w['week_start']<date(2026,1,5) else 'final_holdout',reason=';'.join(reasons),missing_prior_calendar_weeks=';'.join(missing)))
    csvwrite(out/'availability_exclusions.csv',exclusions)
    gates=dict(status='QUALITY_GATE_COMPLETE_NO_FORECAST_SCORES',config=config,config_sha256=digest(root/'config/threat_forecastability_v1.yaml'),categories=q,first_week=weeks[0]['week_start'],last_week=weeks[-1]['week_start']);dump(out/'quality_gate_snapshot.json',gates)
    if quality_only:print(json.dumps(q,indent=2));return
    with threadpool_limits(limits=1):scores,pred,rob,decisions,sensitivity,selection,weak=evaluate(weeks,q,period,config)
    for name,rs in [('category_baselines.csv',scores),('category_walk_forward_results.csv',pred),('category_robustness.csv',rob),('category_decision_matrix.csv',decisions),('classification_version_sensitivity.csv',sensitivity),('training_only_selection.csv',selection)]:csvwrite(out/name,rs)
    if pred:pq.write_table(pa.Table.from_pylist(pred),data/'category_walk_forward_predictions.parquet')
    assert all(digest(root/k)==h for k,h in protected.items()),'Prior artifacts changed'
    summary=dict(status='COMPLETE',scope='retrospective frozen reported-category markers, not physical attacks',config=config,quality_gates=q,decisions=decisions,weak_months=sorted(weak),initial_week=weeks[0]['week_start'],initial_training_last_week=weeks[51]['week_start'],development_first_possible=weeks[52]['week_start'],scored_periods={row['category']:{key:row[key] for key in ['development_first_possible_scored_origin','development_last_possible_scored_origin','final_first_possible_scored_origin','final_last_possible_scored_origin']} for row in q if row['gate_pass']},excluded_origins=len(exclusions),last_week=weeks[-1]['week_start'],prediction_rows=len(pred),protected_files=len(protected),prior_files_unchanged=True,protected_hashes=protected,taxonomy_historical_asof_available=False,full_annotation_holdout_blind=False,operational_forecast=False,source_publication_latency_verified=False)
    dump(out/'threat_forecastability_summary.json',summary)
    plots(fig,flat,q,pred,scores);reports(out,summary,scores,rob,sensitivity,selection)
    print(json.dumps({'decisions':decisions,'protected_files':len(protected),'prediction_rows':len(pred)},indent=2))

def plotfinish(fig,name,title,ylabel):
    plt.title(title);plt.ylabel(ylabel);plt.xlabel('Historical Kyiv calendar period');plt.figtext(.5,.01,'Detected reported markers, not real threat incidence. Frozen retrospective taxonomy; coverage and availability vary.',ha='center',fontsize=8);plt.tight_layout(rect=[0,.07,1,1]);plt.savefig(fig/name,dpi=150);plt.close()

def plots(fig,flat,q,pred,scores):
    plt.figure(figsize=(12,4));rows=[r for r in flat if r['version']=='v16' and r['category']==CATEGORIES[0]];plt.plot([r['week_start'] for r in rows],[r['classification_coverage'] if r['complete_observed_week'] else np.nan for r in rows]);plt.axhline(.6,color='red',ls='--');plotfinish(fig,'weekly_classification_coverage.png','Weekly classification coverage: Aug2023–Oct2026','Classified / eligible alerts (fraction)')
    plt.figure(figsize=(12,4));x=np.arange(7)
    for j,v in enumerate(['v15','v16']):plt.bar(x+(j-.5)*.35,[r['total_labeled_alerts_'+v] for r in q],width=.35,label=v)
    plt.xticks(x,CATEGORIES,rotation=20,ha='right');plt.legend();plotfinish(fig,'category_version_counts.png','Frozen version sensitivity: Aug2023–Oct2026','Unique labeled alerts/category (overlapping categories)')
    for c in CATEGORIES:
        rows=[r for r in pred if r['category']==c]
        if not rows:continue
        models=sorted({r['model'] for r in rows});plt.figure(figsize=(12,4));start=min(r['week_start'] for r in rows);actual=[r for r in flat if r['version']=='v16' and r['category']==c and r['week_start']>=start];dates=[r['week_start'] for r in actual];plt.plot(dates,[r['observed_category_count'] if r['observed_category_count'] is not None else np.nan for r in actual],label='Observed markers (includes unscored weeks)',color='black')
        selected=rows[0]['selected_baseline']
        for n in [selected]+(['M1'] if 'M1' in models else []):
            lookup={r['week_start']:r['prediction'] for r in rows if r['model']==n};plt.plot(dates,[lookup.get(day,np.nan) for day in dates],label=n+' (gaps: unavailable prior labels)')
        plt.axvline(date(2026,1,5),ls='--',color='gray');plt.legend();plotfinish(fig,c+'_historical_predictions.png',c+': reported targets and available-origin predictions Aug2024–Oct2026','Reported-category alerts/week')

def table(rows,keys):return '| '+' | '.join(keys)+' |\n| '+' | '.join(['---']*len(keys))+' |\n'+'\n'.join('| '+' | '.join(f'{r[k]:.4f}' if isinstance(r[k],float) else str(r[k]) for k in keys)+' |' for r in rows)

def reports(out,s,scores,rob,sensitivity,selection):
    periods=list(s['scored_periods'].values())
    scored_description=(f"development {periods[0]['development_first_possible_scored_origin']}–{periods[0]['development_last_possible_scored_origin']}; final {periods[0]['final_first_possible_scored_origin']}–{periods[0]['final_last_possible_scored_origin']}" if periods else 'none: no category passed the gate')
    text=f'''# Task006.1 — Threat-specific forecastability assessment

Status COMPLETE. This task does not inherit Task006's overall decision. Every category has its own observed-data gate and, if eligible, its own chronological experiment. **Counts mean detected reported-category alert markers, not true threat incidence, attacks, weapons or launches.** Generic UAV is not verified Shahed; MiG shorthand is uncertain channel terminology; categories overlap.

## Quality gate before forecast evaluation

The fixed protocol is config/threat_forecastability_v1.yaml and ADR029. quality_gate_snapshot.json is produced before forecast scoring. gate_threshold_sensitivity.csv shows which data gates would change at a Jaccard screen of.65; no forecast is rerun after relaxing a gate. Research sufficiency thresholds are conservative screens, not scientifically validated universal cutoffs:104 observed calendar weeks;100 labeled alerts;40 development/20 final positives;20/10 nonzero scored weeks;20 origins each phase;v15/v16 Jaccard>=.70; annual overall coverage range<=.25;<=40% observed weeks below60% classification. They screen reported-marker feasibility, not physical truth. Failed categories receive no forced forecasts or fabricated zeros.

{table(s['quality_gates'],['category','total_labeled_alerts_v16','complete_observed_weeks','weeks_no_detected_category','development_origins','final_origins','development_positive_alerts','final_positive_alerts','v15_v16_jaccard','gate_status','failed_checks'])}

category_month_year_counts.csv retains month/year counts, eligible/unknown denominators and unavailable nulls. category_evidence_strength.csv reports accepted evidence levels and uncertainty; terminology_reporting_by_year.csv retains subtypes/inferred shorthand over years. Those occurrence counts are not unique-alert or weapon counts. Weekly coverage and reporting volume vary; retrospective vocabulary development, not just physical change, can alter detected counts. Gate-threshold sensitivity is documented: MiG would pass the other screens at Jaccard.65 instead of.70; no forecast is rerun using that relaxed screen. Its decision therefore reflects the predeclared stability requirement, not a mathematical impossibility of fitting a model. All seven source categories remain untouched.

## Availability, unknowns and retrospective annotation limitation

Complete Monday–Monday Kyiv weeks run from {s['initial_week']} through week {s['last_week']}. Official no-record weeks, DST-unresolved weeks and incomplete Telegram alert coverage are unavailable. Observed zero means no detected category marker among eligible recorded alerts, never a negative physical label. Unknown alert counts remain explicit and are not filled with any threat type. Each alert counted once/category; the same alert may count in multiple categories.

Finalization release is max(week end, all source alert ends, every accepted marker and supporting message time), using the later release in either version. At each origin, later-finalizing past weeks are unavailable for training/features; exact prior8 calendar-week windows required. Targets can be scored when their later labels finalize; their timestamps are recorded. No invented release for missing support. Development selection also excludes any development target finalized after2026-01-05; every supervised training row's features are reconstructed at its own historical origin, not merely at the later fitting origin. No edited timestamps were present; pipeline blocks if unmodeled edit timestamps appear. Source API/publication/revision latency is not certified.

**The taxonomy was developed retrospectively across the source history, including2026.** A holdout for numerical model selection is not an independently blind annotation holdout. Frozen labels can support conditional offline marker-target assessment, but cannot reconstruct a real historical service's as-of rules. This limitation is explicit; no claim of fully prospective or physical predictive validation follows even if conditional gains appear. Dictionary availability is not silently equated to message availability.

## Frozen forecasting design

First52 complete calendar weeks initialize training. First possible development origin {s['development_first_possible']}; final period begins2026-01-05 as Task006. Coverage and evidence-release exclusions reduce scored weeks, shared by all methods and versions. Actual scored origins: {scored_description}; {s['excluded_origins']} origins excluded (availability_exclusions.csv). In particular, final scored origins stop at Sep14 rather than Sep28: the Sep21/Sep28 origins lack finalized prior-week labels. Some high late-September weeks are therefore outside the comparable-origin evaluation; final scores are conditional on this availability-selected subset and cannot summarize all39 Task006 weeks. Failed categories' decision-matrix scored-week counts are0; data-quality tables show possible origins only. B0 historical mean; B1 previous4; B2 previous8; B3 previousweek; Z0 observed-marker zero reference. Baseline selected on development MAE only. Optional M1 is the Task006 regularized log-link Poisson AR with lag1/2/4 and4/8 means, training-only scaler and supervised-row features reconstructed at each row's own historical origin, fixed alpha10, no per-category hyperparameter search. It runs only when a recent baseline has>=10% development gain over B0 and paired pointwise95%4-week block interval strictly favors it. Otherwise candidate MAE remains unavailable, never a zero or failed-model score.

{table(selection,['category','selected_baseline','development_recent_vs_mean_gain','development_difference_ci_low','development_difference_ci_high','model_enabled'])}

## Final performance

{table([r for r in scores if r['phase']=='final_holdout'],['category','model','n','positive_alerts','nonzero_weeks','MAE','RMSE','mean_bias','skill_vs_selected_baseline'])}

MAE/RMSE/bias are reported-category alerts/week. Raw MAEs must not rank predictability across categories with different mean event counts; compare each method against its own frozen baseline with uncertainty instead. Sparse events also show Z0; WAPE/MAPE are not used. Development scores are retained but are not untouched validation. No unreported winner selection on final results.

## Uncertainty, stability and label sensitivity

Paired absolute-error differences use circular4-calendar-week blocks with unavailable-origin positions retained as missing slots (joint paired errors, no compressed timeline),4000 reps,seed20261011;8-week sensitivity. **14 planned contrasts remain in the family even when categories/models are not run.** Bonferroni-adjusted two-sided interval alpha=.05/14 controls the nominal familywise rate under the block approximation; pointwise95% intervals are also shown. Short nonstationary samples and tail Monte Carlo resolution limit nominal calibration. A wide interval spanning0 cannot establish gain. These are error-difference intervals, not predictive bands or threat probabilities.

{table([r for r in rob if r['kind']=='paired_final_contrast' and r['block_weeks']==4],['category','method','comparator','n','mean_absolute_error_difference','pointwise_ci_low','pointwise_ci_high','simultaneous_ci_low','simultaneous_ci_high'])}

{table(sensitivity,['category','version','model','n','MAE','skill_vs_selected_baseline'])}

Both versions use exactly matched final origins; selected v1.6 comparator and alpha stay fixed, no retuning. Version sensitivity is classifier uncertainty, not a new independent dataset. Baseline-vs-mean and candidate-vs-selected are different questions; a recent baseline can carry predictive information without a model improvement. Favorable signals require>=10% final gain, adjusted interval below0, same development/final direction, same direction underv1.5 and non-weak-month scoring (>=20 final weeks). Non-weak filtering is a retrospective scoring diagnostic only, never a future-informed training mask. Weak months: {', '.join(s['weak_months'])}. Calendar2024/2025/2026, September and pre/postSep10 errors are in category_robustness.csv; short post-change subset is descriptive. All real yellow/red official alerts remain included; no causal procedure explanation asserted.

## Category decisions and interpretation

{table(s['decisions'],['category','decision','development_weeks','final_weeks','selected_baseline','baseline_MAE','candidate_MAE','candidate_tested','reason'])}

Insufficient means the specified reliable test lacks support, not physical unpredictability. No stable gain refers only to tested approaches. Inconclusive includes promising but statistically/label-unstable gains. Any EVIDENCE result is exploratory conditional marker-target evidence pending independent future annotation; no individual attack/safe-window inference. Overall Task006 B neither supplies nor precludes category evidence. Sources/classes/Task006 outputs remain hash-identical ({s['protected_files']} prior files). No dashboard, chatbot or deployment started.

## Reproduction and checks

`.venv/bin/python -m kyiv_alerts.threat_forecastability --root . --quality-only` then `.venv/bin/python -m kyiv_alerts.threat_forecastability --root .`. Uses frozen v1.5/v1.6 alerts/markers and normalized Telegram timestamps. New tables are in data/processed/threat_forecastability_v1. No raw text exported in this task. Actual tests/repeat output checks are recorded in validation_results.json/reproducibility_results.json. Stop after Task006.1.
'''
    (out/'threat_forecastability_report.md').write_text(text)
    (out/'leakage_audit.md').write_text('''# Task006.1 availability and leakage audit

Exact calendar lags; late-finalizing prior labels masked at each origin. Release includes complete alert end and every accepted support message, using both versions' maximum. Training/standardization and baseline selection use development only; fixed candidate alpha10 fromTask006. Final outcomes enter later fits only after release. No random split/future centering/unknown-to-physical-zero conversion. Version comparisons use identical origins; weak-month masks score subsets only, never determine prior feature availability.

Limits: no archived as-of taxonomy. v1.6 vocabulary/context rules were reviewed retrospectively, including final2026; numerical holdout is not blind label engineering. Source publication/revision latency not certified. Frozen reported markers are an offline conditional target, not prospective threat truth. Post-change weeks too short for reliable regime inference. Paired dependence-aware intervals approximate coverage only.
''')

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--quality-only',action='store_true');a=p.parse_args();run(a.root.resolve(),a.quality_only)
if __name__=='__main__':main()
