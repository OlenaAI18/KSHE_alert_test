"""One-alert consolidation, source-message support and exact coverage audit.

No temporal linking or contextual interpretation occurs in this module.
"""
from collections import Counter, defaultdict
import random
import statistics
from .rules import CATEGORIES
from kyiv_alerts.ingestion.timeutils import KYIV

SPECIFIC=CATEGORIES[:-2]
STATES=('single_type','multiple_types','only_other','no_marker_with_text','no_linked_text','outside_telegram_coverage','unresolved')


def classification_state(feature):
    previous=feature.get('legacy_classification_status',feature['classification_status'])
    if previous=='unresolved_temporal_ambiguity':return 'unresolved'
    if previous in {'no_telegram_historical_coverage','partial_historical_coverage'}:return 'outside_telegram_coverage'
    if previous=='no_linked_text':return 'no_linked_text'
    count=sum(feature[c] is True for c in SPECIFIC)
    if count>=2:return 'multiple_types'
    if count==1:return 'single_type'
    if feature['other'] is True:return 'only_other'
    return 'no_marker_with_text'


def consolidate(features,markers,messages):
    """Add v1.3 columns without changing source/coverage or category evidence."""
    mmap={m['message_id']:m for m in messages if m['message_id'] is not None}
    accepted=defaultdict(list)
    for marker in markers:
        if marker['accepted_for_aggregation']:accepted[marker['alert_id']].append(marker)
    def chronological(mid):
        m=mmap[mid]
        return m['message_time'],m['source_file'],m['source_message_index'],mid
    for f in features:
        f['legacy_classification_status']=f['classification_status']
        f['classification_status']=classification_state(f)
        unavailable=all(f[c] is None for c in CATEGORIES[:-1])
        categories=[c for c in CATEGORIES[:-1] if f[c] is True]
        rows=accepted[f['alert_id']]
        mids=sorted({m['message_id'] for m in rows},key=chronological)
        bycategory=[]
        for c in categories:
            matched=[m for m in rows if m['category']==c]
            ids=sorted({m['message_id'] for m in matched},key=chronological)
            bycategory.append(dict(category=c,first_message_id=ids[0],message_ids=ids,supporting_message_count=len(ids),
                supporting_marker_count=len(matched),uncertain_marker_count=sum(m['uncertainty_flag'] for m in matched)))
        f.update(unique_threat_category_count=None if unavailable else len(categories),
            specific_threat_category_count=None if unavailable else sum(f[c] is True for c in SPECIFIC),
            first_accepted_evidence_message_id=mids[0] if mids and not unavailable else None,
            supporting_message_ids=None if unavailable else mids,
            supporting_message_count=None if unavailable else len(mids),
            category_message_support=None if unavailable else bycategory,
            category_semantics_version='v1.3-broad-uav')
    return features


def is_eligible(f):
    return f['historical_range_relation']=='within' and f['coverage_status'] in {'covered','no_messages_found'}


def summary(features):
    eligible=[f for f in features if is_eligible(f)]
    text=[f for f in eligible if (f['telegram_text_message_count'] or 0)>0]
    observed=[f for f in features if f.get('specific_threat_category_count') is not None]
    specific=[f for f in features if any(f[c] is True for c in SPECIFIC)]
    other=[f for f in features if f['other'] is True and not any(f[c] is True for c in SPECIFIC)]
    classified=[f for f in features if not f['unknown']]
    states=Counter(f['classification_status'] for f in features)
    def ratio(n,d):return n/d if d else None
    return dict(total_alerts=len(features),eligible_alerts=len(eligible),eligible_alerts_with_text=len(text),
      alerts_with_linked_text=sum((f['telegram_text_message_count'] or 0)>0 for f in features),
      specific_classified_alerts=len(specific),classified_alerts=len(classified),only_other_alerts=len(other),
      multiple_specific_category_alerts=sum(sum(f[c] is True for c in SPECIFIC)>=2 for f in features),
      multi_label_alerts_including_other=sum(sum(f[c] is True for c in CATEGORIES[:-1])>=2 for f in features),
      no_marker_with_text=states['no_marker_with_text'],no_linked_text=states['no_linked_text'],outside_telegram_coverage=states['outside_telegram_coverage'],unresolved=states['unresolved'],
      classification_state_counts={state:states[state] for state in STATES},
      per_category_alert_counts={c:sum(f[c] is True for f in features) for c in CATEGORIES[:-1]},
      any_marker_yield_all_official=ratio(len(classified),len(features)),
      any_marker_yield_eligible=ratio(sum(not f['unknown'] for f in eligible),len(eligible)),
      any_marker_yield_eligible_with_text=ratio(sum(not f['unknown'] for f in text),len(text)),
      specific_yield_all_official=ratio(len(specific),len(features)),
      specific_yield_eligible=ratio(sum(any(f[c] is True for c in SPECIFIC) for f in eligible),len(eligible)),
      specific_yield_eligible_with_text=ratio(sum(any(f[c] is True for c in SPECIFIC) for f in text),len(text)),
      median_supporting_messages_per_classified_alert=statistics.median(f['supporting_message_count'] for f in classified) if classified and 'supporting_message_count' in classified[0] else None,
      median_supporting_messages_per_text_alert=statistics.median(f['supporting_message_count'] for f in text) if text and 'supporting_message_count' in text[0] else None,
      supporting_message_median_note='Classified denominator excludes no-marker alerts; text denominator includes observed zeros. Unavailable observations remain null.',
      threat_combinations=dict(sorted(Counter(f['threat_combination'] for f in classified).items())))


