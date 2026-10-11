import argparse,csv,hashlib,json,os,platform,tempfile
from collections import Counter,defaultdict
from datetime import datetime,timedelta
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq
from kyiv_alerts.temporal_analysis import KYIV,UTC,CATEGORIES,block_indices
from . import load_external,assign_intervals,group_state,distribution

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def csvwrite(path,rows,fields=None):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields or list(rows[0]),lineterminator='\n');w.writeheader()
        for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()})
def table(rows,keys):
    return '| '+' | '.join(keys)+' |\n| '+' | '.join(['---']*len(keys))+' |\n'+'\n'.join('| '+' | '.join(f'{r[k]:.3f}' if isinstance(r[k],float) else str(r[k]) for k in keys)+' |' for r in rows)

def reconcile(facts,manifest,root,report):
    histories=[];summary=[];periods=[];sensitivity=[];overlaps=[]
    for source,metadata in manifest.items():
        external=load_external(root/metadata['local_subset']);valid=[r for r in facts if r['end_time'] is not None]
        first=max(min(r['start_time'] for r in valid),external[0]['start_time']).astimezone(KYIV).date()+timedelta(days=1)
        final=min(max(r['end_time'] for r in valid),max(r['end_time'] for r in external)).astimezone(KYIV).date()
        lower=datetime.combine(first,datetime.min.time(),KYIV).astimezone(UTC);upper=datetime.combine(final,datetime.min.time(),KYIV).astimezone(UTC)
        local=[r for r in valid if lower<=r['start_time']<upper];ext=[r for r in external if lower<=r['start_time']<upper]
        pairs,edges=assign_intervals(local,ext);im={i:j for i,j in pairs};jm={j:i for i,j in pairs};cand_i=Counter(i for i,j in edges);cand_j=Counter(j for i,j in edges)
        for tol in (60,300,600):
            pp,ee=assign_intervals(local,ext,tol);sensitivity.append(dict(source=source,tolerance_minutes=tol/60,official_resolved=len(local),external_unique=len(ext),matched=len(pp),official_unmatched=len(local)-len(pp),external_unmatched=len(ext)-len(pp)))
        deltas=[];ends=[]
        def base(a,b,status):
            start_delta=(b['start_time']-a['start_time']).total_seconds()/60 if a and b else None
            end_delta=(b['end_time']-a['end_time']).total_seconds()/60 if a and b else None
            return dict(source=source,source_commit=metadata['commit'],official_alert_id=a['alert_id'] if a else None,external_record_id=b['external_record_id'] if b else None,external_source_csv_lines=b['source_csv_lines'] if b else None,status=status,official_start=a['start_time'].isoformat() if a else None,official_end=a['end_time'].isoformat() if a else None,external_start=b['start_time'].isoformat() if b else None,external_end=b['end_time'].isoformat() if b else None,external_estimated_end=b['naive'] if b else None,external_end_provenance=('archive_no_row_flag_parser_can_impute' if source=='official_archive' else 'estimated_30min' if b and b['naive'] else 'not_flagged_estimated') if b else None,start_delta_minutes=start_delta,end_delta_minutes=end_delta,end_delta_usable=bool(a and b and not b['naive']),official_candidate_count=cand_i.get(local.index(a),0) if a else None,external_candidate_count=cand_j.get(ext.index(b),0) if b else None)
        for i,a in enumerate(local):
            b=ext[im[i]] if i in im else None;r=base(a,b,'matched' if b else 'official_unmatched');histories.append(r)
            if b:
                deltas.append(r['start_delta_minutes'])
                if not b['naive']:ends.append(r['end_delta_minutes'])
        for j,b in enumerate(ext):
            if j not in jm:histories.append(base(None,b,'external_unmatched'))
        # All interval overlaps, independent of start tolerance, expose split/merged records.
        es=np.array([b['start_time'].timestamp() for b in ext]);ee=np.array([b['end_time'].timestamp() for b in ext])
        all_edges=[(i,int(j)) for i,a in enumerate(local) for j in np.flatnonzero((es<a['end_time'].timestamp()) & (ee>a['start_time'].timestamp()))]
        aa=Counter(i for i,j in all_edges);bb=Counter(j for i,j in all_edges)
        for i,j in all_edges:
            if aa[i]>1 or bb[j]>1:
                a,b=local[i],ext[j];overlaps.append(dict(source=source,official_alert_id=a['alert_id'],external_record_id=b['external_record_id'],overlapping_external_for_official=aa[i],overlapping_official_for_external=bb[j],start_delta_minutes=(b['start_time']-a['start_time']).total_seconds()/60,external_estimated_end=b['naive'],assessment='possible split/merge/timing disagreement; not automatically reconciled'))
        row=dict(source=source,common_start=first.isoformat(),common_end_exclusive=final.isoformat(),external_raw_kyiv_rows=metadata['kyiv_rows'],external_unique_kyiv_intervals=len(external),duplicate_rows_removed=metadata['kyiv_rows']-len(external),external_estimated_end_count=sum(r['naive'] for r in external),official_resolved_common=len(local),external_unique_common=len(ext),matched=len(pairs),official_unmatched=len(local)-len(pairs),external_unmatched=len(ext)-len(pairs),official_matching_rate=len(pairs)/len(local),external_matching_rate=len(pairs)/len(ext),start_delta_signed_median=float(np.median(deltas)),start_delta_abs_median=float(np.median(np.abs(deltas))),nonflagged_end_comparisons=len(ends),end_delta_signed_median=float(np.median(ends)),end_delta_abs_median=float(np.median(np.abs(ends))),end_abs_within_5min_rate=float(np.mean(np.abs(ends)<=5)),official_one_to_many_overlap=sum(n>1 for n in aa.values()),external_one_to_many_overlap=sum(n>1 for n in bb.values()),source_identity=metadata['source_relative_path'])
        summary.append(row)
        for scope in ('month','year'):
            keys=sorted({r['start_time'].astimezone(KYIV).strftime('%Y-%m' if scope=='month' else '%Y') for r in local+ext})
            for key in keys:
                choose=lambda r:r['start_time'].astimezone(KYIV).strftime('%Y-%m' if scope=='month' else '%Y')==key
                oo=[r for r in local if choose(r)];ee=[r for r in ext if choose(r)]
                periods.append(dict(source=source,scope=scope,period=key,official_resolved=len(oo),external_unique=len(ee),external_minus_official=len(ee)-len(oo),matched_on_official_start=sum(choose(local[i]) for i,j in pairs),boundary_period=key in (first.strftime('%Y-%m' if scope=='month' else '%Y'),(final-timedelta(days=1)).strftime('%Y-%m' if scope=='month' else '%Y'))))
    csvwrite(report/'historical_reconciliation.csv',histories);csvwrite(report/'historical_reconciliation_summary.csv',summary);csvwrite(report/'historical_count_periods.csv',periods);csvwrite(report/'historical_match_sensitivity.csv',sensitivity);csvwrite(report/'overlap_disagreements.csv',overlaps)
    return summary,periods

