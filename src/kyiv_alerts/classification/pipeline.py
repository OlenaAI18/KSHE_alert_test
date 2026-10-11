"""Evidence-preserving multi-label aggregation and reproducible review sampling."""
from collections import Counter, defaultdict
import json
import random
import statistics
from kyiv_alerts.ingestion.timeutils import KYIV
from .rules import CATEGORIES


def unique_index(rows, key):
    result = {}
    for row in rows:
        identity = row[key]
        if identity is None or identity in result:
            raise ValueError(f'Missing or duplicate {key}: {identity}')
        result[identity] = row
    return result


def process(alerts, messages, links, coverage, dictionary):
    amap = unique_index(alerts,'alert_id')
    cmap = unique_index(coverage,'alert_id')
    mmap = unique_index([r for r in messages if r['message_id'] is not None], 'message_id')
    if set(amap) != set(cmap):
        raise ValueError('Coverage must contain all and only official alerts')
    markers, pairs, linked_by_alert, cache = [], set(), defaultdict(list), {}
    for link in sorted(links,key=lambda r:(r['alert_id'],r['message_id'])):
        pair = link['alert_id'],link['message_id']
        if pair in pairs:
            raise ValueError('Duplicate temporal pair')
        pairs.add(pair)
        a,m = amap[link['alert_id']],mmap[link['message_id']]
        if not (a['start_time'] <= m['message_time'] < a['end_time']):
            raise ValueError('Temporal link violates official half-open interval')
        for field in ['source_file','source_message_index','message_time']:
            if link[field] != m[field]:
                raise ValueError('Link/message provenance mismatch')
        if link['alert_start_time'] != a['start_time'] or link['alert_end_time'] != a['end_time']:
            raise ValueError('Link/alert timestamps mismatch')
        linked_by_alert[a['alert_id']].append(m)
        if m['message_id'] not in cache:
            cache[m['message_id']] = dictionary.classify(m.get('text'))
        for candidate in cache[m['message_id']]:
            marker = dict(candidate,alert_id=a['alert_id'],message_id=m['message_id'],source_file=m['source_file'],source_message_index=m['source_message_index'])
            markers.append(marker)
    evidence = defaultdict(list)
    for marker in markers:
        evidence[marker['alert_id']].append(marker)
    features = []
    for alert in alerts:
        aid = alert['alert_id']
        cov = cmap[aid]
        linked = linked_by_alert[aid]
        text_count = sum(bool(m.get('text') and m['text'].strip()) for m in linked)
        if cov['deterministic_message_count'] != len(linked) or cov['deterministic_text_message_count'] != text_count:
            raise ValueError('Coverage/link counts mismatch')
        for k in ['start_time','end_time','duration_minutes']:
            if cov[k] != alert[k]:
                raise ValueError('Coverage/official alert mismatch')
        accepted = [m for m in evidence[aid] if m['accepted_for_aggregation']]
        categories = [c for c in CATEGORIES[:-1] if any(m['category']==c for m in accepted)]
        unavailable = cov['coverage_status'] in {'no_telegram_historical_coverage','unresolved_temporal_ambiguity','partial_historical_coverage'} or not text_count
        if cov['coverage_status'] == 'unresolved_temporal_ambiguity':
            status = 'unresolved_temporal_ambiguity'
        elif cov['coverage_status'] == 'no_telegram_historical_coverage':
            status = 'no_telegram_historical_coverage'
        elif cov['coverage_status'] == 'partial_historical_coverage':
            status = 'partial_historical_coverage'
        elif not text_count:
            status = 'no_linked_text'
        elif len(categories)>1:
            status = 'multiple_categories'
        elif categories:
            status = 'classified'
        else:
            status = 'no_identifiable_marker'
        row = {k:alert[k] for k in ['alert_id','start_time','end_time','duration_minutes']}
        row.update({k:cov[k] for k in ['coverage_status','historical_range_relation','telegram_message_count','telegram_text_message_count']})
        row.update({c: None if unavailable else c in categories for c in CATEGORIES[:-1]})
        row.update(unknown=not categories or unavailable,threat_combination=None if unavailable else '+'.join(categories) or 'unknown',explicit_cause_categories=None if unavailable else [c for c in CATEGORIES[:-1] if any(m['category']==c and m['evidence_status']=='explicit_alert_cause' for m in accepted)],marker_evidence_count=None if unavailable else len(accepted),candidate_marker_count=len(evidence[aid]),classification_status=status,dictionary_version=dictionary.version)
        row.update(classification_version=dictionary.classification_version,geography_dictionary_version=dictionary.geography_version)
        features.append(row)
    if dictionary.version=='v1.3':
        from .consolidation import consolidate
        consolidate(features,markers,messages)
    features.sort(key=lambda r:(r['start_time'],r['alert_id']))
    markers.sort(key=lambda r:(r['alert_id'],r['message_id'],r['match_start'],r['rule_id']))
    return markers, features


