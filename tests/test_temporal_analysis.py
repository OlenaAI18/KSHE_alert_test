from datetime import datetime,date,timedelta,timezone
from pathlib import Path
import json
import numpy as np
import pyarrow.parquet as pq
import pytest
from kyiv_alerts.temporal_analysis import KYIV,split_interval,union_minutes,bootstrap_ci,holm,block_indices
ROOT=Path(__file__).resolve().parents[1]

def test_overlap_union_and_adjacent_halfopen():
    a=datetime(2025,1,1,tzinfo=timezone.utc)
    assert union_minutes([(a,a+timedelta(minutes=60)),(a+timedelta(minutes=30),a+timedelta(minutes=90)),(a+timedelta(minutes=90),a+timedelta(minutes=100))])==100
    assert union_minutes([])==0
    with pytest.raises(ValueError):union_minutes([(a,a)])

@pytest.mark.parametrize('day,minutes',[(date(2025,3,30),1380),(date(2025,10,26),1500),(date(2025,4,1),1440)])
def test_dst_calendar_day_real_elapsed_minutes(day,minutes):
    a=datetime.combine(day,datetime.min.time(),KYIV);b=datetime.combine(day+timedelta(days=1),datetime.min.time(),KYIV)
    parts=list(split_interval(a,b));assert len(parts)==1
    assert union_minutes([(parts[0][1],parts[0][2])])==minutes

def test_midnight_split_no_extra_end_day():
    a=datetime(2025,6,1,23,30,tzinfo=KYIV);b=datetime(2025,6,3,0,0,tzinfo=KYIV)
    parts=list(split_interval(a,b));assert [p[0] for p in parts]==[date(2025,6,1),date(2025,6,2)]
    assert [union_minutes([(p[1],p[2])]) for p in parts]==[30,1440]
    with pytest.raises(ValueError):list(split_interval(a,None))

def test_joint_block_bootstrap_and_holm():
    x=np.arange(80);fun=lambda z:np.mean(z)
    assert bootstrap_ci(x,fun,reps=40)==bootstrap_ci(x,fun,reps=40)
    assert holm([.01,.04,.03])==pytest.approx([.03,.06,.06])
    i=block_indices(80,14,np.random.default_rng(1));assert len(i)==80 and min(i)>=0 and max(i)<80
    z=np.c_[x,2*x];assert np.all(z[i,1]==2*z[i,0])

def test_real_populations_missingness_and_calendar_reconcile():
    p=ROOT/'data/processed/temporal_analysis'
    facts=pq.read_table(p/'alert_analysis_fact.parquet').to_pylist();daily=pq.read_table(p/'daily_alert_metrics.parquet').to_pylist();months=pq.read_table(p/'monthly_alert_metrics.parquet').to_pylist()
    assert len(facts)==len({f['alert_id'] for f in facts})==2594
    assert sum(f['valid_interval'] for f in facts)==2593
    assert sum(f['eligible'] for f in facts)==1803
    assert sum(f['eligible'] and f['unknown'] for f in facts)==508
    assert sum(d['official_alert_starts'] for d in daily)==2593
    assert sum(d['all_record_starts'] for d in daily)==2594
    assert sum(d['supported_telegram_interpretation_count'] for d in daily)==1295
    assert sum(d['unknown_eligible_count'] for d in daily)==508
    assert all(d['shahed_uav'] is None for d in daily if d['date']<date(2023,8,17))
    assert all(0<=d['total_minutes_under_alert']<=d['calendar_day_minutes'] for d in daily)
    assert sum(d['total_minutes_under_alert'] for d in daily)==pytest.approx(sum(f['duration_minutes'] for f in facts if f['valid_interval']))
    assert next(m for m in months if m['month']=='2026-10')['partial_month']
    assert next(m for m in months if m['month']=='2022-02')['partial_month']
    assert sum(len(f['markers']) for f in facts if f['eligible'])>1295
    unresolved=next(f for f in facts if not f['valid_interval']);assert unresolved['end_local'] is None and unresolved['duration_minutes'] is None

def test_prior_hashes_and_original_timestamp_preservation():
    from kyiv_alerts.temporal_analysis.__main__ import digest
    summary=json.loads((ROOT/'reports/temporal_analysis/temporal_summary.json').read_text())
    assert all(digest(ROOT/p)==h for p,h in summary['protected_hashes'].items())
    originals={f['alert_id']:f for f in pq.read_table(ROOT/'data/interim/alerts.parquet').to_pylist()}
    for f in pq.read_table(ROOT/'data/processed/temporal_analysis/alert_analysis_fact.parquet').to_pylist():
        o=originals[f['alert_id']]
        assert f['start_time_original']==o['start_time_original'] and f['end_time_original']==o['end_time_original']
        assert f['start_local'].astimezone(timezone.utc)==o['start_time']

def test_transition_counts_and_statistical_families():
    import csv
    report=ROOT/'reports/temporal_analysis'
    def read(name):
        with (report/name).open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))
    assert sum(int(r['count']) for r in read('category_transitions_101.csv'))==101
    assert len(read('changed_previously_classified_alerts.csv'))==101
    stats=read('statistical_tests.csv')
    season=[r for r in stats if r['test'].startswith('season_')]
    assert len(season)==4 and all(float(r['holm_p'])>=float(r['p_value']) for r in season)
    assert all(not r['ci_low'] for r in stats if r['test']=='daily_acf_lag_28')
    duration=[r for r in stats if r['test'].startswith('duration_month_adjusted_')]
    assert len(duration)==7 and all(float(r['holm_p'])>=float(r['p_value']) for r in duration)
    trends=read('sensitivity_category_trends.csv')
    ball=[r for r in trends if r['category']=='ballistic_high_speed' and r['mode']=='all_complete_telegram_months']
    assert float(next(r for r in ball if r['version']=='v1_5')['descriptive_share_slope_per_month'])>0
    assert float(next(r for r in ball if r['version']=='v1_6')['descriptive_share_slope_per_month'])<0
