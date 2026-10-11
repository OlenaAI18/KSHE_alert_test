from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import csv
import hashlib
import json
import pytest
import pyarrow.parquet as pq
from kyiv_alerts.myth_lab import (TITLES, VERDICTS, night_minutes, complete_days,
                                  event_comparison, before_after, calm_comparison)
from kyiv_alerts.myth_lab.__main__ import run
ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture(scope='module')
def generated(tmp_path_factory):
    root=tmp_path_factory.mktemp('myth')
    return run(ROOT,root/'reports',root/'public')

def test_public_result_schema(generated):
    summary,results=generated
    assert summary['official_starts_reconciled']==2594
    assert summary['daily_comparison_days']==1671
    assert summary['uav_unique_alerts']==630+131-70
    required={'myth_id','title_uk','short_question_uk','what_is_tested_uk','metric_summary','chart_data','headline_result_uk','verdict_label','verdict_state','limitations_uk','methodology_note_uk'}
    assert [r['myth_id'] for r in results]==[f'myth_{i}' for i in range(1,8)]
    assert [r['title_uk'] for r in results]==TITLES
    for r in results:
        assert set(r)==required
        assert r['verdict_state'] in VERDICTS
        assert len(r['chart_data']['labels'])==len(r['chart_data']['values'])
        assert r['limitations_uk'] and r['methodology_note_uk']
    assert summary['new_significance_tests'] is False

def test_calendar_integrity_and_source_references():
    cfg=json.loads((ROOT/'config/myth_lab_v1.json').read_text())
    sources={r['source_id'] for r in csv.DictReader((ROOT/'reports/myth_lab/source_register.csv').open())}
    for group in ['symbolic_dates','ukrainian_holidays']:
        rows=cfg[group];assert len({r['month_day'] for r in rows})==len(rows)
        for r in rows:
            assert r['source_id'] in sources
            for year in range(2022,2027):date.fromisoformat(f'{year}-{r["month_day"]}')
    assert [r['date'] for r in cfg['negotiations']]==['2022-03-29','2025-05-16','2025-06-02']
    for r in cfg['negotiations']:assert r['source_id'] in sources
    moving=set(cfg['control_moving_holiday_exclusions'])
    # Independent Julian computus validates manually curated Easter/Trinity dates.
    for y in range(2022,2027):
        a,b,c=y%4,y%7,y%19;d=(19*c+15)%30;e=(2*a+4*b-d+34)%7
        easter=date(y,(d+e+114)//31,(d+e+114)%31+1)+timedelta(days=13)
        assert str(easter) in moving and str(easter+timedelta(days=49)) in moving
    assert cfg['matched_control_offsets_days']==[-28,-21,-14,-7,7,14,21,28]

@pytest.mark.parametrize('start,end,expected',[
    ('2024-03-30T22:00:00','2024-03-31T06:00:00',420),
    ('2024-10-26T22:00:00','2024-10-27T06:00:00',540),
    ('2024-06-01T06:00:00','2024-06-01T22:00:00',0),
    ('2024-06-01T21:30:00','2024-06-01T22:30:00',30),
    ('2024-06-01T22:00:00','2024-06-03T06:00:00',960),
])
def test_night_dst_and_half_open_overlap(start,end,expected):
    zone=ZoneInfo('Europe/Kyiv')
    assert night_minutes(datetime.fromisoformat(start).replace(tzinfo=zone),datetime.fromisoformat(end).replace(tzinfo=zone))==expected

def test_night_rejects_unresolved_or_naive():
    with pytest.raises(ValueError):night_minutes(datetime(2024,1,1),datetime(2024,1,2))

def synthetic_day(d,count=0):
    return {'date':d,'month':d.strftime('%Y-%m'),'all_record_starts':count,'source_boundary_day':False,'unresolved_interval_day':False}

def test_unknown_calendar_gaps_do_not_create_calm():
    start=date(2024,1,1);daily={start+timedelta(days=i):synthetic_day(start+timedelta(days=i),0) for i in range(8) if i!=3}
    result=calm_comparison(daily)
    assert result['calm_days']==1  # Only Jan8 has three observed preceding dates after the Jan4 gap.


def test_complete_day_mask():
    rows=[synthetic_day(date(2023,10,8)),synthetic_day(date(2023,10,9)),synthetic_day(date(2023,10,15)),synthetic_day(date(2023,10,16))]
    rows[0]['source_boundary_day']=True
    assert set(complete_days(rows))=={date(2023,10,16)}

def test_matching_does_not_use_event_dates_or_other_month():
    start=date(2024,5,1);daily={start+timedelta(days=i):synthetic_day(start+timedelta(days=i),i) for i in range(31)}
    events=[(date(2024,5,9),'a'),(date(2024,5,16),'b')]
    result=event_comparison(daily,events,[-14,-7,7,14],0,[date(2024,5,23)])
    for r in result['events']:
        for d in r['control_centers']:
            assert d.startswith('2024-05') and d not in ['2024-05-09','2024-05-16','2024-05-23']
            assert date.fromisoformat(d).weekday()==date.fromisoformat(r['date']).weekday()

def test_negotiation_day_not_counted():
    d=date(2024,5,16);daily={d+timedelta(days=i):synthetic_day(d+timedelta(days=i),100 if i==0 else 2) for i in range(-3,4)}
    r=before_after(daily,[{'date':str(d)}],3);assert r['before_mean']==r['after_mean']==2

def test_real_night_and_prior_correlation_reconcile(generated):
    _,r=generated;night=r[2]['metric_summary']
    assert night['unique_alerts']==691
    assert night['night_alert_minutes']<=night['total_alert_minutes']
    assert night['night_minute_share']==pytest.approx(0.6318232542654539)
    assert night['yearly'][-1]['night_minute_share']==pytest.approx(0.39897166697027187)
    assert '2026' in r[2]['headline_result_uk']
    stats=list(csv.DictReader((ROOT/'reports/temporal_analysis/statistical_tests.csv').open(encoding='utf-8-sig')))
    raw=next(x for x in stats if x['test']=='daily_acf_lag_1' and x['block_length']=='14')
    assert r[6]['metric_summary']['raw']['effect']==float(raw['effect'])
    adjusted=next(x for x in stats if x['test']=='within_month_residual_acf_lag_1')
    assert r[6]['metric_summary']['month_adjusted']['effect']==float(adjusted['effect'])
    assert r[4]['metric_summary']['after_calm_mean']<r[4]['metric_summary']['after_other_mean']
    assert r[4]['metric_summary']['month_adjusted_difference']>0

def test_no_individual_records_or_local_paths(generated):
    def inspect(v):
        if isinstance(v,dict):
            assert not set(v)&{'text','message_text','message_id','alert_id','supporting_message_ids','start_time_original'}
            for x in v.values():inspect(x)
        elif isinstance(v,(list,tuple)):
            for x in v:inspect(x)
        elif isinstance(v,str):assert '/workspace/' not in v and '/tmp/' not in v
    inspect(generated)

def test_reproducible_and_inputs_immutable(tmp_path):
    summary,_=run(ROOT,tmp_path/'a-reports',tmp_path/'a-public')
    run(ROOT,tmp_path/'b-reports',tmp_path/'b-public')
    for a in (tmp_path/'a-public').iterdir():assert a.read_bytes()==(tmp_path/'b-public'/a.name).read_bytes()
    for a in (tmp_path/'a-reports').iterdir():assert a.read_bytes()==(tmp_path/'b-reports'/a.name).read_bytes()
    for path,h in summary['inputs'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==h
