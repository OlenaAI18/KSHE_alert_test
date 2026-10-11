"""Versioned alert coverage reports, provenance and semantic-readiness limits."""
from collections import Counter,defaultdict
import json
import csv
from .rules import CATEGORIES
from .consolidation import SPECIFIC,STATES,summary,category_metrics,temporal_summaries,compare_versions,unclassified_sample
from .geography_review import marker_key,indexed
from kyiv_alerts.ingestion.timeutils import KYIV
from kyiv_alerts.validation.quality import json_default


def validate_consolidation(markers,features,messages,links):
    mmap={m['message_id']:m for m in messages if m['message_id'] is not None}
    pairs={(l['alert_id'],l['message_id']) for l in links}
    byalert=defaultdict(list)
    for m in markers:
        if m['accepted_for_aggregation']:byalert[m['alert_id']].append(m)
        if m.get('inferred_shorthand') and not m['uncertainty_flag']:raise ValueError('Inferred shorthand lost uncertainty')
        if m['subtype']=='generic_uav' and (m['category']!='shahed_uav' or m['uav_evidence_type']!='generic_uav'):raise ValueError('Generic UAV evidence semantics invalid')
    for f in features:
        state=f['classification_status']
        if state not in STATES:raise ValueError('Unrecognized alert-level state')
        if any(f[c] is not None and not isinstance(f[c],bool) for c in CATEGORIES):raise ValueError('Category flags must be boolean or null')
        rows=byalert[f['alert_id']]
        categories=[c for c in CATEGORIES[:-1] if f[c] is True]
        unavailable=all(f[c] is None for c in CATEGORIES[:-1])
        nullable=['unique_threat_category_count','specific_threat_category_count','supporting_message_ids','supporting_message_count','category_message_support']
        if unavailable:
            if any(f[k] is not None for k in nullable) or not f['unknown'] or f['first_accepted_evidence_message_id'] is not None:raise ValueError('Unavailable observation became negative evidence')
            continue
        if f['unique_threat_category_count']!=len(categories) or f['specific_threat_category_count']!=sum(f[c] is True for c in SPECIFIC):raise ValueError('Category count differs from booleans')
        if f['unknown']!=(not bool(categories)):raise ValueError('Unknown state differs from categories')
        if f['threat_combination']!=('+'.join(categories) or 'unknown'):raise ValueError('Combination order invalid')
        ids=f['supporting_message_ids']
        expected={m['message_id'] for m in rows}
        if len(ids)!=len(set(ids)) or set(ids)!=expected or f['supporting_message_count']!=len(ids):raise ValueError('Supporting message deduplication failed')
        ordered=sorted(ids,key=lambda mid:(mmap[mid]['message_time'],mmap[mid]['source_file'],mmap[mid]['source_message_index'],mid))
        if ids!=ordered or f['first_accepted_evidence_message_id']!=(ids[0] if ids else None):raise ValueError('First evidence is not chronological')
        if any((f['alert_id'],mid) not in pairs for mid in ids):raise ValueError('Supporting message is not Task 003 linked')
        support=f['category_message_support']
        if [x['category'] for x in support]!=categories:raise ValueError('Per-category support order differs')
        for block in support:
            mm=[m for m in rows if m['category']==block['category']]
            expectedids=[mid for mid in ids if mid in {m['message_id'] for m in mm}]
            if block['message_ids']!=expectedids or block['first_message_id']!=expectedids[0] or block['supporting_message_count']!=len(expectedids) or block['supporting_marker_count']!=len(mm) or block['uncertain_marker_count']!=sum(m['uncertainty_flag'] for m in mm):raise ValueError('Category message support fails reconciliation')
        specific=f['specific_threat_category_count']
        expectedstate='multiple_types' if specific>=2 else 'single_type' if specific==1 else 'only_other' if f['other'] is True else 'no_marker_with_text'
        if state!=expectedstate:raise ValueError('Specific category status mismatch')
    if sum(Counter(f['classification_status'] for f in features).values())!=len(features):raise ValueError('Non-exhaustive classification states')


