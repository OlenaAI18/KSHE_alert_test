"""Descriptive integrity auditing, not research analysis or temporal linking."""
from collections import Counter
from datetime import timedelta
import re
import json
from kyiv_alerts.ingestion.timeutils import KYIV

# Diagnostic flags, not exclusion rules or statistical conclusions.
SHORT_MINUTES = 1
LONG_MINUTES = 24 * 60
ALERT_GAP_HOURS = 7 * 24
POSTING_GAP_HOURS = 24


def duplicate_counts(values):
    return {str(k): v for k, v in Counter(values).items() if k is not None and v > 1}


def completeness(rows, time_key):
    times = [r[time_key] for r in rows if r[time_key] is not None]
    monthly = Counter(t.astimezone(KYIV).strftime('%Y-%m') for t in times)
    if times:
        first, last = min(times).astimezone(KYIV), max(times).astimezone(KYIV)
        year, month = first.year, first.month
        while (year, month) <= (last.year, last.month):
            monthly.setdefault(f'{year:04d}-{month:02d}', 0)
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return {
        'total_extracted_records': len(rows), 'records_with_valid_timestamps': len(times),
        'date_parsing_success_rate': len(times) / len(rows) if rows else None,
        'earliest_timestamp': min(times) if times else None,
        'latest_timestamp': max(times) if times else None,
        'monthly_record_counts': dict(sorted(monthly.items())),
        'missing_or_null_fields': {k: sum(r.get(k) is None or r.get(k) == '' for r in rows)
                                  for k in rows[0]} if rows else {},
        'timestamp_ordering_in_source': all(a <= b for a, b in zip(times, times[1:])),
        'timestamp_ordering_comparable_records': len(times),
    }


def audit_alerts(rows):
    result = completeness(rows, 'start_time')
    result['records_with_valid_start_and_end'] = sum(r['start_time'] is not None and r['end_time'] is not None for r in rows)
    ends = [r['end_time'] for r in rows if r['end_time'] is not None]
    starts = [r['start_time'] for r in rows if r['start_time'] is not None]
    result['latest_interval_boundary'] = max(ends + starts) if ends or starts else None
    result['end_date_parsing_success_rate'] = sum(r['end_time'] is not None for r in rows) / len(rows) if rows else None
    raw_records = [json.loads(r['raw_record_json']) for r in rows]
    raw_keys = sorted({key for r in raw_records if isinstance(r,dict) for key in r})
    result['source_missing_or_null_fields'] = {key: sum(not isinstance(r,dict) or r.get(key) is None or r.get(key) == 'null' for r in raw_records) for key in raw_keys}
    result['records_without_text'] = None  # Not applicable to structured intervals.
    result['duplicate_identifiers'] = duplicate_counts(r['alert_id'] for r in rows)
    result['duplicate_records'] = duplicate_counts(r['raw_record_json'] for r in rows)
    result['duplicate_intervals'] = duplicate_counts(json.dumps([r['start_time_original'], r['end_time_original']],ensure_ascii=False,sort_keys=True) for r in rows)
    result['timestamp_status_counts'] = {
        k: dict(Counter(r[k] for r in rows)) for k in ['start_timestamp_status', 'end_timestamp_status']}
    result['invalid_timestamps'] = sum('invalid' in (r['start_timestamp_status'], r['end_timestamp_status']) for r in rows)
    result['dst_ambiguous_records'] = [r['source_record_index'] for r in rows if 'ambiguous' in (r['start_timestamp_status'], r['end_timestamp_status'])]
    result['dst_nonexistent_records'] = [r['source_record_index'] for r in rows if 'nonexistent' in (r['start_timestamp_status'], r['end_timestamp_status'])]
    result['end_before_start_records'] = [r['source_record_index'] for r in rows if r['start_time'] is not None and r['end_time'] is not None and r['end_time'] < r['start_time']]
    result['zero_duration_records'] = [r['source_record_index'] for r in rows if r['start_time'] is not None and r['end_time'] == r['start_time']]
    result['unexpected_geographic_records'] = [r['source_record_index'] for r in rows if 'unexpected_geography' in r['validation_status']]
    result['unusually_short_duration_records'] = [r['source_record_index'] for r in rows if r['duration_minutes'] is not None and r['duration_minutes'] < SHORT_MINUTES]
    result['unusually_long_duration_records'] = [r['source_record_index'] for r in rows if r['duration_minutes'] is not None and r['duration_minutes'] > LONG_MINUTES]
    result['flagged_records'] = [{'source_record_index': r['source_record_index'], 'alert_id': r['alert_id'], 'status': r['validation_status']} for r in rows if r['validation_status'] != 'valid']
    valid = sorted([r for r in rows if r['duration_minutes'] is not None], key=lambda r: (r['start_time'], r['source_record_index']))
    overlaps, gaps, active = [], [], []
    previous_end = None
    for r in valid:
        active = [a for a in active if a['end_time'] > r['start_time']]
        for a in active:
            overlaps.append({'first_source_record_index': a['source_record_index'], 'second_source_record_index': r['source_record_index']})
        if previous_end is not None and r['start_time'] - previous_end > timedelta(hours=ALERT_GAP_HOURS):
            gaps.append({'previous_end': previous_end, 'next_start': r['start_time'], 'gap_hours': (r['start_time'] - previous_end).total_seconds() / 3600})
        previous_end = max(previous_end, r['end_time']) if previous_end else r['end_time']
        active.append(r)
    result['overlapping_interval_pairs'] = overlaps
    result['suspicious_gaps'] = gaps
    result['parse_errors'] = sum('invalid_record_structure' in r['validation_status'] for r in rows)
    result['skipped_records'] = 0
    return result


