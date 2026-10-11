"""Explicitly synthetic interval and coverage fixtures; no production data."""
from datetime import datetime, timedelta, timezone
import json
import random
import pytest
import pyarrow.parquet as pq
from kyiv_alerts.integration.linking import integrate
from kyiv_alerts.integration.__main__ import (main,write_table,validate_h2)
from kyiv_alerts.ingestion.storage import schema_for

BASE=datetime(2024,1,1,10,tzinfo=timezone.utc)


def alert(aid='a',start=BASE,end=BASE+timedelta(hours=1)):
    return {'alert_id':aid,'start_time':start,'end_time':end,
            'duration_minutes':(end-start).total_seconds()/60 if end and start else None,
            'start_time_original':start.isoformat() if start else None,
            'end_time_original':end.isoformat() if end else None,'validation_status':'valid'}


def message(mid='m',instant=BASE+timedelta(minutes=10),text=True,service=False,**extra):
    return {'message_id':mid,'message_time':instant,
            'message_time_original':instant.isoformat() if instant else None,
            'timestamp_status':'valid_explicit_offset' if instant else 'missing',
            'source_file':'synthetic/messages.html','source_message_index':1,
            'has_text':text,'text':'Synthetic text' if text else None,
            'is_service_message':service,**extra}


def bounds():
    return [message('earlier',BASE-timedelta(days=1)),message('later',BASE+timedelta(days=1))]


@pytest.mark.parametrize(('instant','matched'),[
    (BASE+timedelta(minutes=10),True),
    (BASE,True),
    (BASE+timedelta(hours=1),False),
    (BASE-timedelta(seconds=1),False),
])
def test_half_open_membership(instant,matched):
    links,coverage,_=integrate([alert()],[message(instant=instant),*bounds()])
    assert bool(links)==matched
    assert coverage[0]['coverage_status']==('covered' if matched else 'no_messages_found')


def test_multiple_and_empty_text_messages():
    links,coverage,report=integrate([alert()],[message('one'),message('two',text=False),*bounds()])
    assert len(links)==2
    assert coverage[0]['telegram_message_count']==2
    assert coverage[0]['telegram_text_message_count']==1
    assert report['linked_message_nonempty_text_share']==0.5


def test_alert_without_messages_and_historical_unavailability():
    old=alert('before',BASE-timedelta(days=3),BASE-timedelta(days=2))
    _,coverage,report=integrate([old,alert()],bounds())
    byid={r['alert_id']:r for r in coverage}
    assert byid['before']['coverage_status']=='no_telegram_historical_coverage'
    assert byid['before']['telegram_message_count'] is None
    assert byid['before']['has_telegram_coverage'] is None
    assert byid['a']['telegram_message_count']==0
    assert byid['a']['has_telegram_coverage'] is False
    assert report['eligible_alerts_for_coverage_rate']==1


def test_adjacent_intervals_one_boundary_link():
    end=BASE+timedelta(hours=1)
    links,_,_=integrate([alert('first'),alert('second',end,end+timedelta(hours=1))],[message(instant=end),*bounds()])
    assert [(r['alert_id'],r['message_id']) for r in links]==[('second','m')]


def test_cross_midnight():
    start=datetime(2024,1,1,23,50,tzinfo=timezone.utc)
    end=start+timedelta(minutes=30)
    links,coverage,_=integrate([alert(start=start,end=end)],[message(instant=start+timedelta(minutes=15))])
    assert len(links)==1 and coverage[0]['has_telegram_coverage']


def test_ambiguous_message_not_assigned_and_affected_alert_flagged():
    a=alert(start=datetime(2025,10,26,0,0,tzinfo=timezone.utc),end=datetime(2025,10,26,0,30,tzinfo=timezone.utc))
    m=message(instant=None,message_time_original='26.10.2025 03:10:00 UTC+02:00',timestamp_status='ambiguous')
    links,coverage,report=integrate([a],[m])
    assert links==[] and coverage[0]['coverage_status']=='unresolved_temporal_ambiguity'
    assert report['excluded_messages'][0]['potential_alert_ids']==['a']
    assert coverage[0]['has_telegram_coverage'] is None


