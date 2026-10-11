"""Task 002.1 fixed-example verification; not a dataset linking algorithm."""
from datetime import datetime
from statistics import median
from kyiv_alerts.ingestion.timeutils import KYIV, parse_time


def compare_example(message, alert, event):
    """Compare both readings against exactly the same reviewed official event."""
    if event not in {'start', 'end'}:
        raise ValueError('Expected a reviewed start or end event')
    original = message['message_time_original']
    h1, status1 = parse_time(original)
    h2, status2 = parse_time(original.rsplit(' UTC', 1)[0])
    boundary, boundary_status = parse_time(alert[event + '_time_original'])
    if any(t is None for t in [h1, h2, boundary]):
        raise ValueError(f'Unresolved sample timestamp: {status1}, {status2}, {boundary_status}')
    return {
        'message_id': message['message_id'], 'original_timestamp': original,
        'source_file': message['source_file'],
        'source_message_index': message['source_message_index'],
        'text_excerpt': (message['text'] or '').split('\n\n')[0].strip(),
        'alert_id': alert['alert_id'], 'event': event,
        'official_timestamp_original': alert[event + '_time_original'],
        'official_time_utc': boundary.isoformat(),
        'h1_time_utc': h1.isoformat(), 'h2_time_utc': h2.isoformat(),
        'h1_signed_difference_seconds': (h1 - boundary).total_seconds(),
        'h2_signed_difference_seconds': (h2 - boundary).total_seconds(),
        'season': 'daylight_time' if h2.astimezone(KYIV).utcoffset().total_seconds() == 10800 else 'standard_time',
    }


def summarize(examples):
    summaries = {}
    for group in ['all', 'standard_time', 'daylight_time']:
        subset = [r for r in examples if group == 'all' or r['season'] == group]
        if not subset:
            continue
        summary = {'n': len(subset)}
        for hypothesis in ['h1', 'h2']:
            values = [r[hypothesis + '_signed_difference_seconds'] for r in subset]
            summary[hypothesis] = {
                'median_signed_seconds': median(values),
                'median_absolute_seconds': median(abs(v) for v in values),
                'max_absolute_seconds': max(abs(v) for v in values),
                'matching_counts': {str(limit): sum(abs(v) <= limit for v in values)
                                    for limit in [60, 180, 300, 600]},
                'matching_rates': {str(limit): sum(abs(v) <= limit for v in values) / len(values)
                                   for limit in [60, 180, 300, 600]},
            }
        summaries[group] = summary
    return summaries


def dst_interval_candidates(alert):
    """Enumerate candidate folds without choosing or filling source timestamps."""
    start, _ = parse_time(alert['start_time_original'])
    end = datetime.fromisoformat(alert['end_time_original'])
    candidates = []
    for fold in [0, 1]:
        localized = end.replace(tzinfo=KYIV, fold=fold)
        utc, _ = parse_time(localized.isoformat())
        candidates.append({'fold': fold, 'local_end': localized.isoformat(),
                           'utc_end': utc.isoformat(),
                           'duration_minutes': (utc - start).total_seconds() / 60})
    return candidates