def category_analysis(facts,report):
    eligible=[f for f in facts if f['eligible']];rows=[]
    def emit(scope,period,ff):
        for c in ('ALL',*CATEGORIES):
            for state in ('single_category','multiple_categories','unknown'):
                if c!='ALL' and state=='unknown':continue
                selected=[f for f in ff if group_state(f)==state and (c=='ALL' or c in f['markers'])]
                rows.append(dict(scope=scope,period=period,category=c,group=state,**distribution(selected)))
    emit('overall','all',eligible)
    for field in ('year','month'):
        for key in sorted({f[field] for f in eligible}):emit(field,str(key),[f for f in eligible if f[field]==key])
    csvwrite(report/'single_multi_category_duration.csv',rows)
    # Empirical yield bins and joint strata, keeping no-text and genuine zero-message records.
    duration_edges=[0,15,30,60,120,float('inf')];message_edges=[0,1,4,10,30,float('inf')]
    dd=[f['start_date'] for f in eligible];first=min(dd);last=max(dd);days=[first+timedelta(days=i) for i in range((last-first).days+1)];byday=defaultdict(list)
    for f in eligible:byday[f['start_date']].append(f)
    records=[]
    def make(axis,label,select):
        ff=[f for f in eligible if select(f)];counts=np.array([[sum(select(f) and bool(f['markers']) for f in byday[d]),sum(select(f) for f in byday[d])] for d in days],float)
        n=len(ff);rng=np.random.default_rng(20261011);draws=[]
        for _ in range(800):
            z=counts[block_indices(len(days),14,rng)].sum(axis=0)
            if z[1]:draws.append(z[0]/z[1])
        ci=np.quantile(draws,[.025,.975]) if draws else [None,None]
        records.append(dict(axis=axis,bin=label,eligible=n,classified=sum(bool(f['markers']) for f in ff),unknown=sum(not f['markers'] for f in ff),classification_yield=sum(bool(f['markers']) for f in ff)/n if n else None,ci_low=float(ci[0]) if ci[0] is not None else None,ci_high=float(ci[1]) if ci[1] is not None else None,**{'duration_'+k:v for k,v in distribution(ff).items() if k!='n'},note='retrospective observed yield, not prediction or accuracy; 14-day joint blocks/800 reps; time-varying mix'))
    durbins=[];msgbins=[]
    for a,b in zip(duration_edges,duration_edges[1:]):
        label=f'[{a},{b}) minutes';choose=lambda f,a=a,b=b:a<=f['duration_minutes']<b;durbins.append((label,choose));make('duration',label,choose)
    for a,b in zip(message_edges,message_edges[1:]):
        label=f'[{a},{b}) messages';choose=lambda f,a=a,b=b:a<=(f['telegram_message_count'] or 0)<b;msgbins.append((label,choose));make('messages',label,choose)
    for dl,ds in durbins:
        for ml,ms in msgbins:make('duration_x_messages',dl+' / '+ml,lambda f,ds=ds,ms=ms:ds(f) and ms(f))
    for y in sorted({f['year'] for f in eligible}):make('year',str(y),lambda f,y=y:f['year']==y)
    csvwrite(report/'classification_duration_bias.csv',records)
    # Category contrasts after stratification: directions by year, monthly sample sufficiency explicit.
    contrasts=[]
    for c in ('ALL',*CATEGORIES):
        for scope in ('overall','year','month'):
            grouped=defaultdict(dict)
            for r in rows:
                if r['category']==c and r['scope']==scope and r['group']!='unknown':grouped[r['period']][r['group']]=r
            for period,states in sorted(grouped.items()):
                a,b=states['single_category'],states['multiple_categories']
                contrasts.append(dict(category=c,scope=scope,period=period,single_n=a['n'],multi_n=b['n'],single_median=a['median'],multi_median=b['median'],multi_minus_single_median=b['median']-a['median'] if a['n'] and b['n'] else None,adequate_descriptive_cell=a['n']>=10 and b['n']>=10))
    csvwrite(report/'single_multi_sensitivity.csv',contrasts)
    return rows,records,contrasts

