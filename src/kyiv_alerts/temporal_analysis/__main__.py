"""Reproduce Task005. No forecasting or modification of earlier inputs."""
import argparse,calendar,csv,hashlib,json,platform,os,tempfile
from collections import Counter,defaultdict
from datetime import datetime,timedelta,timezone
from pathlib import Path
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from scipy.stats import norm
from . import KYIV,UTC,CATEGORIES,eligible,split_interval,union_minutes,bootstrap_ci,acf,holm,block_indices
SEED=20261011

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def csvwrite(p,rows):
    if not rows:return
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader()
        for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()})
def writepq(p,rows):pq.write_table(pa.Table.from_pylist(rows),p,compression='zstd')
def table(rows,keys):
    return '| '+' | '.join(keys)+' |\n| '+' | '.join(['---']*len(keys))+' |\n'+'\n'.join('| '+' | '.join(f'{r[k]:.3f}' if isinstance(r[k],float) else str(r[k]) for k in keys)+' |' for r in rows)
def stats_duration(rows):
    x=[r['duration_minutes'] for r in rows if r['duration_minutes'] is not None]
    return dict(n=len(x),median=float(np.median(x)),mean=float(np.mean(x)),p90=float(np.quantile(x,.9)),maximum=float(max(x))) if x else dict(n=0,median=None,mean=None,p90=None,maximum=None)

