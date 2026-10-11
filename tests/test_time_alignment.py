"""Regression checks for the empirically validated source-specific interpretation."""
from datetime import datetime, timezone
import pytest
from kyiv_alerts.ingestion.timeutils import parse_time, parse_telegram_time
from kyiv_alerts.validation.time_alignment import compare_example, summarize, dst_interval_candidates


@pytest.mark.parametrize(('original','expected','status'),[
    ('15.01.2024 12:00:00 UTC+02:00','2024-01-15T10:00:00+00:00','valid_kyiv_wall_clock'),
    ('15.07.2024 12:00:00 UTC+02:00','2024-07-15T09:00:00+00:00','valid_kyiv_wall_clock'),
    ('31.03.2024 02:59:59 UTC+02:00','2024-03-31T00:59:59+00:00','valid_kyiv_wall_clock'),
    ('31.03.2024 03:30:00 UTC+02:00',None,'nonexistent'),
    ('31.03.2024 04:00:00 UTC+02:00','2024-03-31T01:00:00+00:00','valid_kyiv_wall_clock'),
    ('27.10.2024 02:59:59 UTC+02:00','2024-10-26T23:59:59+00:00','valid_kyiv_wall_clock'),
    ('27.10.2024 03:30:00 UTC+02:00',None,'ambiguous'),
    ('27.10.2024 04:00:00 UTC+02:00','2024-10-27T02:00:00+00:00','valid_kyiv_wall_clock'),
    ('26.10.2025 03:05:19 UTC+02:00',None,'ambiguous'),
    ('29.03.2026 03:30:00 UTC+02:00',None,'nonexistent'),
    ('2024-07-15T12:00:00+02:00','2024-07-15T10:00:00+00:00','valid_explicit_offset'),
    ('15.07.2024 12:00:00 UTC+03:00','2024-07-15T09:00:00+00:00','valid_explicit_offset'),
])
def test_validated_clock_and_dst_boundaries(original,expected,status):
    timestamp,actual=parse_telegram_time(original)
    assert actual==status
    assert (timestamp.isoformat() if timestamp else None)==expected


def test_hypotheses_use_same_boundary_and_signed_delay():
    message={'message_id':'synthetic','message_time_original':'15.07.2024 12:01:00 UTC+02:00','text':'Synthetic Kyiv start announcement','source_file':'fixture.html','source_message_index':0}
    alert={'alert_id':'synthetic-alert','start_time_original':'2024-07-15T12:00:00'}
    result=compare_example(message,alert,'start')
    assert result['h1_signed_difference_seconds']==3660
    assert result['h2_signed_difference_seconds']==60
    assert result['alert_id']=='synthetic-alert'
    summary=summarize([result])
    assert summary['daylight_time']['h1']['matching_counts']['300']==0
    assert summary['daylight_time']['h2']['matching_counts']['300']==1


def test_unresolved_comparison_cannot_silently_select_fold():
    message={'message_time_original':'26.10.2025 03:05:19 UTC+02:00'}
    alert={'end_time_original':'2025-10-26T03:05:12'}
    with pytest.raises(ValueError,match='Unresolved'):
        compare_example(message,alert,'end')


def test_dst_alert_has_two_admissible_ends_without_correction():
    alert={'start_time_original':'2025-10-26T02:27:00','end_time_original':'2025-10-26T03:05:12'}
    original=dict(alert)
    candidates=dst_interval_candidates(alert)
    assert [r['utc_end'] for r in candidates]==['2025-10-26T00:05:12+00:00','2025-10-26T01:05:12+00:00']
    assert [r['duration_minutes'] for r in candidates]==[38.2,98.2]
    assert parse_time(alert['end_time_original'])==(None,'ambiguous')
    assert alert==original
