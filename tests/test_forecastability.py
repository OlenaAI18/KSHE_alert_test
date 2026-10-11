from datetime import datetime,date,timedelta,timezone
from pathlib import Path
import json
import numpy as np
import pyarrow.parquet as pq
import pytest
from kyiv_alerts.forecastability import aggregate,monday,features,baseline,candidate,metrics,paired_ci,KYIV
from kyiv_alerts.forecastability.__main__ import select,experiment

def rec(i,start,end=None):return dict(alert_id=str(i),start_time=start,end_time=end or start+timedelta(hours=1))

def test_weekly_aggregation_boundary_and_known_start():
    rs=[rec(1,datetime(2024,1,1,tzinfo=KYIV)),rec(2,datetime(2024,1,8,tzinfo=KYIV)),rec(3,datetime(2024,1,14,23,59,tzinfo=KYIV)),rec(4,datetime(2024,1,22,tzinfo=KYIV))];rs[1]['end_time']=None
    w=aggregate(rs);assert w[0]['complete_calendar_week'] is False
    assert w[1]['recorded_starts']==2 and w[1]['primary_count']==2
    assert w[-1]['complete_calendar_week'] is False
    assert sum(r['recorded_starts'] for r in w)==4

def test_no_records_unknown_not_zero():
    w=aggregate([rec(1,datetime(2024,1,1,tzinfo=KYIV)),rec(2,datetime(2024,1,29,tzinfo=KYIV))]);assert w[1]['primary_count'] is None and w[1]['recorded_starts']==0

def test_timezone_utc_sunday_is_kyiv_monday():
    w=aggregate([rec(1,datetime(2024,1,7,22,tzinfo=timezone.utc)),rec(2,datetime(2024,1,22,tzinfo=KYIV))]);assert w[0]['week_start']==date(2024,1,8)

@pytest.mark.parametrize('a,b,hours',[(datetime(2024,3,18,tzinfo=KYIV),datetime(2024,4,8,tzinfo=KYIV),167),(datetime(2024,10,14,tzinfo=KYIV),datetime(2024,11,4,tzinfo=KYIV),169)])
def test_dst_calendar_week_hours(a,b,hours):
    w=aggregate([rec(1,a),rec(2,b)]);assert w[1]['calendar_hours']==hours

def test_duplicate_id_rejected():
    r=rec(1,datetime(2024,1,1,tzinfo=KYIV))
    with pytest.raises(ValueError):aggregate([r,r])

def test_baselines_and_training_only_suffix():
    y=np.arange(1.,101.)
    assert baseline(y,52,'B0')==26.5
    assert baseline(y,52,'B1')==50.5
    assert baseline(y,52,'B2')==48.5
    assert baseline(y,52,'B3')==52
    assert baseline(y,52,'B4',13)==46
    z=y.copy();z[52:]=10000
    for n in ['B0','B1','B2','B3','B4']:assert baseline(y,52,n)==baseline(z,52,n)

def test_feature_availability_and_missing_calendar_week():
    y=np.arange(100,dtype=float);assert np.allclose(features(y,20),np.log1p([19,18,16,17.5,15.5]))
    y[19]=np.nan;assert features(y,20) is None
    assert np.isnan(baseline(y,20,'B1'))

def test_model_past_only_standardization_and_nonnegative():
    y=np.array([3+(i%9) for i in range(90)],float);z=y.copy();z[60:]=999999
    a,n=candidate(y,60,10);b,m=candidate(z,60,10)
    assert a==b and n==m and a>=0 and np.isfinite(a)

def test_metric_units():
    m=metrics([2,4],[1,6]);assert m['MAE']==1.5 and m['mean_bias']==.5 and m['RMSE']==pytest.approx(np.sqrt(2.5)) and m['WAPE']==.5

def test_ci_deterministic_and_constant():
    assert paired_ci(np.arange(39))==paired_ci(np.arange(39))
    assert paired_ci(np.ones(39)*2)==[2,2]

def test_selection_only_uses_development_grid():
    r={'actual':10,'B0':9,'B1':10,'B2':8,'B3':7,'B4_13':10,'B4_26':11,'B4_52':12,'M1_1':8,'M1_10':10,'M1_100':12}
    s=select([r]);assert s['M1_alpha']==10 and s['B4_window']==13 and s['selected_baseline']=='B1'

def test_real_output_reconciliation_and_cutoffs():
    root=Path(__file__).resolve().parents[1];p=root/'data/processed/forecastability/weekly_official_metrics.parquet'
    if not p.exists():pytest.skip('Task006 real artifacts not present')
    w=pq.read_table(p).to_pylist();rs=pq.read_table(p.with_name('walk_forward_predictions.parquet')).to_pylist()
    assert sum(x['recorded_starts'] for x in w)==2594
    ids=[i for x in w for i in x['official_alert_ids']];assert len(ids)==len(set(ids))==2594
    assert len(rs)==1068 and len({r['week_start'] for r in rs})==178
    for r in rs:
        assert r['training_last_week']<r['training_cutoff_exclusive']==r['week_start']
        assert r['feature_latest_week']<r['week_start']
        assert (r['week_end_exclusive']-r['week_start']).days==7
        assert np.isfinite(r['prediction']) and r['prediction']>=0
        assert (r['week_start']>=date(2026,1,5))==(r['phase']=='final_holdout')
        assert r['M1_alpha']==10 and r['B4_window']==13
    assert not any(r['week_start']==date(2023,10,9) for r in rs)
    s=json.loads((root/'reports/forecastability_validation/forecastability_summary.json').read_text());assert s['previous_files_unchanged'] and s['holdout_origins']==39

def test_final_outcomes_cannot_change_selection_or_first_prediction():
    d=date(2024,10,7);weeks=[dict(week_start=d+timedelta(weeks=i),week_end_exclusive=d+timedelta(weeks=i+1),primary_count=float(3+i%7),recorded_starts=3+i%7) for i in range(75)]
    dev,final,_,s=experiment(weeks)
    revised=[dict(r) for r in weeks]
    for r in revised:
        if r['week_start']>=date(2026,1,5):r['primary_count']=500.;r['recorded_starts']=500
    _,other,_,ss=experiment(revised)
    assert s==ss and final[0]['M1']==other[0]['M1']
    assert [r['M1'] for r in experiment(weeks)[1]]==[r['M1'] for r in final]
