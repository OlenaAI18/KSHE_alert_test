"""Auditable half-open interval matching with unresolved times kept separate."""
from collections import Counter, defaultdict
from datetime import datetime
import heapq
import json
from statistics import median
from kyiv_alerts.ingestion.timeutils import KYIV, UTC


def possible_instants(original):
    """Enumerate valid Kyiv-local folds solely to bound uncertainty, never impute."""
    if not isinstance(original, str):
        return []
    value = original.split(' UTC')[0]
    try:
        try:
            local = datetime.fromisoformat(value)
        except ValueError:
            local = datetime.strptime(value, '%d.%m.%Y %H:%M:%S')
        if local.tzinfo is not None:
            return [local.astimezone(UTC)]
        return sorted({local.replace(tzinfo=KYIV, fold=fold).astimezone(UTC)
                       for fold in [0, 1]
                       if local.replace(tzinfo=KYIV, fold=fold).astimezone(UTC)
                       .astimezone(KYIV).replace(tzinfo=None) == local})
    except (ValueError, OverflowError):
        return []


def sweep(intervals, points):
    """O((intervals + points) log intervals + matches), including overlaps.

    None bounds mean uncertainty extending beyond a known endpoint; these are
    internal potential envelopes, never substituted into normalized datasets.
    """
    starts = sorted(intervals, key=lambda x: (x[0] is not None, x[0] or datetime.min.replace(tzinfo=UTC), x[2]))
    active, endings, cursor = {}, [], 0
    result = {}
    for instant, point_id in sorted(points, key=lambda p: (p[0], p[1])):
        while cursor < len(starts) and (starts[cursor][0] is None or starts[cursor][0] <= instant):
            start, end, interval_id = starts[cursor]
            active[interval_id] = (start, end)
            if end is not None:
                heapq.heappush(endings, (end, interval_id))
            cursor += 1
        while endings and endings[0][0] <= instant:
            _, interval_id = heapq.heappop(endings)
            active.pop(interval_id, None)
        result[point_id] = sorted(active)
    return result


def fingerprint(row):
    return json.dumps(row, sort_keys=True, ensure_ascii=False,
                      default=lambda v: v.isoformat() if isinstance(v, datetime) else str(v))


def message_ref(row, reason, alerts=()):
    return {'message_id': row.get('message_id'), 'source_file': row.get('source_file'),
            'source_message_index': row.get('source_message_index'),
            'message_time_original': row.get('message_time_original'),
            'reason': reason, 'potential_alert_ids': sorted(set(alerts))}


