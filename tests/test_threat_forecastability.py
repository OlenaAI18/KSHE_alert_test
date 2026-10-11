from datetime import datetime,date,timedelta
from pathlib import Path
import json,csv
import numpy as np
import pytest
from kyiv_alerts.threat_forecastability import CATEGORIES,KYIV,build_weeks,asof_series,walk,difference_ci,release_aware_candidate

def alert(i,start,cats=(),unknown=False,end=None):
    r=dict(alert_id=str(i),start_time=start,end_time=end or start+timedelta(hours=1),historical_range_relation='within',coverage_status='covered',unknown=unknown,telegram_message_count=2,telegram_text_message_count=2)
    r.update({c:c in cats for c in CATEGORIES});return r

def versions(rows):return {v:[dict(r) for r in rows] for v in ['v15','v16']}

def marker(i,message,support=()):return dict(alert_id=str(i),message_id=message,support_message_ids=list(support),accepted_for_aggregation=True,category='shahed_uav',source_message_time=datetime(2024,1,9,tzinfo=KYIV),attribution_strength='direct',evidence_status='current_threat',uncertainty_flag=False,subtype='generic_uav',inferred_shorthand=False)

def test_unique_alert_per_nonexclusive_category_and_unknown():
    start=datetime(2024,1,8,12,tzinfo=KYIV);rs=[alert(1,start,['shahed_uav','mig31']),alert(2,start+timedelta(hours=2),unknown=True)]
    m=marker(1,'10');weeks,_,_=build_weeks(versions(rs),{'10':start}, {'v15':[m,m],'v16':[m,m]},datetime(2024,1,4,tzinfo=KYIV),datetime(2024,1,22,tzinfo=KYIV))
    a=weeks[0]['versions']['v16'];assert a['counts']['shahed_uav']==a['counts']['mig31']==1 and a['unknown']==1 and a['eligible']==2
    assert weeks[1]['observed'] is False

def test_observed_nondetection_is_not_physical_negative():
    r=alert(1,datetime(2024,1,8,12,tzinfo=KYIV),unknown=True)
    w,_,_=build_weeks(versions([r]),{}, {'v15':[],'v16':[]},datetime(2024,1,4,tzinfo=KYIV),datetime(2024,1,15,tzinfo=KYIV))
    assert w[0]['observed'] and w[0]['versions']['v16']['counts']['shahed_uav']==0 and w[0]['versions']['v16']['unknown']==1

def test_release_uses_support_and_later_of_both_versions():
    r=alert(1,datetime(2024,1,8,12,tzinfo=KYIV));late=datetime(2024,1,15,2,tzinfo=KYIV)
    m=marker(1,'10',['11']);w,_,_=build_weeks(versions([r]),{'10':r['start_time'],'11':late},{'v15':[m],'v16':[]},datetime(2024,1,4,tzinfo=KYIV),datetime(2024,1,15,tzinfo=KYIV))
    assert w[0]['available_at']==late
    assert np.isnan(asof_series(w,'v16','shahed_uav',datetime(2024,1,15,tzinfo=KYIV))[0])
    assert asof_series(w,'v16','shahed_uav',late)[0]==0

def test_missing_support_blocks_week():
    r=alert(1,datetime(2024,1,8,12,tzinfo=KYIV));m=marker(1,'missing')
    w,_,_=build_weeks(versions([r]),{}, {'v15':[m],'v16':[]},datetime(2024,1,4,tzinfo=KYIV),datetime(2024,1,15,tzinfo=KYIV))
    assert not w[0]['observed'] and 'support_timestamp_unavailable' in w[0]['unavailable_reason']

def test_unresolved_interval_not_filled():
    r=alert(1,datetime(2024,1,8,12,tzinfo=KYIV));r['end_time']=None;r['coverage_status']='unresolved_temporal_ambiguity'
    w,_,_=build_weeks(versions([r]),{}, {'v15':[],'v16':[]},datetime(2024,1,4,tzinfo=KYIV),datetime(2024,1,15,tzinfo=KYIV))
    assert not w[0]['observed']

def test_duplicate_source_ids_rejected():
    r=alert(1,datetime(2024,1,8,tzinfo=KYIV))
    with pytest.raises(AssertionError):build_weeks(versions([r,r]),{}, {'v15':[],'v16':[]},datetime(2024,1,4,tzinfo=KYIV),datetime(2024,1,15,tzinfo=KYIV))

