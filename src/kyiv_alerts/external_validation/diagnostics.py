from pathlib import Path
from collections import Counter
from datetime import datetime,timedelta
import csv,json
import pyarrow.parquet as pq
import numpy as np
from kyiv_alerts.external_validation import load_external,group_state
from kyiv_alerts.external_validation.__main__ import csvwrite
from kyiv_alerts.temporal_analysis import KYIV,UTC,block_indices
from kyiv_alerts.integration.linking import possible_instants

def diagnostics(root):
    report=root/'reports/external_validation';facts=pq.read_table(root/'data/processed/temporal_analysis/alert_analysis_fact.parquet').to_pylist();manifest=json.loads((root/'data/external/task0051/manifest.json').read_text());s=json.loads((report/'external_validation_summary.json').read_text());unresolved=next(f for f in facts if f['end_time'] is None);dst=[];near=[];weekly=[]
    for source,m in manifest.items():
     ext=load_external(root/m['local_subset']);row=next(r for r in s['historical_reconciliation'] if r['source']==source);a=datetime.fromisoformat(row['common_start']).replace(tzinfo=KYIV).astimezone(UTC);b=datetime.fromisoformat(row['common_end_exclusive']).replace(tzinfo=KYIV).astimezone(UTC);ee=[r for r in ext if a<=r['start_time']<b]
     for r in ext:
      delta=(r['start_time']-unresolved['start_time']).total_seconds()/60
      if abs(delta)<=10:
       candidates=possible_instants(unresolved['end_time_original']);dst.append(dict(source=source,official_alert_id=unresolved['alert_id'],external_record_id=r['external_record_id'],external_csv_lines=r['source_csv_lines'],start_delta_minutes=delta,external_end=r['end_time'].isoformat(),estimated_end=r['naive'],candidate_official_ends=[c.isoformat() for c in candidates],end_deltas_to_folds_minutes=[(r['end_time']-c).total_seconds()/60 for c in candidates],interpretation='observational fold evidence only; official source end remains null; archive may impute ends'))
     with (report/'historical_reconciliation.csv').open(encoding='utf-8-sig') as f:rr=[r for r in csv.DictReader(f) if r['source']==source and r['status']=='official_unmatched']
     for r in rr:
      start=datetime.fromisoformat(r['official_start']);nearest=min(ee,key=lambda x:abs((x['start_time']-start).total_seconds()));delta=(nearest['start_time']-start).total_seconds()/60
      near.append(dict(source=source,official_alert_id=r['official_alert_id'],official_start=r['official_start'],nearest_external_record=nearest['external_record_id'],nearest_external_start=nearest['start_time'].isoformat(),nearest_delta_minutes=delta,nearest_is_estimated_end=nearest['naive'],month=start.astimezone(KYIV).strftime('%Y-%m'),note='nearest time only, not a validated event link; no correction applied'))
     exposure=Counter((a.astimezone(KYIV).date()+timedelta(days=i)).weekday() for i in range((b-a).days+2) if a.astimezone(KYIV).date()+timedelta(days=i)<b.astimezone(KYIV).date())
     for name,rows in [('official',[f for f in facts if f['end_time'] and a<=f['start_time']<b]),('external',ee)]:
      counts=Counter(f['start_time'].astimezone(KYIV).weekday() for f in rows)
      for day in range(7):weekly.append(dict(source_comparison=source,population=name,weekday=day,weekday_name=['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][day],observed_days=exposure[day],alert_starts=counts[day],starts_per_day=counts[day]/exposure[day],scope='Kyiv City common span; excludes unresolved; descriptive not weekly periodicity test'))
    csvwrite(report/'dst_external_candidates.csv',dst,fields=['source','official_alert_id','external_record_id','external_csv_lines','start_delta_minutes','external_end','estimated_end','candidate_official_ends','end_deltas_to_folds_minutes','interpretation']);csvwrite(report/'unmatched_nearest_times.csv',near);csvwrite(report/'kyiv_weekday_comparison.csv',weekly)
    # Explicit sparse-cell joint strata, threshold>=10 fixed as descriptive sufficiency only.
    with (report/'single_multi_sensitivity.csv').open(encoding='utf-8-sig') as f:rr=list(csv.DictReader(f))
    out=[]
    for c in ['ALL','shahed_uav','jet_uav','ballistic_high_speed','cruise_missile','mig31','strategic_aviation','other']:
     for scope in ['year','month']:
      usable=[r for r in rr if r['category']==c and r['scope']==scope and r['adequate_descriptive_cell']=='True'];positive=sum(float(r['multi_minus_single_median'])>0 for r in usable)
      out.append(dict(category=c,scope=scope,adequate_cells=len(usable),multi_median_greater_cells=positive,multi_median_not_greater_cells=len(usable)-positive,threshold='at least10 single AND10 multiple; descriptive, no significance claim'))
    csvwrite(report/'single_multi_sensitivity_summary.csv',out)
    print('DST',dst);print('sensitivity',out[:4])
