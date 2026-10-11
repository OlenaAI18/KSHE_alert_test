"""Past-only weekly archived-count validation; no operational forecasting."""
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import numpy as np
from sklearn.linear_model import PoissonRegressor
from sklearn.preprocessing import StandardScaler
KYIV=ZoneInfo('Europe/Kyiv')

def monday(day):return day-timedelta(days=day.weekday())

def aggregate(records):
    ids=[r['alert_id'] for r in records]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate official alert IDs')
    first=min(r['start_time'] for r in records).astimezone(KYIV).date()
    last=max(r['end_time'] for r in records if r['end_time']).astimezone(KYIV).date()
    buckets={}
    for r in records:
        d=monday(r['start_time'].astimezone(KYIV).date());buckets.setdefault(d,[]).append(r['alert_id'])
    rows=[];d=monday(first)
    while d<=monday(last):
        end=d+timedelta(days=7)
        complete=d>first and end<=last
        count=len(buckets.get(d,[]))
        rows.append(dict(week_start=d,week_end_exclusive=end,recorded_starts=count,
                         official_alert_ids=buckets.get(d,[]),complete_calendar_week=complete,
                         primary_count=float(count) if complete and count else None,
                         coverage_status='internal_completeness_unverified' if count else 'no_records_unknown',
                         calendar_hours=(datetime.combine(end,datetime.min.time(),KYIV).timestamp()-datetime.combine(d,datetime.min.time(),KYIV).timestamp())/3600))
        d=end
    return rows

def features(y,i):
    if i<8:return None
    window=np.asarray(y[i-8:i],float)
    if not np.isfinite(window).all():return None
    return np.log1p([y[i-1],y[i-2],y[i-4],np.mean(y[i-4:i]),np.mean(window)])

def baseline(y,i,name,window=13):
    look={'B0':i,'B1':4,'B2':8,'B3':1,'B4':window}[name]
    vals=np.asarray(y[max(0,i-look):i],float)
    if name in ('B1','B2','B3') and not np.isfinite(vals).all():return float('nan')
    return float(np.nanmean(vals)) if np.isfinite(vals).any() else float('nan')

def candidate(y,i,alpha):
    ix=[j for j in range(8,i) if np.isfinite(y[j]) and features(y,j) is not None]
    f=features(y,i)
    if f is None or len(ix)<20:return float('nan'),len(ix)
    x=np.array([features(y,j) for j in ix]);target=np.array([y[j] for j in ix])
    scaler=StandardScaler().fit(x)
    model=PoissonRegressor(alpha=alpha,max_iter=500,tol=1e-7).fit(scaler.transform(x),target)
    pred=float(model.predict(scaler.transform([f]))[0])
    if not np.isfinite(pred) or pred<0:raise ValueError('Invalid prediction')
    return pred,len(ix)

def metrics(actual,pred):
    a,p=np.asarray(actual,float),np.asarray(pred,float);e=p-a
    return dict(n=len(a),MAE=float(np.mean(abs(e))),RMSE=float(np.sqrt(np.mean(e*e))),
                mean_bias=float(np.mean(e)),WAPE=float(sum(abs(e))/sum(a)) if sum(a)>0 else None)

def paired_ci(diff,block=4,reps=2000,seed=20261011):
    v=np.asarray(diff,float);rng=np.random.default_rng(seed);n=len(v)
    indices=((rng.integers(0,n,size=(reps,(n+block-1)//block,1))+np.arange(block))%n).reshape(reps,-1)[:,:n]
    return np.quantile(v[indices].mean(axis=1),[.025,.975]).tolist()