def diagnostics(features, markers, messages, links):
    linked_ids = {l['message_id'] for l in links}
    statuses = Counter(f['classification_status'] for f in features)
    combinations = Counter(f['threat_combination'] for f in features if not f['unknown'])
    monthly = defaultdict(list)
    for f in features:
        monthly[f['start_time'].astimezone(KYIV).strftime('%Y-%m')].append(f)
    published = Counter(m['message_time'].astimezone(KYIV).strftime('%Y-%m') for m in messages if m['message_time'] is not None and not m['is_service_message'])
    months=[]
    for month,rows in sorted(monthly.items()):
        eligible=[f for f in rows if f['historical_range_relation']=='within' and f['coverage_status'] in {'covered','no_messages_found'}]
        text=[f for f in eligible if (f['telegram_text_message_count'] or 0)>0]
        classified=sum(not f['unknown'] for f in eligible)
        counts=[f['telegram_message_count'] for f in eligible]
        months.append(dict(month=month,total_alerts=len(rows),eligible_alerts=len(eligible),alerts_with_text=len(text),classified_alerts=classified,classified_share_of_eligible=classified/len(eligible) if eligible else None,classified_share_of_text_alerts=classified/len(text) if text else None,published_messages=published[month],linked_messages=sum(counts),median_linked_messages_per_eligible_alert=statistics.median(counts) if counts else None,per_category_alert_counts={c:sum(f[c] is True for f in rows) for c in CATEGORIES[:-1]}))
    years=[]
    for year in sorted({m['month'][:4] for m in months}):
        rows=[m for m in months if m['month'].startswith(year)]
        eligible=sum(m['eligible_alerts'] for m in rows)
        years.append(dict(year=year,eligible_alerts=eligible,linked_messages=sum(m['linked_messages'] for m in rows),published_messages=sum(m['published_messages'] for m in rows),mean_linked_messages_per_eligible_alert=sum(m['linked_messages'] for m in rows)/eligible if eligible else None,observed_months_with_eligible_alerts=sum(m['eligible_alerts']>0 for m in rows)))
    examples=[]
    for status in ['uncertain','negated_or_cancelled','historical_or_summary']:
        examples.extend([{k:m[k] for k in ['alert_id','message_id','rule_id','matched_text','evidence_context','evidence_status','geography','exclusion_reason','source_file','source_message_index']} for m in markers if m['evidence_status']==status][:3])
    return dict(publication_density_by_year=years,representative_review_cases=examples,total_processed_alerts=len(features),total_input_messages=len(messages),total_processed_links=len(links),unique_processed_messages=len({l['message_id'] for l in links}),linked_messages_with_text=sum(bool(m['text'] and m['text'].strip()) for m in messages if m['message_id'] in linked_ids),alerts_with_telegram_text=sum((f['telegram_text_message_count'] or 0)>0 for f in features),alerts_with_detected_category=sum(not f['unknown'] for f in features),classification_status_counts=dict(sorted(statuses.items())),per_category_alert_counts={c:sum(f[c] is True for f in features) for c in CATEGORIES[:-1]},single_label_alerts=sum(sum(f[c] is True for c in CATEGORIES[:-1])==1 for f in features),multi_label_alerts=sum(sum(f[c] is True for c in CATEGORIES[:-1])>1 for f in features),unknown_alerts=sum(f['unknown'] for f in features),combination_counts=dict(sorted(combinations.items(),key=lambda kv:(-kv[1],kv[0]))),messages_with_candidate_markers=len({m['message_id'] for m in markers}),messages_with_accepted_markers=len({m['message_id'] for m in markers if m['accepted_for_aggregation']}),candidate_marker_records=len(markers),accepted_marker_records=sum(m['accepted_for_aggregation'] for m in markers),context_counts=dict(Counter(m['evidence_status'] for m in markers)),geography_counts=dict(Counter(m['geography'] for m in markers)),excluded_marker_records=sum(not m['accepted_for_aggregation'] for m in markers),exclusion_reason_counts=dict(Counter(reason for m in markers for reason in (m['exclusion_reason'] or '').split(';') if reason)),monthly_classification_coverage=months)