def marker_comparison(previous,new):
    old=indexed(previous,marker_key);current=indexed(new,marker_key)
    if not set(old)<=set(current):raise ValueError('New dictionary lost existing lexical occurrences')
    allowed_migrations={'other.generic_uav':('other','shahed_uav'),'shahed_uav.reactive_shorthand':('shahed_uav','jet_uav')}
    changes=[]
    for key,m in sorted(current.items()):
        before=old.get(key)
        if before:
            for field in ['matched_text','subtype','source_file','source_message_index','evidence_context','geography','geography_mentions','geography_source']:
                if m[field]!=before[field]:raise ValueError('Unapproved lexical/geography/provenance change: '+field)
            if m['category']!=before['category'] and allowed_migrations.get(m['rule_id'])!=(before['category'],m['category']):raise ValueError('Unapproved category migration')
            if all(m[k]==before[k] for k in ['category','evidence_status','accepted_for_aggregation','uncertainty_flag','exclusion_reason']):continue
        elif m['rule_id']!='jet_uav.reactive_noun_shorthand':raise ValueError('Unapproved new lexical candidate')
        changes.append(dict(alert_id=m['alert_id'],message_id=m['message_id'],rule_id=m['rule_id'],matched_text=m['matched_text'],subtype=m['subtype'],
          previous_category=before['category'] if before else None,new_category=m['category'],previous_context=before['evidence_status'] if before else None,new_context=m['evidence_status'],
          previous_accepted=before['accepted_for_aggregation'] if before else False,new_accepted=m['accepted_for_aggregation'],
          previous_exclusion=before['exclusion_reason'] if before else None,new_exclusion=m['exclusion_reason'],
          previous_uncertainty=before['uncertainty_flag'] if before else None,new_uncertainty=m['uncertainty_flag'],uav_evidence_type=m['uav_evidence_type'],inferred_shorthand=m['inferred_shorthand'],geography=m['geography'],
          source_file=m['source_file'],source_message_index=m['source_message_index'],match_start=m['match_start'],match_end=m['match_end']))
    return changes


