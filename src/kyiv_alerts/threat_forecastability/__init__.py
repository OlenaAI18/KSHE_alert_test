"""Forecastability of frozen reported markers, never physical threat incidence."""
from datetime import datetime,timedelta
from collections import Counter
import numpy as np
from kyiv_alerts.forecastability import KYIV,monday,baseline,features,metrics
CATEGORIES=('shahed_uav','jet_uav','ballistic_high_speed','cruise_missile','mig31','strategic_aviation','other')

def eligible(r):return r['historical_range_relation']=='within' and r['coverage_status'] in ('covered','no_messages_found') and r['end_time'] is not None

def build_weeks(versions,message_times,marker_rows,telegram_start,source_end):
    """Aligned source weeks; conservative release includes all corroboration."""
    common=set(r['alert_id'] for r in versions['v16'])
    assert all(len(rows)==len(common) and set(r['alert_id'] for r in rows)==common for rows in versions.values())
    releases={};invalid=set();strength=Counter();terms=Counter()
    for v,markers in marker_rows.items():
        for r in markers:
            if not r['accepted_for_aggregation']:continue
            key=(v,r['alert_id']);ids=set(r.get('support_message_ids') or [])|{r['message_id']}
            if r.get('anchor_message_id'):ids.add(r['anchor_message_id'])
            times=[message_times.get(i) for i in ids]
            if r.get('source_message_time'):times.append(r['source_message_time'])
            if any(t is None for t in times):invalid.add(key)
            else:releases[key]=max([releases.get(key,min(times))]+times)
            strength[(v,r['category'],r.get('attribution_strength') or r['evidence_status'],bool(r['uncertainty_flag']))]+=1
            year=r['source_message_time'].astimezone(KYIV).year if r['source_message_time'] else None
            terms[(v,r['category'],year,r['subtype'],bool(r['inferred_shorthand']))]+=1
    first=monday(telegram_start.astimezone(KYIV).date())+timedelta(days=7)
    last=source_end.astimezone(KYIV).date();rows=[];day=first
    indexed={v:{} for v in versions}
    for v,rs in versions.items():
        for r in rs:indexed[v].setdefault(monday(r['start_time'].astimezone(KYIV).date()),[]).append(r)
    while day+timedelta(days=7)<=last:
        end=day+timedelta(days=7);bound=datetime.combine(end,datetime.min.time(),KYIV)
        release=bound;reason=[];perversion={}
        for v in versions:
            rs=indexed[v].get(day,[])
            if not rs:reason.append('no_official_records_unknown')
            if any(not eligible(r) for r in rs):reason.append('unresolved_or_incomplete_coverage')
            if any((v,r['alert_id']) in invalid for r in rs):reason.append('support_timestamp_unavailable')
            eligible_rs=[r for r in rs if eligible(r)]
            times=[r['end_time'] for r in rs if r['end_time']]+[releases[(v,r['alert_id'])] for r in rs if (v,r['alert_id']) in releases]
            if times:release=max([release]+times)
            classified=sum(not r['unknown'] for r in eligible_rs)
            counts={c:sum(bool(r[c]) for r in eligible_rs) for c in CATEGORIES}
            perversion[v]=dict(linked_messages=sum(r.get('telegram_message_count') or 0 for r in eligible_rs),text_messages=sum(r.get('telegram_text_message_count') or 0 for r in eligible_rs),eligible=len(eligible_rs),unknown=sum(bool(r['unknown']) for r in eligible_rs),classified=classified,coverage=classified/len(eligible_rs) if eligible_rs else None,counts=counts,alert_ids=[r['alert_id'] for r in rs],category_ids={c:[r['alert_id'] for r in eligible_rs if r[c]] for c in CATEGORIES})
        rows.append(dict(week_start=day,week_end_exclusive=end,available_at=release,observed=not reason,unavailable_reason=';'.join(sorted(set(reason))),versions=perversion));day=end
    return rows,strength,terms

def asof_series(weeks,version,category,origin):
    return np.array([r['versions'][version]['counts'][category] if r['observed'] and r['available_at']<=origin else np.nan for r in weeks],float)

def release_aware_candidate(weeks,category,version,i,current_y):
    """Training features reconstructed at each supervised sample's own origin."""
    from sklearn.linear_model import PoissonRegressor
    from sklearn.preprocessing import StandardScaler
    x=[];target=[]
    for j in range(8,i):
        if not np.isfinite(current_y[j]):continue
        historical_origin=datetime.combine(weeks[j]['week_start'],datetime.min.time(),KYIV)
        f=features(asof_series(weeks,version,category,historical_origin),j)
        if f is not None:x.append(f);target.append(current_y[j])
    if len(x)<20:raise ValueError('Insufficient as-of supervised training rows')
    scaler=StandardScaler().fit(x)
    model=PoissonRegressor(alpha=10,max_iter=500,tol=1e-7).fit(scaler.transform(x),target)
    f=features(current_y,i)
    prediction=float(model.predict(scaler.transform([f]))[0])
    if not np.isfinite(prediction) or prediction<0:raise ValueError('Invalid category prediction')
    return prediction,len(x)

def walk(weeks,category,version='v16',model=False):
    rows=[]
    for i in range(52,len(weeks)):
        target=weeks[i]
        if not target['observed']:continue
        if target['week_start'].year<2026 and target['available_at']>datetime(2026,1,5,tzinfo=KYIV):continue
        origin=datetime.combine(target['week_start'],datetime.min.time(),KYIV)
        y=asof_series(weeks,version,category,origin)
        if features(y,i) is None:continue
        row=dict(category=category,version=version,week_start=target['week_start'],week_end_exclusive=target['week_end_exclusive'],origin=origin,phase='development' if target['week_start'].year<2026 else 'final_holdout',actual=target['versions'][version]['counts'][category],training_last_week=weeks[i-1]['week_start'],latest_training_release=max(r['available_at'] for j,r in enumerate(weeks[:i]) if np.isfinite(y[j])),training_observed_targets=int(np.isfinite(y[:i]).sum()),target_available_at=target['available_at'])
        for n in ['B0','B1','B2','B3']:row[n]=baseline(y,i,n)
        row['Z0']=0.
        if model:row['M1'],row['model_training_rows']=release_aware_candidate(weeks,category,version,i,y)
        rows.append(row)
    return rows

def difference_ci(diff,block=4,reps=4000,seed=20261011,alpha=.05,dates=None):
    v=np.asarray(diff,float)
    if dates is not None:
        first=min(dates);grid=np.full((max(dates)-first).days//7+1,np.nan)
        for day,value in zip(dates,v):grid[(day-first).days//7]=value
        v=grid
    n=len(v);rng=np.random.default_rng(seed)
    idx=((rng.integers(0,n,size=(reps,(n+block-1)//block,1))+np.arange(block))%n).reshape(reps,-1)[:,:n]
    draws=np.nanmean(v[idx],axis=1)
    if not np.isfinite(draws).all():raise ValueError('Empty observed bootstrap draw')
    return np.quantile(draws,[alpha/2,1-alpha/2]).tolist()