def integrate(alerts, messages):
    """Return links, one coverage row per alert, and descriptive audit evidence."""
    ids = [a.get('alert_id') for a in alerts]
    if any(not x for x in ids) or len(set(ids)) != len(ids):
        raise ValueError('Official alert IDs must be present and unique')
    for row in alerts:
        for key in ['start_time', 'end_time']:
            value = row.get(key)
            if value is not None and (not isinstance(value, datetime) or value.utcoffset() is None):
                raise ValueError('Alert timestamps must be timezone-aware or null')
    unique, seen, duplicate_occurrences = [], {}, []
    for row in messages:
        value = row.get('message_time')
        if value is not None and (not isinstance(value, datetime) or value.utcoffset() is None):
            raise ValueError('Message timestamps must be timezone-aware or null')
        mid = row.get('message_id')
        if mid is not None and mid in seen:
            if fingerprint(row) != seen[mid]:
                raise ValueError(f'Conflicting duplicate message ID: {mid}')
            duplicate_occurrences.append(message_ref(row, 'exact_duplicate_input_occurrence'))
            continue
        if mid is not None:
            seen[mid] = fingerprint(row)
        unique.append(row)

    # Historical availability is a recorded date span, not continuous reporting.
    observed = [r['message_time'] for r in unique if r.get('message_time') is not None]
    first, last = (min(observed), max(observed)) if observed else (None, None)
    resolved, uncertain, invalid, envelopes = [], {}, [], []
    for i, a in enumerate(alerts):
        start, end = a.get('start_time'), a.get('end_time')
        if start is not None and end is not None and end > start:
            resolved.append((start, end, i))
        else:
            reasons = a.get('validation_status') or 'unresolved_or_invalid_interval'
            uncertain[i] = {'alert_id': a['alert_id'], 'reason': reasons,
                            'source_record_index': a.get('source_record_index'),
                            'start_time_original': a.get('start_time_original'),
                            'end_time_original': a.get('end_time_original')}
            if start is not None and end is not None and end <= start:
                invalid.append(a['alert_id'])
                continue
            starts = [start] if start is not None else possible_instants(a.get('start_time_original'))
            ends = [end] if end is not None else possible_instants(a.get('end_time_original'))
            lower, upper = (min(starts) if starts else None), (max(ends) if ends else None)
            if lower is not None and upper is not None and upper <= lower:
                continue
            envelopes.append((lower, upper, i))
            uncertain[i]['potential_envelope_start'] = lower
            uncertain[i]['potential_envelope_end'] = upper
            uncertain[i]['candidate_end_instants'] = ends

    points = [(r['message_time'], i) for i, r in enumerate(unique) if r.get('message_time') is not None]
    matches = sweep(resolved, points)
    unresolved_matches = sweep(envelopes, points)
    candidate_points, candidate_to_message = [], {}
    for i, row in enumerate(unique):
        if row.get('message_time') is None and row.get('timestamp_status') == 'ambiguous':
            for instant in possible_instants(row.get('message_time_original')):
                point_id = len(candidate_points)
                candidate_points.append((instant, point_id))
                candidate_to_message[point_id] = i
    potential = sweep(resolved + envelopes, candidate_points)
    ambiguous_by_message = defaultdict(set)
    affected_alerts = set(uncertain)
    for point_id, aindices in potential.items():
        ambiguous_by_message[candidate_to_message[point_id]].update(aindices)
        affected_alerts.update(aindices)

    links, exclusions, outside, review_overlaps = [], [], [], []
    counts, text_counts = Counter(), Counter()
    for i, row in enumerate(unique):
        mid, instant = row.get('message_id'), row.get('message_time')
        if instant is None:
            reason = ('ambiguous_timestamp' if row.get('timestamp_status') == 'ambiguous'
                      else 'untimestamped_service' if row.get('is_service_message', False)
                      else 'invalid_or_missing_timestamp')
            exclusions.append(message_ref(row, reason, [alerts[j]['alert_id'] for j in ambiguous_by_message[i]]))
            continue
        if not mid:
            exclusions.append(message_ref(row, 'missing_source_message_id'))
            affected_alerts.update(matches.get(i, []))
            continue
        if unresolved_matches.get(i):
            aindices = unresolved_matches[i]
            # Conservatively withhold the entire uncertain interval, including its
            # definitely-before-both-ends prefix, rather than publish a null-end link.
            affected_alerts.update(matches.get(i, []))
            exclusions.append(message_ref(row, 'potential_unresolved_alert_interval', [alerts[j]['alert_id'] for j in aindices]))
            continue
        aindices = matches.get(i, [])
        if not aindices:
            outside.append(message_ref(row, 'outside_official_intervals'))
            continue
        for j in aindices:
            a = alerts[j]
            quality = 'deterministic' if len(aindices) == 1 else 'review_overlapping_intervals'
            links.append({'alert_id': a['alert_id'], 'message_id': mid, 'message_time': instant,
                          'alert_start_time': a['start_time'], 'alert_end_time': a['end_time'],
                          'match_method': 'within_official_interval', 'match_quality': quality,
                          'source_file': row.get('source_file'),
                          'source_message_index': row.get('source_message_index')})
            counts[j] += 1
            text_counts[j] += bool(row.get('has_text'))
            if quality != 'deterministic':
                review_overlaps.append({'alert_id': a['alert_id'], 'message_id': mid})
    links.sort(key=lambda r: (r['alert_start_time'], r['alert_id'], r['message_time'], r['message_id'], r['source_file'] or '', r['source_message_index'] or 0))
    coverage = []
    for j, a in enumerate(alerts):
        start, end = a.get('start_time'), a.get('end_time')
        relation = 'unknown'
        range_start, range_end = start, end
        if j in uncertain and 'potential_envelope_start' in uncertain[j]:
            range_start = uncertain[j]['potential_envelope_start']
            range_end = uncertain[j]['potential_envelope_end']
        if first is not None and range_start is not None and range_end is not None and range_end > range_start:
            relation = ('outside' if range_end <= first or range_start > last else
                        'within' if range_start >= first and range_end <= last else 'partial')
        if j in affected_alerts:
            status, has_coverage = 'unresolved_temporal_ambiguity', True if counts[j] else None
            count, text_count = None, None
        elif relation == 'outside' or first is None:
            status, has_coverage = 'no_telegram_historical_coverage', None
            count, text_count = None, None
        elif relation == 'partial':
            status = 'covered' if counts[j] else 'partial_historical_coverage'
            has_coverage = True if counts[j] else None
            count, text_count = counts[j], text_counts[j]
        elif counts[j]:
            status, has_coverage = 'covered', True
            count, text_count = counts[j], text_counts[j]
        else:
            status, has_coverage = 'no_messages_found', False
            count, text_count = 0, 0
        coverage.append({'alert_id': a['alert_id'], 'start_time': start, 'end_time': end,
                         'duration_minutes': a.get('duration_minutes'),
                         'telegram_message_count': count, 'telegram_text_message_count': text_count,
                         'has_telegram_coverage': has_coverage, 'coverage_status': status,
                         'historical_range_relation': relation,
                         'deterministic_message_count': counts[j],
                         'deterministic_text_message_count': text_counts[j]})
    coverage.sort(key=lambda r: (r['start_time'] is None, r['start_time'] or datetime.max.replace(tzinfo=UTC), r['alert_id']))
    monthly = defaultdict(list)
    for row in coverage:
        key = row['start_time'].astimezone(KYIV).strftime('%Y-%m') if row['start_time'] else 'unknown'
        monthly[key].append(row)
    monthly_report = []
    for month, group in sorted(monthly.items()):
        eligible = [r for r in group if r['coverage_status'] in {'covered','no_messages_found'} and r['historical_range_relation']=='within']
        covered = [r for r in eligible if r['coverage_status']=='covered']
        monthly_report.append({'month': month, 'total_alerts': len(group),
                               'eligible_fully_observed_resolved_alerts': len(eligible),
                               'covered_alerts': len(covered),
                               'coverage_rate': len(covered)/len(eligible) if eligible else None,
                               'median_messages_per_eligible_alert': median(r['telegram_message_count'] for r in eligible) if eligible else None,
                               'median_messages_per_covered_alert': median(r['telegram_message_count'] for r in covered) if covered else None,
                               'status_counts': dict(Counter(r['coverage_status'] for r in group))})
    linked_ids = {r['message_id'] for r in links}
    linked_text = sum(bool(r.get('has_text')) for r in unique if r.get('message_id') in linked_ids)
    eligible = [r for r in coverage if r['coverage_status'] in {'covered','no_messages_found'} and r['historical_range_relation']=='within']
    statuses = dict(Counter(r['coverage_status'] for r in coverage))
    report = {
        'task_status': 'COMPLETE', 'rule': 'start <= message_time < end',
        'telegram_historical_range': {'first': first, 'last': last},
        'total_official_alerts': len(alerts), 'total_input_message_records': len(messages),
        'unique_input_message_records': len(unique),
        'timestamped_message_records': len(points),
        'ordinary_message_records': sum(not r.get('is_service_message',False) for r in unique),
        'service_message_records': sum(r.get('is_service_message',False) for r in unique),
        'alerts_with_known_full_range_containment': sum(r['historical_range_relation']=='within' for r in coverage),
        'alerts_with_known_range_intersection': sum(r['historical_range_relation'] in {'within','partial'} for r in coverage),
        'eligible_alerts_for_coverage_rate': len(eligible),
        'overall_coverage_rate': sum(r['coverage_status']=='covered' for r in eligible)/len(eligible) if eligible else None,
        'alerts_with_at_least_one_link': sum(r['deterministic_message_count']>0 for r in coverage),
        'alerts_without_linked_messages': sum(r['deterministic_message_count']==0 for r in coverage),
        'coverage_status_counts': statuses,
        'total_temporal_links': len(links), 'total_linked_messages': len(linked_ids),
        'timestamped_messages_outside_alerts': len(outside),
        'linked_messages_with_nonempty_text': linked_text,
        'linked_message_nonempty_text_share': linked_text/len(linked_ids) if linked_ids else None,
        'median_messages_per_covered_alert': median(r['telegram_message_count'] for r in eligible if r['coverage_status']=='covered') if any(r['coverage_status']=='covered' for r in eligible) else None,
        'monthly_coverage': monthly_report,
        'unresolved_alerts': list(uncertain.values()), 'affected_alert_ids': sorted(alerts[j]['alert_id'] for j in affected_alerts),
        'excluded_messages': exclusions, 'excluded_message_reason_counts': dict(Counter(r['reason'] for r in exclusions)),
        'exact_duplicate_input_occurrences': duplicate_occurrences,
        'review_overlapping_interval_links': review_overlaps,
        'invalid_interval_alert_ids': invalid,
    }
    return links, coverage, report