def category_metrics(features,markers):
    out={}
    for c in CATEGORIES[:-1]:
        rows=[m for m in markers if m['category']==c and m['accepted_for_aggregation']]
        out[c]=dict(unique_official_alerts=len({m['alert_id'] for m in rows}),
          supporting_messages=len({(m['alert_id'],m['message_id']) for m in rows}),unique_supporting_messages=len({m['message_id'] for m in rows}),
          supporting_marker_records=len(rows),explicit_cause_alert_count=len({m['alert_id'] for m in rows if m['evidence_status']=='explicit_alert_cause'}),
          contextual_threat_alert_count=len({m['alert_id'] for m in rows if m['evidence_status'] in {'current_threat','uncertain'}}),
          uncertain_accepted_markers=sum(m['uncertainty_flag'] for m in rows),inferred_shorthand_accepted_markers=sum(m.get('inferred_shorthand',False) for m in rows),
          subtype_alert_support={sub:len({m['alert_id'] for m in rows if m['subtype']==sub}) for sub in sorted({m['subtype'] for m in rows})},
          uav_evidence_type_alert_support={typ:len({m['alert_id'] for m in rows if m.get('uav_evidence_type')==typ}) for typ in sorted({m['uav_evidence_type'] for m in rows if m.get('uav_evidence_type')})})
        if out[c]['unique_official_alerts']!=sum(f[c] is True for f in features):raise ValueError('Category metric fails feature reconciliation')
    return out


def temporal_summaries(features):
    months=defaultdict(list);years=defaultdict(list)
    for f in features:
        date=f['start_time'].astimezone(KYIV);months[date.strftime('%Y-%m')].append(f);years[str(date.year)].append(f)
    monthly=[dict(month=month,**summary(rows)) for month,rows in sorted(months.items())]
    yearly=[dict(year=year,**summary(rows)) for year,rows in sorted(years.items())]
    for tables in (monthly,yearly):
        for key in ['total_alerts','eligible_alerts','eligible_alerts_with_text','classified_alerts','specific_classified_alerts','only_other_alerts','multiple_specific_category_alerts','no_marker_with_text','no_linked_text','outside_telegram_coverage','unresolved']:
            if sum(row[key] for row in tables)!=summary(features)[key]:raise ValueError('Calendar/global totals differ: '+key)
    return monthly,yearly


def compare_versions(previous,new):
    old={f['alert_id']:f for f in previous};current={f['alert_id']:f for f in new}
    if len(old)!=len(previous) or len(current)!=len(new) or set(old)!=set(current):raise ValueError('Version comparison requires the same unique official IDs')
    rows=[];gained=[];lost=[]
    for f in new:
        before=old[f['alert_id']]
        for k in ['start_time','end_time','duration_minutes','coverage_status','historical_range_relation','telegram_message_count','telegram_text_message_count']:
            if before[k]!=f[k]:raise ValueError('Comparison modified official/coverage field '+k)
        bc=[c for c in CATEGORIES[:-1] if before[c] is True];nc=[c for c in CATEGORIES[:-1] if f[c] is True]
        prior_specific=sum(before[c] is True for c in SPECIFIC)
        prior_state=classification_state(before)
        gain=before['unknown'] and not f['unknown'];loss=not before['unknown'] and f['unknown']
        if gain:gained.append(f['alert_id'])
        if loss:lost.append(f['alert_id'])
        row=dict(alert_id=f['alert_id'],start_time=f['start_time'],end_time=f['end_time'],
          previous_version=before['classification_version'],new_version=f['classification_version'],
          previous_classification_status=before['classification_status'],previous_state_under_v13_definitions=prior_state,new_classification_status=f['classification_status'],
          previous_combination=before['threat_combination'],new_combination=f['threat_combination'],previous_specific_category_count=prior_specific if before['threat_combination'] is not None else None,
          new_specific_category_count=f['specific_threat_category_count'],new_unique_threat_category_count=f['unique_threat_category_count'],
          gained_any_classification=gain,lost_any_classification=loss,added_categories=[c for c in nc if c not in bc],removed_categories=[c for c in bc if c not in nc])
        for c in CATEGORIES[:-1]:row['previous_'+c]=before[c];row['new_'+c]=f[c]
        rows.append(row)
    old_months=defaultdict(list);new_months=defaultdict(list)
    for f in previous:old_months[f['start_time'].astimezone(KYIV).strftime('%Y-%m')].append(f)
    for f in new:new_months[f['start_time'].astimezone(KYIV).strftime('%Y-%m')].append(f)
    monthly=[]
    for month in sorted(old_months):
        a,b=summary(old_months[month]),summary(new_months[month])
        monthly.append(dict(month=month,eligible_alerts=b['eligible_alerts'],eligible_alerts_with_text=b['eligible_alerts_with_text'],previous_classified=a['classified_alerts'],new_classified=b['classified_alerts'],
          previous_specific=a['specific_classified_alerts'],new_specific=b['specific_classified_alerts'],previous_only_other=a['only_other_alerts'],new_only_other=b['only_other_alerts'],
          previous_yield_eligible=a['any_marker_yield_eligible'],new_yield_eligible=b['any_marker_yield_eligible']))
    a,b=summary(previous),summary(new)
    return dict(previous_classified_alerts=a['classified_alerts'],new_classified_alerts=b['classified_alerts'],gained_alert_ids=sorted(gained),lost_alert_ids=sorted(lost),
        gained_count=len(gained),lost_count=len(lost),previous_specific_alerts=a['specific_classified_alerts'],new_specific_alerts=b['specific_classified_alerts'],
        previous_only_other=a['only_other_alerts'],new_only_other=b['only_other_alerts'],
        per_category_changes={c:dict(previous=a['per_category_alert_counts'][c],new=b['per_category_alert_counts'][c],delta=b['per_category_alert_counts'][c]-a['per_category_alert_counts'][c]) for c in CATEGORIES[:-1]},
        previous_combinations=a['threat_combinations'],new_combinations=b['threat_combinations'],monthly_coverage_changes=monthly),rows