def review_sample(messages,links,markers,features,seed=20261010,target=180):
    """Round-robin across overlapping strata; unique alert/message examples, no labels."""
    mmap={r['message_id']:r for r in messages if r['message_id'] is not None}
    fmap={r['alert_id']:r for r in features}
    grouped=defaultdict(list)
    for marker in markers:
        grouped[(marker['alert_id'],marker['message_id'])].append(marker)
    examples={}
    pools=defaultdict(list)
    for link in sorted(links,key=lambda r:(r['alert_id'],r['message_id'])):
        pair=link['alert_id'],link['message_id']
        m,f=mmap[pair[1]],fmap[pair[0]]
        evidence=grouped[pair]
        strata={f"year:{m['message_time'].astimezone(KYIV).year}",f"alert_status:{f['classification_status']}", 'volume:low' if (f['telegram_message_count'] or 0)<=3 else 'volume:high' if (f['telegram_message_count'] or 0)>=20 else 'volume:middle'}
        if not evidence:
            strata.add('markers:none')
        for e in evidence:
            strata.update([f"category:{e['category']}",f"context:{e['evidence_status']}",f"geography:{e['geography']}"])
        examples[pair]=dict(alert_id=pair[0],message_id=pair[1],message_time=m['message_time'].isoformat(),original_timestamp=m['message_time_original'],original_text=m['text'] or '',detected_markers=json.dumps([{k:e[k] for k in ['category','subtype','matched_text','rule_id','evidence_status','geography','accepted_for_aggregation','exclusion_reason','geography_mentions','geography_source']} for e in evidence],ensure_ascii=False),rule_ids=';'.join(sorted({e['rule_id'] for e in evidence})),predicted_context=';'.join(sorted({e['evidence_status'] for e in evidence})),predicted_geography=';'.join(sorted({e['geography'] for e in evidence})),threat_combination=f['threat_combination'],source_file=m['source_file'],source_message_index=m['source_message_index'],dictionary_version=f['dictionary_version'],strata=';'.join(sorted(strata)),reviewer_categories='',reviewer_context='',reviewer_geography='',reviewer_kyiv_relevance='',reviewer_notes='')
        for s in sorted(strata):
            pools[s].append(pair)
    rng=random.Random(seed)
    for s in sorted(pools):
        rng.shuffle(pools[s])
    chosen=[]
    used=set()
    while len(chosen)<min(target,len(examples)):
        progress=False
        for s in sorted(pools):
            while pools[s] and pools[s][-1] in used:
                pools[s].pop()
            if pools[s]:
                pair=pools[s].pop()
                chosen.append(examples[pair]);used.add(pair);progress=True
                if len(chosen)==min(target,len(examples)):
                    break
        if not progress:
            break
    return chosen