def synthetic_weeks():
    d=date(2024,10,7);rows=[]
    for i in range(80):
        start=d+timedelta(weeks=i);end=start+timedelta(days=7)
        rows.append(dict(week_start=start,week_end_exclusive=end,available_at=datetime.combine(end,datetime.min.time(),KYIV),observed=True,versions={v:dict(counts={c:3+i%5 for c in CATEGORIES}) for v in ['v15','v16']}))
    return rows

def test_no_future_outcomes_in_predictions_or_past_scaler():
    w=synthetic_weeks();a=walk(w,'shahed_uav',model=True)
    revised=synthetic_weeks()
    for row in revised[53:]:
        for v in ['v15','v16']:row['versions'][v]['counts']['shahed_uav']=999
    b=walk(revised,'shahed_uav',model=True)
    assert a[0]['M1']==b[0]['M1'] and a[0]['B1']==b[0]['B1']
    assert all(r['training_last_week']<r['week_start'] and r['latest_training_release']<=r['origin'] for r in a)

def test_late_prior_week_excludes_origin_without_calendar_compression():
    w=synthetic_weeks();w[51]['available_at']+=timedelta(hours=1)
    a=walk(w,'shahed_uav');assert w[52]['week_start'] not in {r['week_start'] for r in a}
    assert w[53]['week_start'] in {r['week_start'] for r in a}

def test_development_selection_cannot_use_late_target_release():
    w=synthetic_weeks();i=next(i for i,r in enumerate(w) if r['week_start']==date(2025,12,29));w[i]['available_at']=datetime(2026,1,5,1,tzinfo=KYIV)
    a=walk(w,'shahed_uav');assert date(2025,12,29) not in {r['week_start'] for r in a}

def test_training_features_use_own_historical_origin():
    w=synthetic_weeks();i=60;y=asof_series(w,'v16','shahed_uav',datetime.combine(w[i]['week_start'],datetime.min.time(),KYIV))
    _,n=release_aware_candidate(w,'shahed_uav','v16',i,y)
    w[20]['available_at']+=timedelta(hours=1)
    _,m=release_aware_candidate(w,'shahed_uav','v16',i,y)
    assert m==n-1

def test_bootstrap_multiple_family_interval_and_repeatability():
    x=np.arange(36,dtype=float)
    ordinary=difference_ci(x);adjusted=difference_ci(x,alpha=.05/14)
    assert adjusted[0]<=ordinary[0]<=ordinary[1]<=adjusted[1]
    assert adjusted==difference_ci(x,alpha=.05/14)

def test_real_gate_predictions_and_versions_preserved():
    import pyarrow.parquet as pq
    root=Path(__file__).resolve().parents[1];out=root/'reports/threat_forecastability'
    if not (out/'threat_forecastability_summary.json').exists():pytest.skip('Task006.1 local artifacts absent')
    s=json.loads((out/'threat_forecastability_summary.json').read_text());assert s['prior_files_unchanged'] and not s['taxonomy_historical_asof_available']
    gates={r['category']:r for r in s['quality_gates']};assert [c for c in CATEGORIES if gates[c]['gate_pass']]==['shahed_uav','ballistic_high_speed']
    with (out/'category_walk_forward_results.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
    assert len(rows)==924 and {r['category'] for r in rows}=={'shahed_uav','ballistic_high_speed'}
    assert all(r['training_last_week']<r['week_start'] for r in rows)
    assert all(datetime.fromisoformat(r['latest_training_release'])<=datetime.fromisoformat(r['origin']) for r in rows)
    w=pq.read_table(root/'data/processed/threat_forecastability_v1/weekly_reported_category_metrics.parquet').to_pylist()
    for r in w:
        if r['complete_observed_week']:assert r['observed_category_count']==len(set(r['category_alert_ids']))
        else:assert r['observed_category_count'] is None
    assert {r['decision'] for r in s['decisions']}=={'INCONCLUSIVE','NO_STABLE_GAIN_OVER_BASELINES','INSUFFICIENT_DATA_FOR_RELIABLE_FORECAST_TEST'}

def test_calendar_block_bootstrap_retains_unavailable_slots():
    dates=[date(2026,1,5)+timedelta(weeks=i) for i in range(39) if i not in [5,10,22]]
    a=difference_ci(np.arange(36),dates=dates)
    assert a==difference_ci(np.arange(36),dates=dates) and np.isfinite(a).all()
    assert a!=difference_ci(np.arange(36))