def figures(report,facts,rows,bias,periods):
    os.environ.setdefault('MPLCONFIGDIR',str(Path(tempfile.gettempdir())/'kshe-matplotlib'));os.environ.setdefault('XDG_CACHE_HOME',str(Path(tempfile.gettempdir())/'kshe-cache'))
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig=report/'figures';fig.mkdir(exist_ok=True)
    def finish(name,note):
        plt.grid(alpha=.2);plt.figtext(.01,.01,note,fontsize=8);plt.tight_layout(rect=(0,.08,1,1));plt.savefig(fig/name,dpi=150);plt.close()
    ff=[f for f in facts if f['eligible']];states=('single_category','multiple_categories','unknown')
    plt.figure(figsize=(10,5));plt.boxplot([[f['duration_minutes'] for f in ff if group_state(f)==st] for st in states],tick_labels=states,showfliers=False);plt.yscale('log');plt.ylabel('Official duration, minutes (log scale)');plt.title('Eligible alerts: single / multiple / unknown — Aug2023 to Oct2026');finish('single_multi_duration.png','N=1803 eligible; experimental v1.6; unknown retained; whiskers describe distributions, not causal effects. October2026 partial.')
    plt.figure(figsize=(12,5));xx=np.arange(len(CATEGORIES))
    for i,st in enumerate(states[:2]):plt.bar(xx+(i-.5)*.3,[next(r['median'] for r in rows if r['scope']=='overall' and r['category']==c and r['group']==st) or 0 for c in CATEGORIES],width=.3,label=st)
    plt.xticks(xx,CATEGORIES,rotation=15);plt.ylabel('Median official duration (minutes)');plt.title('Category durations separated by co-occurrence — Aug2023 to Oct2026');plt.legend();finish('category_single_multi.png','Categories overlap across multi-category alerts; generic UAV is not confirmed Shahed. Sample sizes in single_multi_category_duration.csv.')
    figobj,axes=plt.subplots(1,2,figsize=(12,5))
    for ax,axis in zip(axes,('duration','messages')):
        rr=[r for r in bias if r['axis']==axis];p=[r['classification_yield'] for r in rr];ax.plot(np.arange(len(rr)),p,marker='o');ax.fill_between(np.arange(len(rr)),[r['ci_low'] for r in rr],[r['ci_high'] for r in rr],alpha=.2);ax.set_xticks(np.arange(len(rr)),[r['bin'] for r in rr],rotation=25,fontsize=8);ax.set_ylabel('Classified / eligible');ax.set_ylim(0,1);ax.set_title(axis)
    figobj.suptitle('Retrospective classification opportunity — Aug2023 to Oct2026');finish('classification_duration_volume.png','N=1803; descriptive yields and pointwise 14-day block intervals; duration/publication opportunity/confounding are not causal attribution.')
    for source in ('pavlo','vadimkin','official_archive'):
        rr=[r for r in periods if r['source']==source and r['scope']=='month'];plt.figure(figsize=(12,5));xx=[datetime.strptime(r['period'],'%Y-%m') for r in rr];plt.plot(xx,[r['official_resolved'] for r in rr],label='Kyiv Digital resolved');plt.plot(xx,[r['external_unique'] for r in rr],label=source+' deduplicated');plt.title('Kyiv City monthly count reconciliation: '+source);plt.xlabel('Kyiv local month; common full-day span only');plt.ylabel('Alert starts / month');plt.legend();finish('historical_'+source+'.png','Exact geographic filter; endpoint days excluded; boundary months partial; external estimated endpoints flagged; shared events are not independent gold.')