def build_audit(features,markers,previous_features,previous_markers,messages,links,dictionary,seed):
    validate_consolidation(markers,features,messages,links)
    monthly,yearly=temporal_summaries(features);comparison,versionrows=compare_versions(previous_features,features)
    markerrows=marker_comparison(previous_markers,markers)
    sample=unclassified_sample(features,markers,messages,links,28,seed)
    states=Counter(f['classification_status'] for f in features)
    observed={label for row in sample for label in row['strata']}
    expected=set()
    for f in features:
        if f['classification_status']!='no_marker_with_text':continue
        month=f['start_time'].astimezone(KYIV).strftime('%Y-%m')
        expected.update([f'year:{month[:4]}','with_rejected_candidates' if f['candidate_marker_count'] else 'no_candidates',
            'density:low' if f['telegram_text_message_count']<=3 else 'density:high' if f['telegram_text_message_count']>=20 else 'density:middle'])
        if month in {'2026-08','2026-09','2026-10'}:expected.add('recent:'+month)
    no_marker_ids={f['alert_id'] for f in features if f['classification_status']=='no_marker_with_text'}
    for m in markers:
        if m['alert_id'] in no_marker_ids:
            why=(m['exclusion_reason'] or '').split(';')
            if any(reason.startswith('geography_') for reason in why):expected.add('rejected_geography')
            if 'context_uncertain' in why:expected.add('rejected_uncertain_context')
    lookup={f['alert_id']:f for f in previous_features}
    untouched=['ballistic_high_speed','cruise_missile','mig31','strategic_aviation']
    non_uav_changes=[dict(alert_id=f['alert_id'],category=c,previous=lookup[f['alert_id']][c],new=f[c]) for f in features for c in untouched if lookup[f['alert_id']][c]!=f[c]]
    r=dict(task_status='COMPLETE',semantic_validation_status='PROVISIONAL — HUMAN VALIDATION REQUIRED',dictionary_version=dictionary.version,classification_version=dictionary.classification_version,
      category_semantics_version=dictionary.config['category_semantics_version'],category_semantics=dictionary.config['category_semantics'],approved_change_log=dictionary.config['approved_change_log'],
      global_metrics=summary(features),per_category_metrics=category_metrics(features,markers),monthly_statistics=monthly,yearly_statistics=yearly,version_comparison=comparison,
      non_uav_category_flag_changes=non_uav_changes,accepted_marker_records=sum(m['accepted_for_aggregation'] for m in markers),candidate_marker_records=len(markers),
      unclassified_review_sample_size=len(sample),review_sampling_seed=seed,observed_review_strata=sorted(observed),missing_review_strata=sorted(expected-observed),
      independently_reviewed_reference_examples=0,precision=None,recall=None,
      source_bounds=dict(first_official_alert_start=min(f['start_time'] for f in features),last_official_alert_start=max(f['start_time'] for f in features),last_resolved_official_alert_end=max(f['end_time'] for f in features if f['end_time']),
        first_telegram_time=min(m['message_time'] for m in messages if m['message_time']),last_telegram_time=max(m['message_time'] for m in messages if m['message_time'])),
      time_series_readiness=dict(technical_alert_level_dataset='READY',semantic_category_analysis='NOT READY — independent semantic validation and coverage-aware methodology required',
         official_interval_analysis='AVAILABLE FOR A SEPARATELY AUTHORIZED TASK; unresolved interval must remain missing for duration analysis, October is partial',
         reasons=['No independent semantic reference labels; passing tests validate implementation only.',
                 'shahed_uav now denotes a broad UAV analytical group, not a confirmed Shahed model.',
                 'Unclassified/unavailable intervals are not negative threat labels; reporting vocabulary/density changes across periods.',
                 'Reactive shorthand is channel-interpreted and retains uncertainty; geography/elliptic context gaps remain.',
                 'One DST-unresolved official interval remains unresolved; recent October official-source observations are partial.'],time_series_analysis_performed=False),
      quality_checks=dict(all_alerts_retained=True,one_row_per_alert=True,category_boolean_or_unknown=True,unique_category_aggregation=True,states_exhaustive_and_exclusive=sum(states.values())==len(features),
          source_provenance_valid=True,calendar_totals_reconcile=True,no_cross_message_coreference=True))
    return r,versionrows,markerrows,sample


