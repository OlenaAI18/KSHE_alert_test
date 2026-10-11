"""Task005.1 source-preserving retrospective reconciliation; no predictions."""
from datetime import datetime,timezone,timedelta
from bisect import bisect_left,bisect_right
from collections import defaultdict
import csv
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import min_weight_full_bipartite_matching

def load_external(path):
    rows=[];groups={}
    with path.open() as f:
        for row in csv.DictReader(f):
            start=datetime.fromisoformat(row['started_at']);end=datetime.fromisoformat(row['finished_at'])
            if start.tzinfo is None or end.tzinfo is None:raise ValueError('External explicit offset required')
            start,end=start.astimezone(timezone.utc),end.astimezone(timezone.utc)
            if end<=start:raise ValueError('Invalid external interval')
            key=(start,end)
            if key in groups:groups[key]['source_csv_lines'].append(row['source_csv_line']);continue
            record=dict(start_time=start,end_time=end,naive=row.get('naive','False').lower()=='true',source_csv_lines=[row['source_csv_line']],external_record_id=row['source_csv_line'])
            rows.append(record);groups[key]=record
    return sorted(rows,key=lambda x:(x['start_time'],x['end_time']))

def assign_intervals(official,external,tolerance_seconds=300):
    """Maximum-cardinality positive-overlap matching, then minimum start error.

    A separate large-cost dummy edge exists for each official record. All genuine
    candidates retained for ambiguity/split review; no arbitrary greedy tie choice.
    """
    if not official or not external:return [],[]
    edges=[];ri=[];ci=[];cost=[]
    indexed=sorted(enumerate(external),key=lambda item:item[1]['start_time'])
    starts=[b['start_time'] for j,b in indexed]
    for i,a in enumerate(official):
        if a['end_time'] is None:raise ValueError('Unresolved official end excluded from matching')
        lo=bisect_left(starts,a['start_time']-timedelta(seconds=tolerance_seconds));hi=bisect_right(starts,a['start_time']+timedelta(seconds=tolerance_seconds))
        for j,b in indexed[lo:hi]:
            delta=(b['start_time']-a['start_time']).total_seconds()
            overlap=(min(a['end_time'],b['end_time'])-max(a['start_time'],b['start_time'])).total_seconds()
            if abs(delta)<=tolerance_seconds and overlap>0:
                edges.append((i,j));ri.append(i);ci.append(j);cost.append(1+abs(delta)+min(abs((b['end_time']-a['end_time']).total_seconds()),86400)*1e-7)
        ri.append(i);ci.append(len(external)+i);cost.append(1e9)
    mat=coo_matrix((cost,(ri,ci)),shape=(len(official),len(external)+len(official))).tocsr()
    ii,jj=min_weight_full_bipartite_matching(mat)
    pairs=[(int(i),int(j)) for i,j in zip(ii,jj) if j<len(external)]
    assert len({i for i,j in pairs})==len(pairs)==len({j for i,j in pairs})
    return pairs,edges

def group_state(row):
    n=len(row['markers'])
    return 'unknown' if n==0 else 'single_category' if n==1 else 'multiple_categories'

def distribution(rows):
    x=np.array([r['duration_minutes'] for r in rows],float)
    return dict(n=len(rows),median=float(np.median(x)) if len(x) else None,mean=float(np.mean(x)) if len(x) else None,q25=float(np.quantile(x,.25)) if len(x) else None,q75=float(np.quantile(x,.75)) if len(x) else None,p90=float(np.quantile(x,.9)) if len(x) else None,median_messages=float(np.median([r['telegram_message_count'] or 0 for r in rows])) if len(x) else None)