def run(root):
    os.environ.setdefault('MPLCONFIGDIR',str(Path(tempfile.gettempdir())/'kshe-matplotlib'));os.environ.setdefault('XDG_CACHE_HOME',str(Path(tempfile.gettempdir())/'kshe-cache'))
    report=root/'reports/external_validation';report.mkdir(parents=True,exist_ok=True)
    protected={str(p.relative_to(root)):digest(p) for folder in ('data','reports','config','src/kyiv_alerts') for p in sorted((root/folder).rglob('*')) if p.is_file() and '__pycache__' not in p.parts and '/external_validation/' not in str(p) and '/external/task0051/' not in str(p)}
    facts=pq.read_table(root/'data/processed/temporal_analysis/alert_analysis_fact.parquet').to_pylist();manifest=json.loads((root/'data/external/task0051/manifest.json').read_text())
    for m in manifest.values():assert digest(root/m['local_subset'])==m['subset_sha256']
    from .official import official_validation
    official=official_validation(root,facts)
    hist,periods=reconcile(facts,manifest,root,report);rows,bias,contrasts=category_analysis(facts,report);figures(report,facts,rows,bias,periods)
    assert sum(r['n'] for r in rows if r['scope']=='overall' and r['category']=='ALL')==1803
    assert all(digest(root/path)==h for path,h in protected.items())
    summary=dict(status='COMPLETE_WITH_DOCUMENTED_SOURCE_LIMITATIONS',physical_primary_verification='Kyiv Digital/alerts.in.ua schemas and dated Kyiv City statements verified; DSNS challenge and direct AirForce evidence limited',experimental_classification_unchanged=True,eligible=1803,groups=[r for r in rows if r['scope']=='overall' and r['category']=='ALL'],category_single_multi=[r for r in rows if r['scope']=='overall' and r['category']!='ALL'],classification_bias=[r for r in bias if r['axis'] in ('duration','messages')],historical_reconciliation=hist,external_source_manifest=manifest,official_validation=official,external_weapon_labels_available_for_comparison=True,external_label_agreement=None,readiness='FURTHER_VALIDATION_NEEDED',task006='NOT_STARTED; no unconditional forecasting approval',protected_hashes=protected,seed=20261011,block_days=14,bootstrap_replicates=800,software=dict(python=platform.python_version(),numpy=np.__version__),reproduce='python -m kyiv_alerts.external_validation --root .')
    (report/'external_validation_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    from .diagnostics import diagnostics
    diagnostics(root)
    print(json.dumps({k:summary[k] for k in ('status','groups','historical_reconciliation')},indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('.'));args=p.parse_args();run(args.root.resolve())
