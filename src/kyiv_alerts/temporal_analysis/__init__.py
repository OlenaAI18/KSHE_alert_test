"""Task005 retrospective calendar aggregation and dependence-aware diagnostics."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import numpy as np
KYIV=ZoneInfo('Europe/Kyiv')
UTC=timezone.utc
CATEGORIES=('shahed_uav','jet_uav','ballistic_high_speed','cruise_missile','mig31','strategic_aviation','other')

def eligible(f):
    return f['historical_range_relation']=='within' and f['coverage_status'] in ('covered','no_messages_found')

def split_interval(start,end):
    """Half-open UTC intervals clipped to actual Kyiv midnight instants."""
    if start is None or end is None or end<=start: raise ValueError('Resolved positive interval required')
    start,end=start.astimezone(UTC),end.astimezone(UTC)
    day=start.astimezone(KYIV).date()
    while True:
        left=datetime.combine(day,datetime.min.time(),KYIV).astimezone(UTC)
        right=datetime.combine(day+timedelta(days=1),datetime.min.time(),KYIV).astimezone(UTC)
        a,b=max(start,left),min(end,right)
        if b>a: yield day,a,b
        if right>=end:break
        day+=timedelta(days=1)

def union_minutes(intervals):
    total=0.;end=None
    for a,b in sorted(intervals):
        if b<=a:raise ValueError('Invalid union interval')
        if end is None or a>=end:total+=(b-a).total_seconds()/60
        elif b>end:total+=(b-end).total_seconds()/60
        end=max(end,b) if end else b
    return total

def block_indices(n,block,rng):
    """Circular moving blocks, joint sampling of all daily variables."""
    return ((rng.integers(0,n,size=(n+block-1)//block)[:,None]+np.arange(block))%n).ravel()[:n]

def bootstrap_ci(values,stat,block=14,reps=1200,seed=20261011):
    values=np.asarray(values);rng=np.random.default_rng(seed)
    draws=np.array([stat(values[block_indices(len(values),block,rng)]) for _ in range(reps)])
    return [float(x) for x in np.nanquantile(draws,[.025,.975])]

def acf(values,lag):
    x=np.asarray(values,float)
    if len(x)<=lag or np.std(x)==0:return float('nan')
    return float(np.corrcoef(x[:-lag],x[lag:])[0,1])

def holm(p):
    p=np.asarray(p,float);order=np.argsort(p);out=np.zeros(len(p));last=0.
    for j,i in enumerate(order):last=max(last,min(1.,(len(p)-j)*p[i]));out[i]=last
    return out.tolist()