def test_ambiguous_alert_withholds_prefix_and_possible_tail():
    start=datetime(2025,10,25,23,27,tzinfo=timezone.utc)
    a=alert('amb-alert',start,None)
    a.update(start_time_original='2025-10-26T02:27:00',end_time_original='2025-10-26T03:05:12',validation_status='end_ambiguous')
    m1=message('prefix',start+timedelta(minutes=1))
    m2=message('possible-tail',datetime(2025,10,26,0,30,tzinfo=timezone.utc))
    m3=message('upper-boundary',datetime(2025,10,26,1,5,12,tzinfo=timezone.utc))
    links,coverage,report=integrate([a],[m1,m2,m3])
    assert not links
    assert coverage[0]['end_time'] is None and coverage[0]['duration_minutes'] is None
    assert coverage[0]['telegram_message_count'] is None
    assert report['excluded_message_reason_counts']=={'potential_unresolved_alert_interval':2}
    assert report['timestamped_messages_outside_alerts']==1
    assert report['unresolved_alerts'][0]['candidate_end_instants']==[datetime(2025,10,26,0,5,12,tzinfo=timezone.utc),datetime(2025,10,26,1,5,12,tzinfo=timezone.utc)]


def test_untimestamped_service_counted_not_linked():
    links,_,report=integrate([alert()],[message('service',None,service=True),*bounds()])
    assert not links
    assert report['service_message_records']==1
    assert report['excluded_message_reason_counts']['untimestamped_service']==1


def test_duplicate_prevention_and_conflicting_id_rejected():
    row=message()
    links,_,report=integrate([alert()],[row,dict(row),*bounds()])
    assert len(links)==1 and len(report['exact_duplicate_input_occurrences'])==1
    with pytest.raises(ValueError,match='Conflicting duplicate'):
        integrate([alert()],[row,message(text=False)])
    with pytest.raises(ValueError,match='unique'):
        integrate([alert(),alert()],[row])


def test_source_traceability_and_deterministic_order():
    a=[alert('late',BASE+timedelta(hours=2),BASE+timedelta(hours=3)),alert()]
    messages=[message('z',source_message_index=99),message('a',source_message_index=5),*bounds()]
    first=integrate(a,messages)
    second=integrate(list(reversed(a)),list(reversed(messages)))
    assert first[:2]==second[:2]
    assert [r['message_id'] for r in first[0]]==['a','z']
    assert first[0][1]['source_message_index']==99
    assert first[0][0]['source_file']=='synthetic/messages.html'


def test_overlapping_resolved_intervals_flag_review_without_duplicate_pairs():
    links,_,report=integrate([alert('a'),alert('b',BASE+timedelta(minutes=5),BASE+timedelta(minutes=20))],[message(),*bounds()])
    assert len(links)==2 and all(r['match_quality']=='review_overlapping_intervals' for r in links)
    assert len({(r['alert_id'],r['message_id']) for r in links})==2
    assert len(report['review_overlapping_interval_links'])==2


def test_partial_range_does_not_enter_monthly_denominator():
    links,coverage,report=integrate([alert()],[message()])
    assert len(links)==1 and coverage[0]['has_telegram_coverage']
    assert coverage[0]['historical_range_relation']=='partial'
    assert report['monthly_coverage'][0]['coverage_rate'] is None


def test_monthly_coverage_true_zeros_and_unavailable_rates():
    old=alert('old',BASE-timedelta(days=365),BASE-timedelta(days=365)+timedelta(hours=1))
    empty=alert('empty',BASE+timedelta(hours=2),BASE+timedelta(hours=3))
    _,_,report=integrate([old,alert(),empty],[message(),*bounds()])
    months={r['month']:r for r in report['monthly_coverage']}
    assert months['2023-01']['coverage_rate'] is None
    assert months['2024-01']['coverage_rate']==0.5
    assert months['2024-01']['median_messages_per_eligible_alert']==0.5