def audit_telegram(rows, metadata):
    result = completeness(rows, 'message_time')
    result['records_without_text'] = sum(not r['has_text'] for r in rows)
    result['service_messages'] = sum(r['is_service_message'] for r in rows)
    ordinary = [r for r in rows if not r['is_service_message']]
    result['ordinary_messages'] = len(ordinary)
    result['ordinary_messages_with_valid_timestamps'] = sum(r['message_time'] is not None for r in ordinary)
    result['ordinary_message_date_parsing_success_rate'] = sum(r['message_time'] is not None for r in ordinary) / len(ordinary) if ordinary else None
    result['ordinary_messages_without_text'] = sum(not r['has_text'] for r in ordinary)
    result['service_messages_without_timestamps'] = sum(r['is_service_message'] and r['message_time'] is None for r in rows)
    result['export_service_heading_records'] = sum(r['source_html_id'] is not None and r['source_html_id'].startswith('message-') for r in rows)
    offsets, different, unresolved = Counter(), 0, 0
    for r in rows:
        original = r['message_time_original']
        match = re.search(r'UTC([+-])(\d{2}):(\d{2})$', original or '')
        if match:
            minutes = (int(match.group(2)) * 60 + int(match.group(3))) * (1 if match.group(1) == '+' else -1)
            offsets[minutes] += 1
            if r['message_time'] is None:
                unresolved += 1
            else:
                different += minutes != r['message_time'].astimezone(KYIV).utcoffset().total_seconds() / 60
    result['explicit_export_offset_minutes_counts'] = dict(sorted(offsets.items()))
    result['export_offsets_differing_from_kyiv_zone_records'] = different
    result['export_offset_comparison_unresolved_records'] = unresolved
    result['offset_interpretation'] = 'Task 002.1 validated H2: fixed +02:00 Telegram titles encode Kyiv wall clocks. Original suffixes are preserved; UTC normalization uses Europe/Kyiv DST. Ambiguous/nonexistent times remain unresolved.' 
    result['timestamp_status_counts'] = dict(Counter(r['timestamp_status'] for r in rows))
    result['invalid_timestamps'] = sum(r['timestamp_status'] == 'invalid' for r in rows)
    result['dst_ambiguous_records'] = [{'source_file': r['source_file'], 'source_message_index': r['source_message_index']} for r in rows if r['timestamp_status'] == 'ambiguous']
    result['dst_nonexistent_records'] = [{'source_file': r['source_file'], 'source_message_index': r['source_message_index']} for r in rows if r['timestamp_status'] == 'nonexistent']
    result['missing_identifiers'] = sum(r['message_id'] is None for r in rows)
    result['flagged_records'] = [{k:r[k] for k in ['message_id','source_file','source_message_index','parse_status']} for r in rows if r['parse_status'] != 'valid']
    result['duplicate_identifiers'] = dict(Counter(d['message_id'] for d in metadata['duplicate_identifier_occurrences']))
    result['duplicate_records'] = sum(not d['conflicting_content'] for d in metadata['duplicate_identifier_occurrences'])
    times = sorted({r['message_time'] for r in rows if r['message_time'] is not None})
    result['large_posting_gaps'] = [{'previous_time': a, 'next_time': b, 'gap_hours': (b-a).total_seconds()/3600} for a,b in zip(times,times[1:]) if b-a > timedelta(hours=POSTING_GAP_HOURS)]
    result['parse_errors'] = metadata['html_parse_errors']
    result['skipped_duplicate_records'] = len(metadata['duplicate_identifier_occurrences'])
    result['skipped_unsafe_html_members'] = metadata['unsafe_html_members_skipped']
    result['skipped_records_in_unreadable_members'] = None if any('error' in e for e in metadata['html_parse_errors']) else 0
    return result


