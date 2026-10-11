"""Kyiv Digital JSON ingestion; source rows are retained without corrections."""
import json
from pathlib import Path
from .timeutils import null, parse_time, valid_status

EXPECTED_REGION = 'UA80000000000093317'


def parse_alerts(path: Path):
    source = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(source, list):
        raise ValueError('Kyiv Digital input must be a JSON array')
    rows = []
    for index, item in enumerate(source):
        issues = []
        raw = item if isinstance(item, dict) else {}
        if not isinstance(item, dict):
            issues.append('invalid_record_structure')
        start, start_status = parse_time(raw.get('dateTimeStart'))
        end, end_status = parse_time(raw.get('dateTimeEnd'))
        for name, status in [('start', start_status), ('end', end_status)]:
            if not valid_status(status):
                issues.append(f'{name}_{status}')
        uid = null(raw.get('uid'))
        uid = None if uid is None else str(uid)
        if not uid:
            issues.append('missing_identifier')
        region = null(raw.get('CATUTTC'))
        if region != EXPECTED_REGION:
            issues.append('unexpected_geography')
        duration = None
        if start is not None and end is not None:
            if end <= start:
                issues.append('end_not_after_start')
            else:
                duration = (end - start).total_seconds() / 60
        rows.append({
            'alert_id': uid, 'source_uid': uid, 'source_region_code': region,
            'source_region_name': null(raw.get('addressPostName')),
            'alert_type': null(raw.get('type')), 'source_cause': null(raw.get('cause')),
            'start_time_original': raw.get('dateTimeStart'),
            'end_time_original': raw.get('dateTimeEnd'),
            'start_time': start, 'end_time': end, 'duration_minutes': duration,
            'validation_status': ';'.join(issues) or 'valid',
            'start_timestamp_status': start_status, 'end_timestamp_status': end_status,
            'source_file': path.name, 'source_record_index': index,
            'raw_record_json': json.dumps(item, ensure_ascii=False, sort_keys=True),
        })
    return rows