def test_sweep_matches_independent_small_brute_force_oracle():
    rng=random.Random(123)
    alerts=[alert(str(i),BASE+timedelta(seconds=s),BASE+timedelta(seconds=s+width)) for i in range(30) for s,width in [(rng.randrange(100),rng.randrange(1,30))]]
    messages=[message(str(i),BASE+timedelta(seconds=rng.randrange(140))) for i in range(100)]
    links,_,_=integrate(alerts,messages)
    expected={(a['alert_id'],m['message_id']) for a in alerts for m in messages if a['start_time']<=m['message_time']<a['end_time']}
    assert {(r['alert_id'],r['message_id']) for r in links}==expected


def test_missing_source_id_is_not_invented():
    links,coverage,report=integrate([alert()],[message(None),*bounds()])
    assert not links and coverage[0]['coverage_status']=='unresolved_temporal_ambiguity'
    assert report['excluded_message_reason_counts']['missing_source_message_id']==1


def test_h2_guard_rejects_stale_h1_but_accepts_unresolved_fold():
    row=message(instant=datetime(2024,7,15,10,tzinfo=timezone.utc),message_time_original='15.07.2024 12:00:00 UTC+02:00')
    with pytest.raises(ValueError,match='H2'):
        validate_h2([row])
    row['message_time']=datetime(2024,7,15,9,tzinfo=timezone.utc)
    validate_h2([row])
    validate_h2([message(instant=None,message_time_original='26.10.2025 03:10:00 UTC+02:00',timestamp_status='ambiguous')])


def test_cli_outputs_repeatable_and_inputs_unchanged(tmp_path):
    a,m=tmp_path/'alerts.parquet',tmp_path/'messages.parquet'
    write_table([alert()],a,schema_for('alerts'))
    write_table([message(),*bounds()],m,schema_for('telegram'))
    raw=[a.read_bytes(),m.read_bytes()]
    args=['--alerts',str(a),'--messages',str(m),'--output',str(tmp_path/'out'),'--report',str(tmp_path/'report')]
    assert main(args)==0
    first=pq.read_table(tmp_path/'out/alert_message_links.parquet')
    assert main(args)==0
    assert first.equals(pq.read_table(tmp_path/'out/alert_message_links.parquet'))
    assert raw==[a.read_bytes(),m.read_bytes()]
    assert json.loads((tmp_path/'report/coverage_report.json').read_text())['task_status']=='COMPLETE'


def test_cli_missing_inputs_nonzero_with_blocked_report(tmp_path):
    assert main(['--alerts',str(tmp_path/'missing.parquet'),'--messages',str(tmp_path/'other.parquet'),'--report',str(tmp_path/'report')])==1
    assert json.loads((tmp_path/'report/coverage_report.json').read_text())['task_status']=='BLOCKED'


def test_timestamped_service_can_match_when_metadata_is_available():
    links,coverage,report=integrate([alert()],[message(service=True)])
    assert len(links)==1 and coverage[0]['has_telegram_coverage'] is True
    assert report['service_message_records']==1


def test_unknown_end_is_not_replaced_by_next_alert_or_last_message():
    unknown=alert('unknown',BASE,None)
    known=alert('known',BASE+timedelta(hours=2),BASE+timedelta(hours=3))
    links,coverage,report=integrate([unknown,known],[message(instant=BASE+timedelta(hours=2,minutes=10)),*bounds()])
    assert links==[]
    byid={r['alert_id']:r for r in coverage}
    assert byid['unknown']['end_time'] is None
    assert byid['known']['coverage_status']=='unresolved_temporal_ambiguity'
    assert report['unresolved_alerts'][0]['potential_envelope_end'] is None