def json_default(value):
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    raise TypeError(type(value).__name__)


def markdown_report(report):
    lines = ['# Data Quality Report', '', f"Task status: **{report['task_status']}**", '',
             'Descriptive input audit only. Posting frequency is not attack frequency; gaps do not establish absence of threats.', '',
             'Thresholds are diagnostic flags, not data corrections: durations <1 minute or >24 hours; alert gaps >7 days; Telegram posting gaps >24 hours.', '']
    for name in ['alerts', 'telegram']:
        source = report['sources'][name]
        lines += [f'## {name}', '', f"Processing status: {source['processing_status']}", '']
        if source.get('error'):
            lines += [f"Error: {source['error']}", '']
        if 'quality' not in source:
            continue
        q = source['quality']
        for k in ['total_extracted_records','records_with_valid_timestamps','ordinary_messages','ordinary_messages_with_valid_timestamps','ordinary_message_date_parsing_success_rate','ordinary_messages_without_text','service_messages_without_timestamps','export_service_heading_records','explicit_export_offset_minutes_counts','export_offsets_differing_from_kyiv_zone_records','export_offset_comparison_unresolved_records','offset_interpretation','records_with_valid_start_and_end','latest_interval_boundary','records_without_text','earliest_timestamp','latest_timestamp','date_parsing_success_rate','invalid_timestamps','timestamp_ordering_in_source','missing_identifiers','parse_errors','skipped_records']:
            if k in q:
                lines.append(f'- {k}: {q[k]}')
        for k in ['duplicate_identifiers','duplicate_records','duplicate_intervals','overlapping_interval_pairs','end_before_start_records','zero_duration_records','dst_ambiguous_records','dst_nonexistent_records','unusually_short_duration_records','unusually_long_duration_records','suspicious_gaps','large_posting_gaps','unexpected_geographic_records','flagged_records','skipped_duplicate_records','service_messages']:
            if k in q:
                value=q[k]
                lines.append(f'- {k}: {len(value) if isinstance(value,(list,dict)) else value}')
        lines += ['', '### Monthly counts (Europe/Kyiv)', '', '| Month | Records |', '| --- | ---: |']
        lines += [f'| {month} | {count} |' for month,count in q['monthly_record_counts'].items()]
        lines += ['', '### Missing/null fields', '', '| Field | Records |', '| --- | ---: |']
        lines += [f'| {field} | {count} |' for field,count in q['missing_or_null_fields'].items()]
        if 'source_missing_or_null_fields' in q:
            lines += ['', '### Original source missing/null fields', '', '| Field | Records |', '| --- | ---: |']
            lines += [f'| {field} | {count} |' for field,count in q['source_missing_or_null_fields'].items()]
        lines += ['', f"Elapsed seconds: {source.get('elapsed_seconds')}", '', 'Measured stage seconds: ' + json.dumps(source.get('stage_seconds',{})), '']
    lines += ['## Cross-source coverage', '', json.dumps(report['coverage_intersection'], default=json_default), '',
              '## Limitations', '', 'DST-ambiguous/nonexistent local times remain null in UTC with original values preserved. For the inspected fixed-+02:00 Telegram HTML titles, Task 002.1 validated Kyiv wall-clock normalization (H2); original titles remain intact. Other explicit offsets retain their interpretation. No automatic interval correction, classification, production linking, or statistical analysis was performed. Telegram continuation records are not assigned guessed timestamps. Detailed flagged source references and duplicate occurrences are in the JSON report.', '']
    return '\n'.join(lines)