def unclassified_sample(features,markers,messages,links,size=28,seed=20261011):
    """Round-robin alert sampling across overlapping year/volume/recent/hit strata."""
    eligible={f['alert_id']:f for f in features if f['classification_status']=='no_marker_with_text'}
    mmap={m['message_id']:m for m in messages if m['message_id'] is not None}
    byalert=defaultdict(list);candidate=defaultdict(list)
    for l in links:
        if l['alert_id'] in eligible:
            m=mmap[l['message_id']]
            if m.get('text') and m['text'].strip():byalert[l['alert_id']].append(m)
    for m in markers:
        if m['alert_id'] in eligible:candidate[m['alert_id']].append(m)
    pools=defaultdict(list);strata={}
    for aid,f in eligible.items():
        month=f['start_time'].astimezone(KYIV).strftime('%Y-%m');count=f['telegram_text_message_count'];labels=[f'year:{month[:4]}','with_rejected_candidates' if candidate[aid] else 'no_candidates',
            'density:low' if count<=3 else 'density:high' if count>=20 else 'density:middle']
        if month in {'2026-08','2026-09','2026-10'}:labels.append('recent:'+month)
        why={reason for m in candidate[aid] for reason in (m['exclusion_reason'] or '').split(';') if reason}
        if any(r.startswith('geography_') for r in why):labels.append('rejected_geography')
        if 'context_uncertain' in why:labels.append('rejected_uncertain_context')
        strata[aid]=labels
        for label in labels:pools[label].append(aid)
    rng=random.Random(seed)
    for label in sorted(pools):pools[label]=sorted(pools[label]);rng.shuffle(pools[label])
    chosen=[];seen=set()
    while len(chosen)<min(size,len(eligible)):
        progress=False
        for label in sorted(pools):
            while pools[label] and pools[label][-1] in seen:pools[label].pop()
            if pools[label]:aid=pools[label].pop();chosen.append(aid);seen.add(aid);progress=True
            if len(chosen)==min(size,len(eligible)):break
        if not progress:break
    rows=[]
    for aid in chosen:
        f=eligible[aid];mm=sorted(byalert[aid],key=lambda m:(m['message_time'],m['source_message_index'],m['message_id']))
        mids_with_hits={m['message_id'] for m in candidate[aid]}
        # Spread original messages in time and add a hit-bearing example if absent.
        indices=sorted({0,len(mm)//4,len(mm)//2,3*len(mm)//4,len(mm)-1}) if mm else []
        sample=[mm[i] for i in indices]
        if mids_with_hits and not any(m['message_id'] in mids_with_hits for m in sample):sample[-1]=next(m for m in mm if m['message_id'] in mids_with_hits)
        sample=sorted({m['message_id']:m for m in sample}.values(),key=lambda m:(m['message_time'],m['source_message_index'],m['message_id']))
        why=Counter(reason for m in candidate[aid] for reason in (m['exclusion_reason'] or '').split(';') if reason)
        rows.append(dict(alert_id=aid,start_time=f['start_time'],end_time=f['end_time'],duration_minutes=f['duration_minutes'],linked_message_count=f['telegram_message_count'],linked_text_count=f['telegram_text_message_count'],
          candidate_marker_count=f['candidate_marker_count'],main_exclusion_reasons=dict(why),representative_message_ids=[m['message_id'] for m in sample],representative_original_texts=[m['text'] for m in sample],
          representative_original_timestamps=[m['message_time_original'] for m in sample],representative_source_files=[m['source_file'] for m in sample],representative_source_indices=[m['source_message_index'] for m in sample],
          strata=strata[aid],human_review_status='',human_decision='',review_notes=''))
    return rows