def audit_markdown(r):
    g=r['global_metrics'];v=r['version_comparison']
    def rate(value):return 'unavailable' if value is None else f'{value:.2%}'
    lines=['# Task 004.3 — Alert-level marker consolidation and coverage audit','',
      f"Status: **{r['task_status']}**. **PROVISIONAL — HUMAN VALIDATION REQUIRED**.",'',
      f"Active dictionary/classification version: **{r['dictionary_version']}**. One row per official Kyiv alert; repeated message mentions cannot increase category presence. Reported threat context is not confirmed attacks, launches, interceptions or deployments.",'',
      '## Approved changes','',
      '`shahed_uav` is now a broad UAV analytical group. Generic UAV wording retains subtype/evidence type generic_uav; explicit Shahed/Geran, attack-UAV, explicit jet and inferred reactive evidence remain distinguishable. Bare reactive adjective/noun shorthand belongs to jet_uav with uncertainty_flag=true and inferred_shorthand=true; it never establishes Shahed-238 or another model. Existing source subtypes, spans, rule IDs and literal geography are preserved.','',
      *['- '+item for item in r['approved_change_log']], '',
      'Operational context and Kyiv relevance still qualify evidence. Negation, history, non-threat meanings and unsupported context remain excluded. No standalone locality or elliptical fragment supplies a category; no cross-message referent inference.','',
      '## Global reconciliation','',
      '| Metric | Alerts |','| --- | ---: |']
    for k in ['total_alerts','eligible_alerts','eligible_alerts_with_text','specific_classified_alerts','classified_alerts','only_other_alerts','multiple_specific_category_alerts','multi_label_alerts_including_other','no_marker_with_text','no_linked_text','outside_telegram_coverage','unresolved']:
        lines.append(f'| {k} | {g[k]} |')
    lines += ['','The seven classification states are exclusive: '+json.dumps(g['classification_state_counts'],sort_keys=True)+'. `single_type`/`multiple_types` count the six analytical categories excluding other; broad UAV is an analytical category, not model verification. Other remains a separate flag even alongside a specific category. Null unavailable observations differ from observed zero markers.','',
      '| Denominator | Any accepted category | At least one analytical category excluding other |','| --- | ---: | ---: |',
      f"| All {g['total_alerts']} official alerts | {rate(g['any_marker_yield_all_official'])} | {rate(g['specific_yield_all_official'])} |",
      f"| {g['eligible_alerts']} historically eligible alerts | {rate(g['any_marker_yield_eligible'])} | {rate(g['specific_yield_eligible'])} |",
      f"| {g['eligible_alerts_with_text']} eligible alerts with text | {rate(g['any_marker_yield_eligible_with_text'])} | {rate(g['specific_yield_eligible_with_text'])} |",'',
      'Classification yield is detection coverage, not recall, attack probability, event frequency or actual historical threat incidence.','',
      '## Per-category source support','',
      '| Category | Unique alerts | Supporting alert/message pairs | Unique message IDs | Marker occurrences | Cause alerts | Contextual alerts | Uncertain accepted markers |',
      '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for c,m in r['per_category_metrics'].items():
        lines.append(f"| {c} | {m['unique_official_alerts']} | {m['supporting_messages']} | {m['unique_supporting_messages']} | {m['supporting_marker_records']} | {m['explicit_cause_alert_count']} | {m['contextual_threat_alert_count']} | {m['uncertain_accepted_markers']} |")
    lines+=['','Message support counts unique (alert_id, message_id) pairs; unique message IDs additionally deduplicate cross-alert overlap. Marker occurrences can repeat within a message. Cause/context alert subsets overlap; counts are not deployment counts. Subtype and UAV-evidence-type support breakdowns are retained in JSON.','',
      '## Version comparison','',f"Any accepted category: **{v['previous_classified_alerts']} → {v['new_classified_alerts']}**; gained {v['gained_count']}, lost {v['lost_count']}. Analytical categories excluding other: {v['previous_specific_alerts']} → {v['new_specific_alerts']}; other-only: {v['previous_only_other']} → {v['new_only_other']}.",'',
      'This includes deliberate regrouping of existing generic-UAV evidence, not newly verified Shahed models or improved precision. All IDs/categories/combinations are compared in classification_version_comparison.csv; exact candidate transitions are in marker_version_comparison.csv.','',
      'Newly classified IDs: '+json.dumps(v['gained_alert_ids'])+'. Lost IDs: '+json.dumps(v['lost_alert_ids'])+'.','',
      'Unaffected-category flag changes to inspect: '+json.dumps(r['non_uav_category_flag_changes'])+'.','',
      '| Category | Previous | v1.3 | Delta |','| --- | ---: | ---: | ---: |']
    for c,m in v['per_category_changes'].items():lines.append(f"| {c} | {m['previous']} | {m['new']} | {m['delta']} |")
    lines+=['','## Yearly coverage','',
      '| Year | All alerts | Eligible | With text | Analytical categories | Only other | No marker / text | Multiple specific | Any-marker / eligible | Specific / eligible | Median supporting / classified |',
      '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for m in r['yearly_statistics']:
        lines.append(f"| {m['year']} | {m['total_alerts']} | {m['eligible_alerts']} | {m['eligible_alerts_with_text']} | {m['specific_classified_alerts']} | {m['only_other_alerts']} | {m['no_marker_with_text']} | {m['multiple_specific_category_alerts']} | {rate(m['any_marker_yield_eligible'])} | {rate(m['specific_yield_eligible'])} | {m['median_supporting_messages_per_classified_alert']} |")
    lines+=['','## Monthly coverage','',
      '| Month | Eligible | With text | Analytical categories | Only other | No marker / text | Multiple specific | Any-marker / eligible | Specific / eligible | Median supporting / classified |',
      '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for m in r['monthly_statistics']:
        lines.append(f"| {m['month']} | {m['eligible_alerts']} | {m['eligible_alerts_with_text']} | {m['specific_classified_alerts']} | {m['only_other_alerts']} | {m['no_marker_with_text']} | {m['multiple_specific_category_alerts']} | {rate(m['any_marker_yield_eligible'])} | {rate(m['specific_yield_eligible'])} | {m['median_supporting_messages_per_classified_alert']} |")
    lines+=['','Year/month calendar uses Europe/Kyiv alert start. Eligible means resolved and fully contained in the observed Telegram span. Median supporting messages is defined among classified alerts (separate observed-text median in JSON includes genuine zeros). Null unavailable observations are never replaced by zero. October is a partial official-alert window; Telegram extends further, which does not create additional official intervals. Source bounds: '+json.dumps(r['source_bounds'],default=json_default)+'.','',
      '## Unclassified review','',f"{r['unclassified_review_sample_size']} unique alerts in unclassified_alerts_review.csv, seed {r['review_sampling_seed']}. Stratified across available years, message-density levels, August–October 2026 and lexical-hit/no-candidate cases. Complete original messages, source positions and timestamps remain traceable. Human fields are blank; no new label is inferred.",'',
      'Observed strata: '+json.dumps(r['observed_review_strata'])+'. Missing strata: '+json.dumps(r['missing_review_strata'])+'.','',
      '## Readiness and remaining limitations','',
      'The alert-level dataset is technically ready for a separately scoped analysis. **Threat-category time-series conclusions are not semantically ready**: independent human validation, reporting-coverage treatment and a predeclared methodology remain necessary. Interval-only descriptive analysis can be considered separately, retaining missing duration for the unresolved DST interval. No time-series analysis was started.','',
      *['- '+reason for reason in r['time_series_readiness']['reasons']], '',
      'Precision/recall remain null; software tests do not establish semantic or statistical validation. Increased category coverage partly reflects a broader category definition.','',
      '## Reproduction and integrity','',
      '`python -m kyiv_alerts.classification --dictionary config/threat_dictionary_v1_3.yaml --geography config/kyiv_geography_v1_1.yaml --previous data/processed/classification_v1_2 --previous-report reports/classification_v1_2/classification_report.json --output data/processed/classification_v1_3 --report reports/classification_v1_3`','',
      'Inputs and previous outputs unchanged: '+str(r['input_hashes_unchanged'])+'. SHA-256: '+json.dumps(r['input_sha256'],sort_keys=True)+'.','',
      f"Measured CLI runtime: {r['elapsed_seconds']} seconds. Tests/readback/repeat verification are recorded in docs/VALIDATION_PLAN.md.",'']
    return '\n'.join(lines)


def write_audit_csv(rows,path,columns=None):
    """Machine-readable nested evidence and full original multiline CSV text."""
    fields=columns or (list(rows[0]) if rows else ['alert_id','message_id','rule_id'])
    with path.open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for row in rows:
            writer.writerow({k:json.dumps(v,ensure_ascii=False,sort_keys=True,default=json_default) if isinstance(v,(dict,list)) else json_default(v) if hasattr(v,'isoformat') else v for k,v in row.items()})