def run(root):
    data=root/'data/processed/temporal_analysis';report=root/'reports/temporal_analysis';fig=report/'figures'
    # Hash all pre-existing research inputs/outputs/code/config; Task005 outputs excluded.
    protected={str(p.relative_to(root)):digest(p) for folder in ('data','reports','config','src/kyiv_alerts') for p in sorted((root/folder).rglob('*')) if p.is_file() and '__pycache__' not in p.parts and '/temporal_analysis/' not in str(p)}
    for p in (data,report,fig):p.mkdir(parents=True,exist_ok=True)
    alerts=pq.read_table(root/'data/interim/alerts.parquet').to_pylist()
    versions={v:pq.read_table(root/f'data/processed/classification_{v}/alert_threat_features.parquet').to_pylist() for v in ('v1_4','v1_5','v1_6')}
    fs=versions['v1_6'];fm={f['alert_id']:f for f in fs}
    counts=Counter(f['classification_status'] for f in fs)
    baseline=dict(official=len(alerts),eligible=sum(eligible(f) for f in fs),classified=sum(eligible(f) and not f['unknown'] for f in fs),text_unknown=counts['no_marker_with_text'],no_text=counts['no_linked_text'],outside=counts['outside_telegram_coverage'],unresolved=counts['unresolved'])
    assert baseline==dict(official=2594,eligible=1803,classified=1295,text_unknown=410,no_text=98,outside=790,unresolved=1),baseline
    assert len(fm)==2594==len({a['alert_id'] for a in alerts})
    facts=[]
    for a in alerts:
        f=fm[a['alert_id']];s=a['start_time'].astimezone(KYIV);e=a['end_time'].astimezone(KYIV) if a['end_time'] else None
        assert f['start_time']==a['start_time'] and f['end_time']==a['end_time'] and f['duration_minutes']==a['duration_minutes']
        facts.append(dict(alert_id=a['alert_id'],start_time=a['start_time'],end_time=a['end_time'],start_time_original=a['start_time_original'],end_time_original=a['end_time_original'],start_local=s,end_local=e,duration_minutes=a['duration_minutes'],start_date=s.date(),year=s.year,month=s.strftime('%Y-%m'),quarter=f'{s.year}-Q{(s.month-1)//3+1}',iso_week=f'{s.isocalendar().year}-W{s.isocalendar().week:02}',valid_interval=e is not None,source_coverage_status=f['coverage_status'],eligible=eligible(f),classification_status=f['classification_status'],unknown=f['unknown'],markers=[c for c in CATEGORIES if f[c]],marker_evidence_strength=f['evidence_strengths'],experimental_classification_version='v1.6',telegram_message_count=f['telegram_message_count'],telegram_text_message_count=f['telegram_text_message_count'],**{c:f[c] for c in CATEGORIES}))
    facts.sort(key=lambda f:f['start_time']);valid=[f for f in facts if f['valid_interval']];bf=[f for f in facts if f['eligible']];classified=[f for f in bf if not f['unknown']]
    start=facts[0]['start_date'];last=max(f['end_local'].date() for f in valid)
    telegram=pq.read_table(root/'data/interim/telegram_messages.parquet',columns=['message_time']).to_pylist() if 'message_time' in pq.read_schema(root/'data/interim/telegram_messages.parquet').names else None
    if telegram is None:
        schema=pq.read_schema(root/'data/interim/telegram_messages.parquet');tcol=next(n for n in schema.names if n in ('timestamp','timestamp_utc','message_timestamp'))
        telegram=pq.read_table(root/'data/interim/telegram_messages.parquet',columns=[tcol]).to_pylist();ts=[r[tcol] for r in telegram if r[tcol]]
    else:ts=[r['message_time'] for r in telegram if r['message_time']]
    tfirst,tlast=min(ts),max(ts)
    perday=defaultdict(list);pieces=defaultdict(list)
    for f in facts:perday[f['start_date']].append(f)
    for f in valid:
        for d,a,b in split_interval(f['start_time'],f['end_time']):pieces[d].append((a,b))
    ambiguous=next(f for f in facts if not f['valid_interval']);ambday=ambiguous['start_date']
    daily=[];d=start
    while d<=last:
        rows=perday[d];br=[f for f in rows if f['eligible']];cr=[f for f in br if not f['unknown']]
        left=datetime.combine(d,datetime.min.time(),KYIV).astimezone(UTC);right=datetime.combine(d+timedelta(days=1),datetime.min.time(),KYIV).astimezone(UTC)
        observable=left>=tfirst and right<=tlast and d!=ambday
        daily.append(dict(date=d,month=d.strftime('%Y-%m'),year=d.year,iso_week=f'{d.isocalendar().year}-W{d.isocalendar().week:02}',official_alert_starts=sum(f['valid_interval'] for f in rows),all_record_starts=len(rows),total_minutes_under_alert=union_minutes(pieces[d]),unresolved_interval_day=d==ambday,calendar_day_minutes=(right-left).total_seconds()/60,source_boundary_day=d in (start,last),telegram_full_calendar_day=observable,eligible_alert_starts=len(br),supported_telegram_interpretation_count=len(cr),unknown_eligible_count=len(br)-len(cr),unknown_total_count=sum(f['unknown'] for f in rows),unknown_text_count=sum(f['classification_status']=='no_marker_with_text' for f in rows),unknown_no_text_count=sum(f['classification_status']=='no_linked_text' for f in rows),outside_coverage_count=sum(f['classification_status']=='outside_telegram_coverage' for f in rows),coverage_rate=len(cr)/len(br) if br else None,**{c:sum(bool(f[c]) for f in br) if observable or br else None for c in CATEGORIES}))
        d+=timedelta(days=1)
    months=[];catmonths=[];stability=[]
    groups=defaultdict(list)
    for r in daily:groups[r['month']].append(r)
    for month,days in groups.items():
        ff=[f for f in facts if f['month']==month];bb=[f for f in ff if f['eligible']];cc=[f for f in bb if not f['unknown']]
        complete=len(days)==calendar.monthrange(days[0]['year'],days[0]['date'].month)[1]
        msgs=[f['telegram_message_count'] or 0 for f in bb]
        row=dict(month=month,days_observed=len(days),partial_month=not complete,source_boundary_month=month in (start.strftime('%Y-%m'),last.strftime('%Y-%m')),official_alert_starts=sum(r['official_alert_starts'] for r in days),all_record_starts=len(ff),official_starts_per_observed_day=sum(r['official_alert_starts'] for r in days)/len(days),total_minutes_under_alert=sum(r['total_minutes_under_alert'] for r in days),eligible=len(bb),classified=len(cc),unknown=len(bb)-len(cc),unknown_text=sum(f['classification_status']=='no_marker_with_text' for f in bb),unknown_no_text=sum(f['classification_status']=='no_linked_text' for f in bb),outside=len([f for f in ff if f['classification_status']=='outside_telegram_coverage']),unresolved=len([f for f in ff if not f['valid_interval']]),classification_coverage=len(cc)/len(bb) if bb else None,unknown_rate=(len(bb)-len(cc))/len(bb) if bb else None,median_messages=float(np.median(msgs)) if msgs else None,mean_messages=float(np.mean(msgs)) if msgs else None,duration_median_minutes=stats_duration(ff)['median'],telegram_full_month=all(r['telegram_full_calendar_day'] for r in days) and complete)
        months.append(row);stability.append(row)
        for c in CATEGORIES:
            selected=[f for f in bb if f[c]]
            catmonths.append(dict(month=month,category=c,count=len(selected) if bb else None,eligible=len(bb),classified=len(cc),share_classified=len(selected)/len(cc) if cc else None,share_eligible=len(selected)/len(bb) if bb else None,unknown_rate=row['unknown_rate'],partial_month=not complete,telegram_full_month=row['telegram_full_month'],duration_median_minutes=stats_duration(selected)['median']))
    writepq(data/'alert_analysis_fact.parquet',facts);writepq(data/'daily_alert_metrics.parquet',daily);writepq(data/'monthly_alert_metrics.parquet',months);writepq(data/'threat_category_monthly.parquet',catmonths)
    csvwrite(report/'classification_stability.csv',stability);csvwrite(report/'monthly_official_summary.csv',months);csvwrite(report/'threat_category_monthly.csv',catmonths)
    years=[];quarters=[]
    for field,out in [('year',years),('quarter',quarters)]:
        keys=sorted({f[field] for f in facts})
        for k in keys:
            ff=[f for f in facts if f[field]==k];dd=[r for r in daily if (r['year'] if field=='year' else f"{r['year']}-Q{(r['date'].month-1)//3+1}")==k];bb=[f for f in ff if f['eligible']];cc=[f for f in bb if not f['unknown']]
            out.append(dict(period=k,days=len(dd),partial_period=dd[0]['date']==start or dd[-1]['date']==last,official_valid=sum(f['valid_interval'] for f in ff),all_records=len(ff),starts_per_day=sum(f['valid_interval'] for f in ff)/len(dd),union_minutes=sum(r['total_minutes_under_alert'] for r in dd),eligible=len(bb),classified=len(cc),unknown=len(bb)-len(cc),classification_rate=len(cc)/len(bb) if bb else None,**{'duration_'+key:value for key,value in stats_duration(ff).items()}))
    csvwrite(report/'yearly_summary.csv',years);csvwrite(report/'quarterly_summary.csv',quarters)
    weeks=[]
    for week in sorted({r['iso_week'] for r in daily}):
        dd=[r for r in daily if r['iso_week']==week];weeks.append(dict(iso_week=week,days=len(dd),partial_week=len(dd)!=7,official_starts=sum(r['official_alert_starts'] for r in dd),union_minutes=sum(r['total_minutes_under_alert'] for r in dd)))
    csvwrite(report/'weekly_summary.csv',weeks)
    catrows=[]
    for c in CATEGORIES:
        ff=[f for f in bf if f[c]]
        catrows.append(dict(category=c,count=len(ff),share_classified=len(ff)/1295,share_eligible=len(ff)/1803,**stats_duration(ff)))
    csvwrite(report/'category_summary.csv',catrows)
    overlap=[dict(category_a=a,category_b=b,unique_alerts=sum(bool(f[a]) and bool(f[b]) for f in bf)) for a in CATEGORIES for b in CATEGORIES]
    csvwrite(report/'category_overlap.csv',overlap)
    category_year=[dict(year=y['period'],category=c,count=sum(bool(f[c]) for f in bf if f['year']==y['period']),eligible=y['eligible'],classified=y['classified'],share_eligible=sum(bool(f[c]) for f in bf if f['year']==y['period'])/y['eligible'] if y['eligible'] else None) for y in years for c in CATEGORIES]
    csvwrite(report/'category_yearly.csv',category_year)
    vrows=[]
    for v,rows in versions.items():
        br=[f for f in rows if eligible(f)]
        vrows.append(dict(version=v,eligible=len(br),classified=sum(not f['unknown'] for f in br),**{c:sum(bool(f[c]) for f in br) for c in CATEGORIES}))
    csvwrite(report/'version_category_counts.csv',vrows)
    old={f['alert_id']:f for f in versions['v1_5']};transitions=Counter();changed=[]
    for f in fs:
        o=old[f['alert_id']];before=tuple(c for c in CATEGORIES if o[c]);after=tuple(c for c in CATEGORIES if f[c])
        if eligible(f) and before and after and before!=after:
            transitions[(' + '.join(before),' + '.join(after))]+=1;changed.append(dict(alert_id=f['alert_id'],month=f['start_time'].astimezone(KYIV).strftime('%Y-%m'),before=list(before),after=list(after)))
    assert len(changed)==101
    csvwrite(report/'changed_previously_classified_alerts.csv',changed);csvwrite(report/'category_transitions_101.csv',[dict(before=a,after=b,count=n) for (a,b),n in sorted(transitions.items())])
    marks=pq.read_table(root/'data/processed/classification_v1_6/message_threat_markers.parquet',columns=['alert_id','category','subtype','matched_text','accepted_for_aggregation','uncertainty_flag','inferred_shorthand','uav_evidence_type']).to_pylist()
    vocab=defaultdict(set);uncertain=defaultdict(set)
    for m in marks:
        if m['accepted_for_aggregation']:
            f=fm[m['alert_id']];y=f['start_time'].astimezone(KYIV).year;vocab[(y,m['category'],m['subtype'] or 'unspecified',(m['matched_text'] or '[context reference, no lexical expression]').casefold())].add(m['alert_id'])
            if m['uncertainty_flag']:uncertain[m['category']].add(m['alert_id'])
    evidence_rows=[dict(category=c,unique_alerts=sum(bool(f[c]) for f in bf),alerts_with_uncertain_evidence=len(uncertain[c])) for c in CATEGORIES]
    csvwrite(report/'category_evidence_uncertainty.csv',evidence_rows)
    csvwrite(report/'vocabulary_yearly.csv',[dict(year=y,category=c,subtype=s,matched_expression=e,unique_alerts=len(ids)) for (y,c,s,e),ids in sorted(vocab.items())])
    tests=[]
    x=np.array([r['official_alert_starts'] for r in daily if not r['source_boundary_day']],float)
    def add(name,pop,effect,ci,method,block=None,p=None,notes=''):
        tests.append(dict(test=name,population=pop,effect=effect,ci_low=ci[0] if ci else None,ci_high=ci[1] if ci else None,block_length=block,p_value=p,holm_p=None,method=method,notes=notes))
    for block in (7,14,28):
        fun=lambda z:np.var(z,ddof=1)/np.mean(z)
        add('daily_variance_to_mean','A',float(fun(x)),bootstrap_ci(x,fun,block), 'circular moving-block bootstrap, 1200 replicates',block,notes='Poisson reference ratio=1; pooled nonstationarity contributes. CI exploratory, not IID Poisson test.')
        for lag in (1,7,28):add(f'daily_acf_lag_{lag}','A',acf(x,lag),bootstrap_ci(x,lambda z:acf(z,lag),block) if lag<block/2 else None, 'circular moving-block bootstrap where lag < block/2; otherwise descriptive only',block,notes='Lag at/above half block: CI omitted due to block-boundary bias; raw ACF includes regime shifts, see within-month residual ACF.')
    centered=np.array([r['official_alert_starts']-np.mean([d['official_alert_starts'] for d in groups[r['month']]]) for r in daily if not r['source_boundary_day']])
    for lag in (1,7,28):add(f'within_month_residual_acf_lag_{lag}','A',acf(centered,lag),bootstrap_ci(centered,lambda z:acf(z,lag),14) if lag==1 else None,'retrospective month residual correlation; lag1 moving-block CI',notes='Removes monthly mean retrospectively, not an available forecasting feature; no calibrated p-value claimed.')
    wx=np.array([r['official_starts'] for r in weeks if not r['partial_week']],float)
    for lag in (1,4):add(f'weekly_acf_lag_{lag}','A',acf(wx,lag),bootstrap_ci(wx,lambda z:acf(z,lag),8) if lag<4 else None,'moving-block bootstrap 8 weeks; lag4 CI omitted due to block-boundary bias',8,notes='Pooled nonstationary series; no stationary AR interpretation.')
    # Broad seasonal contrasts adjusted by calendar year; joint daily bootstrap.
    dd=[r for r in daily if r['year'] in (2023,2024,2025)]
    seasonal=np.array([[r['official_alert_starts'],r['year'],(r['date'].month%12)//3] for r in dd],float)
    def season_contrast(z,season):
        diffs=[]
        for year in (2023,2024,2025):
            a=z[(z[:,1]==year)&(z[:,2]==season),0];b=z[(z[:,1]==year)&(z[:,2]!=season),0]
            if len(a) and len(b):diffs.append(np.mean(a)-np.mean(b))
        return float(np.mean(diffs)) if diffs else float('nan')
    season_rows=[]
    for season,name in enumerate(('DJF','MAM','JJA','SON')):
        fun=lambda z,s=season:season_contrast(z,s)
        val=fun(seasonal);ci=bootstrap_ci(seasonal,fun,14);se=(ci[1]-ci[0])/3.92
        add('season_'+name+'_vs_rest','A complete years 2023–2025',val,ci,'equal-year seasonal differences; joint day block bootstrap; approximate bootstrap-SE Wald p',14,float(2*norm.sf(abs(val)/se)),notes='Only 3 annual repetitions; exploratory, physical seasonality not identified; Holm family=4 seasons.')
        season_rows.append(tests[-1])
    for row,q in zip(season_rows,holm([r['p_value'] for r in season_rows])):row['holm_p']=q
    # Calendar-year changes, pre-specified adjacent-year contrasts, block bootstrap separately per year.
    for ya,yb in ((2023,2024),(2024,2025)):
        a=np.array([r['official_alert_starts'] for r in daily if r['year']==ya]);b=np.array([r['official_alert_starts'] for r in daily if r['year']==yb]);rng=np.random.default_rng(SEED)
        draws=np.array([np.mean(b[block_indices(len(b),14,rng)])-np.mean(a[block_indices(len(a),14,rng)]) for _ in range(1200)])
        add(f'year_mean_{yb}_minus_{ya}','A complete years',float(b.mean()-a.mean()),np.quantile(draws,[.025,.975]).tolist(),'separate within-year 14-day moving blocks',14,notes='Regime contrast; neither a validated change-point nor causal change. No scan-selected break p-value.')
    # Duration associations: daily cluster sums retain overlapping categories.
    # Difference in mean log(1+minutes), adjusted by alert-start month within classified alerts.
    residual={}
    for month in groups:
        cr=[f for f in classified if f['month']==month]
        if cr:
            mu=np.mean([np.log1p(f['duration_minutes']) for f in cr]);residual.update({f['alert_id']:np.log1p(f['duration_minutes'])-mu for f in cr})
    duration_effects=[]
    for c in CATEGORIES:
        z=[]
        for day in daily:
            rows=[f for f in perday[day['date']] if f['alert_id'] in residual]
            if day['date']<tfirst.astimezone(KYIV).date():continue
            yes=[residual[f['alert_id']] for f in rows if f[c]];no=[residual[f['alert_id']] for f in rows if not f[c]]
            z.append([sum(yes),len(yes),sum(no),len(no)])
        z=np.array(z,float)
        def effect(a):
            s=a.sum(axis=0);return s[0]/s[1]-s[2]/s[3] if s[1] and s[3] else float('nan')
        val=effect(z);ci=bootstrap_ci(z,effect,14);se=(ci[1]-ci[0])/(2*1.96);p=float(2*norm.sf(abs(val)/se)) if se else None
        add('duration_month_adjusted_'+c,'B classified only',val,ci,'daily-cluster 14-day block bootstrap; log1p duration residualized within month; approximate bootstrap-SE Wald p',14,p,notes='Association vs other classified alerts; overlapping labels, selection and reporting confounding; not causal. Holm family=7 categories.')
        duration_effects.append(tests[-1])
    for row,q in zip(duration_effects,holm([r['p_value'] for r in duration_effects])):row['holm_p']=q
    csvwrite(report/'statistical_tests.csv',tests)
    # Sensitivity: same-calendar-span populations; classified+unknown exhaust eligible.
    sensitivities=[]
    weak={m['month'] for m in months if m['eligible']>=10 and m['classification_coverage'] is not None and m['classification_coverage']<.60}
    for name,rows in [('all_valid_official',valid),('eligible',bf),('classified_v16',classified),('unknown_eligible_v16',[f for f in bf if f['unknown']]),('eligible_excluding_weak_months',[f for f in bf if f['month'] not in weak])]:
        sensitivities.append(dict(population=name,**stats_duration(rows),category_counts={c:sum(bool(f[c]) for f in rows) for c in CATEGORIES},unknown=sum(f['unknown'] for f in rows)))
    csvwrite(report/'sensitivity_populations.csv',sensitivities)
    # Matched complete months Aug2023 excluded; inspect version/weak-coverage differences in category slopes.
    trends=[]
    for v in ('v1_5','v1_6'):
        vm={f['alert_id']:f for f in versions[v]}
        for mode in ('all_complete_telegram_months','exclude_weak_months'):
            mm=[m for m in months if m['telegram_full_month'] and (mode!='exclude_weak_months' or m['month'] not in weak)]
            for c in CATEGORIES:
                tt=np.array([int(m['month'][:4])*12+int(m['month'][5:]) for m in mm],float);yy=np.array([sum(bool(vm[f['alert_id']][c]) for f in bf if f['month']==m['month'])/m['eligible'] for m in mm]);slope=float(np.polyfit(tt-tt.min(),yy,1)[0])
                trends.append(dict(version=v,mode=mode,category=c,months=len(mm),descriptive_share_slope_per_month=slope,interpretation='not a significance test; unknown retained in denominator'))
    csvwrite(report/'sensitivity_category_trends.csv',trends)
    # DST endpoint folds: uncertainty bounds only, never fill source end.
    from kyiv_alerts.integration.linking import possible_instants
    ends=possible_instants(ambiguous['end_time_original']);dst=dict(alert_id=ambiguous['alert_id'],start_original=ambiguous['start_time_original'],end_original=ambiguous['end_time_original'],candidate_ends=[e.isoformat() for e in ends],candidate_duration_minutes=[(e-ambiguous['start_time']).total_seconds()/60 for e in ends],primary_end_is_null=True)
    dst['incremental_union_minutes_bounds']=[union_minutes(pieces[ambday]+[(ambiguous['start_time'],e)])-union_minutes(pieces[ambday]) for e in ends]
    gaps=np.diff(np.array([f['start_time'].timestamp() for f in facts]))/3600
    summary=dict(status='COMPLETE',task='005',baseline=baseline,population_A_valid_intervals=len(valid),population_B_eligible=len(bf),official_source_first_start=facts[0]['start_local'].isoformat(),official_source_last_end=max(f['end_local'] for f in valid).isoformat(),telegram_first=tfirst.isoformat(),telegram_last=tlast.isoformat(),observed_days=len(daily),duration_minutes=stats_duration(valid),gaps_between_all_record_starts_hours=dict(median=float(np.median(gaps)),p90=float(np.quantile(gaps,.9)),maximum=float(max(gaps))),official_union_minutes=sum(r['total_minutes_under_alert'] for r in daily),individual_duration_sum=sum(f['duration_minutes'] for f in valid),yearly=years,category_summary=catrows,version_counts=vrows,previously_classified_modified=101,modified_share_of_v15_classified=101/1141,weak_month_threshold=.60,weak_months=sorted(weak),sensitivity_populations=sensitivities,category_share_trends=trends,category_evidence_uncertainty=evidence_rows,dst=dst,statistical_seed=SEED,bootstrap_replicates=1200,readiness='FURTHER_VALIDATION_NEEDED',protected_hashes=protected,software=dict(python=platform.python_version(),numpy=np.__version__,pyarrow=pa.__version__),reproduce='python -m kyiv_alerts.temporal_analysis --root .')
    assert sum(r['official_alert_starts'] for r in daily)==2593
    assert sum(r['all_record_starts'] for r in daily)==2594
    assert sum(r['eligible_alert_starts'] for r in daily)==1803
    assert sum(r['supported_telegram_interpretation_count'] for r in daily)==1295
    assert sum(r['unknown_eligible_count'] for r in daily)==508
    assert all(0<=r['total_minutes_under_alert']<=r['calendar_day_minutes'] for r in daily)
    assert abs(summary['official_union_minutes']-summary['individual_duration_sum'])<1e-6 # actual source has no resolved overlap
    assert all(digest(root/p)==h for p,h in protected.items())
    (report/'temporal_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    make_figures(fig,daily,months,valid,gaps,catmonths,vrows)
    draft_report(report,summary,tests,months,quarters,transitions,trends,uncertain)
    return summary

def make_figures(fig,daily,months,valid,gaps,catmonths,vrows):
    os.environ.setdefault('MPLCONFIGDIR',str(Path(tempfile.gettempdir())/'kshe-matplotlib'))
    os.environ.setdefault('XDG_CACHE_HOME',str(Path(tempfile.gettempdir())/'kshe-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'figure.figsize':(12,5),'font.size':10})
    def save(name,title,ylabel,note):
        plt.title(title);plt.ylabel(ylabel);plt.xlabel('Kyiv calendar; observed 2022-02-28 through 2026-10-05');plt.grid(alpha=.2);plt.figtext(.01,.01,note,fontsize=8);plt.tight_layout(rect=(0,.07,1,1));plt.savefig(fig/(name+'.png'),dpi=150);plt.close()
    xx=[datetime.strptime(m['month'],'%Y-%m') for m in months]
    plt.figure();plt.bar(xx,[m['official_alert_starts'] for m in months],width=20);save('official_monthly_counts','Official alerts: monthly count','Resolved alert starts','Partial February2022/October2026 have incomplete exposure; one unresolved interval excluded. Counts do not normalize exposure.')
    plt.figure();plt.plot(xx,[m['official_starts_per_observed_day'] for m in months],marker='o');plt.axvline(datetime(2023,8,17),color='grey',linestyle='--',label='Telegram span starts');plt.scatter([xx[0],xx[-1]],[months[0]['official_starts_per_observed_day'],months[-1]['official_starts_per_observed_day']],color='red',zorder=5,label='Partial month');plt.legend();save('official_monthly_rate','Official alerts: monthly starts per observed day','Starts/day','A=2593 resolved intervals; 1 unresolved start excluded. Boundary-day observation exposure is unknown; partial months descriptive only.')
    plt.figure();plt.plot([r['date'] for r in daily],[r['official_alert_starts'] for r in daily],alpha=.5);save('official_daily_counts','Official alert starts by day','Starts/day','Zero days are inside the observed official span only; source completeness not independently validated. One unresolved interval excluded.')
    plt.figure();plt.hist([f['duration_minutes'] for f in valid],bins=np.geomspace(.1,max(f['duration_minutes'] for f in valid)+1,50));plt.xscale('log');plt.xlabel('Duration (minutes, log scale)');plt.title('Official alert duration — 2022-02-28 to 2026-10-05');plt.ylabel('Unique resolved alerts');plt.figtext(.01,.01,'2593 resolved intervals; no Telegram filtering; ambiguous DST duration excluded.',fontsize=8);plt.tight_layout(rect=(0,.05,1,1));plt.savefig(fig/'duration_distribution.png',dpi=150);plt.close()
    plt.figure();plt.hist(gaps,bins=60);plt.title('Gaps between successive official starts — 2022-02-28 to 2026-10-04');plt.xlabel('Hours between starts');plt.ylabel('Successive start pairs');plt.figtext(.01,.01,'2594 known starts, including the unresolved-end interval; these are not safe-period estimates.',fontsize=8);plt.tight_layout(rect=(0,.05,1,1));plt.savefig(fig/'start_gap_distribution.png',dpi=150);plt.close()
    plt.figure();plt.plot(xx,[m['classification_coverage'] if m['classification_coverage'] is not None else np.nan for m in months],label='Classified / eligible');plt.plot(xx,[m['unknown_rate'] if m['unknown_rate'] is not None else np.nan for m in months],label='Unknown / eligible');plt.legend();save('classification_coverage','Experimental v1.6 interpretation yield and unknown share','Fraction of eligible alerts','No Telegram history is a gap, not zero. 2023-08 and 2026-10 incomplete coverage months; quality ≠ accuracy.')
    plt.figure()
    for c in CATEGORIES:plt.plot(xx,[next(r['share_eligible'] for r in catmonths if r['month']==m['month'] and r['category']==c) or (0 if m['eligible'] else np.nan) for m in months],label=c)
    plt.legend(ncol=2,fontsize=8);save('category_monthly_shares','Reported threat-context categories: v1.6 monthly shares','Unique category alerts / eligible alerts','Multi-label sets overlap; generic UAV ≠ confirmed Shahed; unknown is not threat absence; partial boundary months descriptive.')
    plt.figure();plt.plot(xx,[m['median_messages'] if m['median_messages'] is not None else np.nan for m in months]);save('message_volume','Linked message volume per eligible alert','Median linked messages/alert','Publication density changes observation opportunity; not physical threat intensity. Empty-message alerts included.')
    plt.figure();positions=np.arange(len(CATEGORIES))
    for j,v in enumerate(vrows):plt.bar(positions+(j-1)*.25,[v[c] for c in CATEGORIES],width=.25,label=v['version'])
    plt.xticks(positions,CATEGORIES,rotation=20);plt.legend();plt.title('Classification-version instability — eligible span 2023-08 to 2026-10');plt.ylabel('Unique alert/category detections');plt.figtext(.01,.01,'Same 1803 eligible alerts; counts overlap. Dictionary changes are not changes in physical threat activity.',fontsize=8);plt.tight_layout(rect=(0,.07,1,1));plt.savefig(fig/'version_category_counts.png',dpi=150);plt.close()

def draft_report(report,s,tests,months,quarters,transitions,trends,uncertain):
    def pick(name,block=None):return next(r for r in tests if r['test']==name and (block is None or r['block_length']==block))
    dispersion=pick('daily_variance_to_mean',14);ar=pick('daily_acf_lag_1',14);arres=pick('within_month_residual_acf_lag_1');seasons=[r for r in tests if r['test'].startswith('season_')];duration=[r for r in tests if r['test'].startswith('duration_month')]
    recent=[m for m in months if m['month']>='2026-07'];desc=s['duration_minutes']
    text=f'''# Task005 — Temporal analysis and quality diagnostics

Status: COMPLETE; retrospective exploratory diagnostics, no forecast model. v1.6 is the user-authorized primary experimental interpretation, not validated ground truth.

## Populations, time and observation

Baseline: {json.dumps(s['baseline'])}. Fact table retains all 2594 source IDs and original timestamps. Population A has 2593 resolved intervals; Population B has 1803 eligible alerts, 1295 classified and 508 unknown (410 text / 98 no text). Another 790 are outside Telegram history and one is unresolved. A never requires a threat label. Category flags denote detected context, not evidence of absence when false.

Official observed span: {s['official_source_first_start']} to {s['official_source_last_end']}; Telegram: {s['telegram_first']} to {s['telegram_last']}. Daily zeros are inserted only inside the official span; availability does not prove complete recording. The final official event predates the export cutoff; no silent zeros extend to October10. February2022 and October2026 are partial. Endpoint days are excluded from inferential daily checks. Source timestamps are never corrected here; accepted H2 and Europe/Kyiv calendars are reused. Calendar days can have 1380/1500 minutes.

## Official counts and durations

Yearly table (all records versus resolved intervals are separate; incomplete years are descriptive):

{table(s['yearly'],['period','days','partial_period','all_records','official_valid','starts_per_day','duration_median','union_minutes'])}

[Monthly counts](figures/official_monthly_counts.png). Monthly and quarterly details: [monthly_official_summary.csv](monthly_official_summary.csv), [quarterly_summary.csv](quarterly_summary.csv); weekly counts: [weekly_summary.csv](weekly_summary.csv). [Monthly rate](figures/official_monthly_rate.png), [daily counts](figures/official_daily_counts.png).

Resolved duration median={desc['median']:.2f} minutes, mean={desc['mean']:.2f}, p90={desc['p90']:.2f}, maximum={desc['maximum']:.2f}. Total calendar-split interval-union minutes={s['official_union_minutes']:.2f}. Actual resolved source intervals do not overlap: sum durations equals union. Synthetic overlap regression tests verify union behavior rather than assuming that equality generally. [Duration distribution](figures/duration_distribution.png). Inter-start gaps (including the known start of the DST case) median={s['gaps_between_all_record_starts_hours']['median']:.2f} hours, p90={s['gaps_between_all_record_starts_hours']['p90']:.2f}; [gap distribution](figures/start_gap_distribution.png). These summaries do not identify safe periods.

Recent months (October partial, never treated as a whole month):

{table(recent,['month','days_observed','partial_month','official_alert_starts','official_starts_per_observed_day','eligible','classified','unknown_rate'])}

## Dependence-aware exploratory statistics

Analytical plan fixed in ADR026 before calculation: daily counts, 14-day circular moving blocks, seed20261011,1200 replicates, 7/28-day sensitivity; weekly blocks8 weeks. Effects and pointwise 95% intervals are exploratory, not simultaneous confidence sets. Nonstationarity limits pooled resampling. No IID Poisson test, uncalibrated change-point scan or independently validated seasonal conclusion is reported. All results and assumptions: [statistical_tests.csv](statistical_tests.csv).

Pooled daily variance/mean={dispersion['effect']:.3f} (14-day block CI {dispersion['ci_low']:.3f}–{dispersion['ci_high']:.3f}), relative to equidispersed reference1. This includes changing mean regimes. Raw daily lag1 correlation={ar['effect']:.3f} (CI {ar['ci_low']:.3f}–{ar['ci_high']:.3f}); after removing monthly means, lag1={arres['effect']:.3f} (CI {arres['ci_low']:.3f}–{arres['ci_high']:.3f}). Thus the strong-looking raw persistence largely disappears after controlling changing monthly activity; it is not evidence of stable day-level predictability. Long-lag bootstrap ACF is biased by block joins, especially lags at/above block size: interpret raw long-lag values descriptively and do not use their CIs as calibrated evidence. Daily/weekly persistence and changing mean activity justify prospective aggregate validation, not individual attack prediction.

Complete-year and seasonal contrasts:

{table([r for r in tests if r['test'].startswith(('year_mean_','season_'))],['test','effect','ci_low','ci_high','p_value','holm_p','method'])}

Season contrasts use complete2023–2025, equal-year differences versus other months, not incomplete2022/2026. No seasonal contrast survives the four-comparison Holm screen; three annual cycles and regime/reporting changes cannot identify stable physical seasonality. Adjacent-year contrasts describe broad changes, not a uniquely located or causal structural break. Monthly evolution is plotted rather than tested in dozens of post-hoc pairwise tests.

## Reported categories and missingness

{table(s['category_summary'],['category','count','share_classified','share_eligible','median','p90'])}

Categories are context attribution, never confirmed launches/impacts. shahed_uav includes generic non-jet UAV; mig31 includes approved uncertain channel shorthand without verified model. Multiple categories can occur in the same alert; totals must not be added into mutually exclusive counts. [Category overlap](category_overlap.csv), [yearly category table](category_yearly.csv), [monthly category table](threat_category_monthly.csv), [monthly shares](figures/category_monthly_shares.png).

Duration associations versus other classified alerts, monthly-demeaned log(1+minutes), daily cluster/block uncertainty and Holm correction across7 categories:

{table(duration,['test','effect','ci_low','ci_high','p_value','holm_p'])}

Positive values mean longer reported-context intervals after retrospective month-centering. Categories overlap and month-centering does not adjust every confounder. Bootstrap-SE Wald p-values are approximate exploratory screening, not independent gold validation. No causal weapon-duration conclusion follows. See raw duration distributions above and population sensitivity table.

## Source and classifier stability

[Classification yield/unknown](figures/classification_coverage.png), [message volume](figures/message_volume.png), [classification_stability.csv](classification_stability.csv). Source-span eligibility is not continuous channel availability. Monthly message medians and unknown rates vary, including increased recent unknown rates; reporting vocabulary is documented in [vocabulary_yearly.csv](vocabulary_yearly.csv), counting unique alert support, not token repetition. Inference from lexical variation to physical activity is not supported.

{table(s['version_counts'],['version','eligible','classified',*CATEGORIES])}

Accepted uncertainty by category is tabulated in [category_evidence_uncertainty.csv](category_evidence_uncertainty.csv); any uncertain evidence does not imply all supporting messages are uncertain. Context-reference rows without a lexical expression are explicitly flagged in the vocabulary table and must not be counted as new lexical vocabulary.

[Version plot](figures/version_category_counts.png). Exactly101 previously-classified alerts changed combinations v1.5→v1.6 ({100*s['modified_share_of_v15_classified']:.2f}% of1141 previously classified); this excludes155 gains and1 loss. Full counted transitions: [category_transitions_101.csv](category_transitions_101.csv), IDs in [changed_previously_classified_alerts.csv](changed_previously_classified_alerts.csv). Category shifts are classifier instability, not new historical events. Known1096/2581 label/source discrepancies and unlabeled independent holdout persist.

## Sensitivity and uncertainty

[sensitivity_populations.csv](sensitivity_populations.csv) compares A, B, classified-only, unknown separately and B excluding weak months. Weak threshold fixed before analysis: classification yield below60%, at least10 eligible alerts, purely a reporting-quality screen. Weak months: {', '.join(s['weak_months'])}. [sensitivity_category_trends.csv](sensitivity_category_trends.csv) reports descriptive linear share slopes on full Telegram calendar months for both versions with/without weak months. Slopes are descriptive associations, not fitted forecasts or calibrated trend significance. Unknowns remain in eligible denominator. Version comparisons and classified-only filtering alter counts/duration distributions; conclusions about absolute physical category incidence cannot survive these observation choices. The analysis never imputes unknown labels. Zero detected categories in unknown rows does not establish zero physical threats.

Concrete sensitivity findings:

{table(s['sensitivity_populations'],['population','n','median','mean','p90','unknown'])}

The classified-only mean duration is {s['sensitivity_populations'][2]['mean']:.2f} minutes versus {s['sensitivity_populations'][1]['mean']:.2f} for all eligible and {s['sensitivity_populations'][3]['mean']:.2f} for eligible unknowns. Dropping unknowns selects longer intervals and raises the mean by {100*(s['sensitivity_populations'][2]['mean']/s['sensitivity_populations'][1]['mean']-1):.1f}%. The ballistic share slope reverses from positive under v1.5 to negative under v1.6, and the v1.5 positive slope nearly disappears after excluding weak months; these are descriptive signs, not significant physical trends. Exact slopes per month are in sensitivity_category_trends.csv. Generic-UAV/jet positive and MiG negative descriptive slope directions persist across these checks, but both classifier and publication changes remain alternative explanations. Raw official lag1 persistence becomes small after monthly centering; nominal summer association disappears under Holm correction. These disappearing findings prevent a stable forecasting claim.

DST alert {s['dst']['alert_id']}: original {s['dst']['start_original']} → {s['dst']['end_original']}. Source end remains null. Candidate folds {s['dst']['candidate_ends']}; duration bounds {s['dst']['candidate_duration_minutes']} minutes; added union bounds {s['dst']['incremental_union_minutes_bounds']} minutes. Primary A excludes its start/duration; all-record frequency sensitivity adds its known single start. B excludes it. Daily unresolved flag identifies lower-bound union time. This tiny count difference cannot justify selecting an endpoint.

## Reproducibility and validation

Run `.venv/bin/python -m kyiv_alerts.temporal_analysis --root .`; install plotting requirements from `requirements-temporal.lock.txt` after existing analysis/dev dependencies. Inputs and all earlier source/config/classifier/report hashes are recorded in temporal_summary.json and checked unchanged. Generated Parquet tables retain local-zone aware timestamps and source identifiers; rates are null when no eligible observations, categories unavailable before Telegram. Tests cover DST day lengths, overlap unions, half-open midnight, counts, unknowns, transitions and deterministic resampling. Complete-suite actual outcome is recorded in validation_results.json after execution. No forecasting or Task006 implementation.

Recommendation: **FURTHER_VALIDATION_NEEDED**; see [forecasting_readiness.md](forecasting_readiness.md).
'''
    (report/'temporal_analysis_report.md').write_text(text)
    readiness='''# Forecasting readiness — Task005

**FURTHER_VALIDATION_NEEDED**

Aggregate official counts have measurable nonstationary variation, overdispersion and serial structure (statistical_tests.csv; official_monthly_rate.png). Daily/weekly counts and union alert-minutes are reasonable candidate aggregate targets for prospective validation, after verifying official completeness and resolving endpoint exposure. No model was built.

2593 valid intervals across more than four years are adequate for descriptive diagnostics; only three fully observed calendar years and shifting regimes limit replicated seasonality. The sharp recent rate change and classification/reporting drift prevent a stationarity assumption. Retrospective autocorrelation is not out-of-sample skill.

Telegram bias is substantial:790 alerts outside history,508 eligible unknowns, one DST unresolved; v1.6 labels are experimental.101 already-classified combinations changed between v1.5 and v1.6. Recent yield weakens despite changing publication density. Generic UAV and conditional MiG aliases are not verified technical types. Validate classifier error by chronological/coverage strata and preserve unknowns before category forecasting.1096/2581 source/target discrepancies remain open.

Future aggregate validation must approve target/horizon; use strictly chronological walk-forward evaluation, training-only transforms and an untouched future period. Compare historical constant/training-window mean, last-observed aggregate, rolling mean and calendar-conditioned historical means, with Poisson and overdispersed empirical count reference intervals. Evaluate calibration and errors by regime, compare to no-change baselines, and ensure features were available at prediction time. In-alert messages are unavailable before the alert and would leak information. No operational safe-period or individual attack prediction is justified.

Misleading analyses: extrapolating partial October totals; treating pre-Telegram zeros as no threats; deleting unknowns; treating multi-label counts as weapon counts; interpreting dictionary/vocabulary growth as physical growth; IID alerts, random train/test splits, uncorrected seasonal searches and using retrospective month-centering prospectively. Authorize a separate aggregate-validation task only after these checks. Stop here.
'''
    (report/'forecasting_readiness.md').write_text(readiness)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path('.'));args=parser.parse_args();s=run(args.root.resolve());print(json.dumps({k:s[k] for k in ('status','baseline','duration_minutes','readiness')},indent=2))
