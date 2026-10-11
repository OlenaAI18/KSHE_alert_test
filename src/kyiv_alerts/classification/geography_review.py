"""Compare frozen v1.0 with the geography extension; predictions are not review labels."""
import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import random
import time
import pyarrow.parquet as pq
from kyiv_alerts.ingestion.__main__ import file_hash
from kyiv_alerts.ingestion.timeutils import KYIV
from .rules import CATEGORIES


def marker_key(marker):
    return tuple(marker[k] for k in ['alert_id','message_id','rule_id','match_start','match_end'])


def indexed(rows, key):
    result = {key(row): row for row in rows}
    if len(result) != len(rows):
        raise ValueError('Duplicate comparison identity')
    return result


def feature_summary(features):
    eligible = [f for f in features if f['historical_range_relation']=='within' and f['coverage_status'] in {'covered','no_messages_found'}]
    text = [f for f in eligible if (f['telegram_text_message_count'] or 0)>0]
    detected = [f for f in eligible if not f['unknown']]
    return dict(total_alerts=len(features),eligible_alerts=len(eligible),eligible_alerts_with_text=len(text),classified_alerts=len(detected),classified_share_of_eligible=len(detected)/len(eligible) if eligible else None,classified_share_of_text=len(detected)/len(text) if text else None,per_category_alert_counts={c:sum(f[c] is True for f in features) for c in CATEGORIES[:-1]},classification_status_counts=dict(Counter(f['classification_status'] for f in features)))


def compare(before_markers, after_markers, before_features, after_features, messages):
    before = indexed(before_markers,marker_key)
    after = indexed(after_markers,marker_key)
    if set(before)!=set(after):
        raise ValueError('Geographic-only extension must preserve every threat candidate identity')
    old_features = indexed(before_features,lambda f:f['alert_id'])
    new_features = indexed(after_features,lambda f:f['alert_id'])
    if set(old_features)!=set(new_features):
        raise ValueError('Official alert set changed')
    for aid,old in old_features.items():
        for field in ['start_time','end_time','duration_minutes','coverage_status','historical_range_relation','telegram_message_count','telegram_text_message_count','candidate_marker_count','dictionary_version']:
            if old[field]!=new_features[aid][field]:
                raise ValueError('Non-geographic feature changed: '+field)
    mmap = {m['message_id']:m for m in messages if m['message_id'] is not None}
    changes = []
    transitions = Counter()
    unspecified_transitions = Counter()
    gained_markers, lost_markers = [], []
    for key,old in sorted(before.items()):
        new = after[key]
        for field in ['category','subtype','matched_text','evidence_status','evidence_context','dictionary_version','source_file','source_message_index']:
            if old[field]!=new[field]:
                raise ValueError('Threat/context/provenance changed: '+field)
        transitions[old['geography']+' -> '+new['geography']] += 1
        if old['geography']=='unspecified':
            unspecified_transitions[new['geography']] += 1
        if not old['accepted_for_aggregation'] and new['accepted_for_aggregation']:
            gained_markers.append(new)
        if old['accepted_for_aggregation'] and not new['accepted_for_aggregation']:
            lost_markers.append(new)
        informative_mentions = [m for m in new['geography_mentions'] if m['locality_id'] not in {'kyiv_city','kyiv_oblast'}]
        if old['geography']==new['geography'] and old['accepted_for_aggregation']==new['accepted_for_aggregation'] and not informative_mentions:
            continue
        original = mmap[old['message_id']]
        changes.append(dict(alert_id=old['alert_id'],message_id=old['message_id'],rule_id=old['rule_id'],category=old['category'],subtype=old['subtype'],matched_text=old['matched_text'],evidence_status=old['evidence_status'],before_geography=old['geography'],after_geography=new['geography'],before_accepted=old['accepted_for_aggregation'],after_accepted=new['accepted_for_aggregation'],before_exclusion=old['exclusion_reason'],after_exclusion=new['exclusion_reason'],geography_mentions=json.dumps(new['geography_mentions'],ensure_ascii=False),geography_source=new['geography_source'],original_text=original['text'],original_timestamp=original['message_time_original'],source_file=old['source_file'],source_message_index=old['source_message_index'],reviewer_geography='',reviewer_kyiv_relevance='',reviewer_decision='',reviewer_notes=''))
    gained_alerts = sorted(aid for aid,f in new_features.items() if not f['unknown'] and old_features[aid]['unknown'])
    lost_alerts = sorted(aid for aid,f in old_features.items() if not f['unknown'] and new_features[aid]['unknown'])
    monthly=[]
    for month in sorted({f['start_time'].astimezone(KYIV).strftime('%Y-%m') for f in before_features}):
        olds=[f for f in before_features if f['start_time'].astimezone(KYIV).strftime('%Y-%m')==month]
        news=[new_features[f['alert_id']] for f in olds]
        b,a=feature_summary(olds),feature_summary(news)
        monthly.append(dict(month=month,eligible_alerts=b['eligible_alerts'],before_classified=b['classified_alerts'],after_classified=a['classified_alerts'],before_rate=b['classified_share_of_eligible'],after_rate=a['classified_share_of_eligible']))
    original_unspecified=sum(m['geography']=='unspecified' for m in before_markers)
    newly_accepted_unspecified=sum(before[marker_key(m)]['geography']=='unspecified' for m in gained_markers)
    remaining_unspecified=[m for m in after_markers if m['geography']=='unspecified']
    report = dict(task_status='TECHNICALLY COMPLETE',semantic_validation_status='PROVISIONAL — HUMAN VALIDATION REQUIRED',threat_dictionary_version='v1.0',classification_version='v1.1-geo',geography_dictionary_version='kyiv-geography-v1.0',unchanged_threat_candidate_records=len(before),all_previously_excluded_markers_reevaluated=sum(not m['accepted_for_aggregation'] for m in before_markers),previously_unspecified_marker_records=original_unspecified,previously_unspecified_unique_messages=len({m['message_id'] for m in before_markers if m['geography']=='unspecified'}),previously_unspecified_transition_counts=dict(unspecified_transitions),previously_unspecified_now_recognized_or_ambiguous=original_unspecified-unspecified_transitions['unspecified'],previously_unspecified_now_accepted=newly_accepted_unspecified,previously_unspecified_now_city_context_counts=dict(Counter(m['evidence_status'] for m in after_markers if before[marker_key(m)]['geography']=='unspecified' and m['geography']=='explicit_kyiv')),representative_newly_excluded_examples=[{k:m[k] for k in ['alert_id','message_id','evidence_context','evidence_status','geography','geography_mentions']} for m in lost_markers[:8]],representative_newly_accepted_examples=[{k:m[k] for k in ['alert_id','message_id','evidence_context','evidence_status','geography','geography_mentions']} for m in gained_markers[:8]],previously_unspecified_newly_accepted_unique_messages=len({m['message_id'] for m in gained_markers if before[marker_key(m)]['geography']=='unspecified'}),remaining_unspecified_marker_records=len(remaining_unspecified),remaining_unspecified_examples=[{k:m[k] for k in ['alert_id','message_id','evidence_context','evidence_status']} for m in remaining_unspecified[:20]],geography_transition_counts=dict(sorted(transitions.items())),newly_accepted_marker_records=len(gained_markers),previously_accepted_now_excluded_records=len(lost_markers),gained_classified_alert_ids=gained_alerts,lost_classified_alert_ids=lost_alerts,before=feature_summary(before_features),after=feature_summary(after_features),monthly_comparison=monthly,precision=None,recall=None,reviewed_reference_examples=0)
    return report, changes


def sample_changes(changes, seed=20261010, target=180):
    """Unique message/alert pairs, round-robin transition/context/year strata."""
    groups=defaultdict(list)
    for row in changes:
        groups[(row['alert_id'],row['message_id'])].append(row)
    examples,pools={},defaultdict(list)
    for key,rows in sorted(groups.items()):
        first=rows[0]
        strata=set()
        for row in rows:
            strata.update(['transition:'+row['before_geography']+'->'+row['after_geography'],'context:'+row['evidence_status'],'acceptance:'+str(row['before_accepted'])+'->'+str(row['after_accepted']), 'year:'+row['original_timestamp'][:4] if '-' in row['original_timestamp'][:5] else 'year:'+row['original_timestamp'][6:10]])
        example = {k:first[k] for k in ['alert_id','message_id','original_timestamp','original_text','source_file','source_message_index']}
        locations=[location for row in rows for location in json.loads(row['geography_mentions'])]
        example.update(matched_geography_names=';'.join(sorted({m['matched_text'] for m in locations})),canonical_geography_names=';'.join(sorted({m['canonical_name'] for m in locations})),locality_types=';'.join(sorted({m['locality_type'] for m in locations})),predicted_context=';'.join(sorted({r['evidence_status'] for r in rows})),before_any_accepted=any(r['before_accepted'] for r in rows),after_any_accepted=any(r['after_accepted'] for r in rows),before_geography=';'.join(sorted({r['before_geography'] for r in rows})),after_geography=';'.join(sorted({r['after_geography'] for r in rows})),changed_markers=json.dumps([{k:r[k] for k in ['rule_id','category','matched_text','evidence_status','before_accepted','after_accepted','after_exclusion','geography_source','geography_mentions','context_status_original','context_rule_id','relevance_rule_id','uncertainty_flag','evidence_qualifiers'] if k in r} for r in rows],ensure_ascii=False),strata=';'.join(sorted(strata)),reviewer_geography='',reviewer_kyiv_relevance='',reviewer_decision='',reviewer_notes='')
        examples[key]=example
        for stratum in sorted(strata):pools[stratum].append(key)
    rng=random.Random(seed)
    for name in sorted(pools):rng.shuffle(pools[name])
    result,seen=[],set()
    while len(result)<min(target,len(examples)):
        progress=False
        for name in sorted(pools):
            while pools[name] and pools[name][-1] in seen:pools[name].pop()
            if pools[name]:
                key=pools[name].pop();seen.add(key);result.append(examples[key]);progress=True
                if len(result)==min(target,len(examples)):break
        if not progress:break
    return result


def markdown(report):
    lines=['# Task 004.1 — Geographic Dictionary Expansion','', '**PROVISIONAL — HUMAN VALIDATION REQUIRED**','',
           'Only geography interpretation changes. Threat taxonomy v1.0, lexical candidates, contexts, official intervals, H2 timestamps and Task 003 links are unchanged. Baseline output files are retained. Both increases and losses are reported; a newly recognized place is not an independently validated correct threat assignment.','',
           '| Metric | Before v1.0 | After v1.1-geo |','| --- | ---: | ---: |']
    for key in ['total_alerts','eligible_alerts','eligible_alerts_with_text','classified_alerts','classified_share_of_eligible','classified_share_of_text']:
        lines.append(f"| {key} | {report['before'][key]} | {report['after'][key]} |")
    lines += ['', '## Category counts — overlapping reported contexts', '', '| Category | Before | After |','| --- | ---: | ---: |']
    for category in CATEGORIES[:-1]:lines.append(f"| {category} | {report['before']['per_category_alert_counts'][category]} | {report['after']['per_category_alert_counts'][category]} |")
    lines += ['', '## Reassessment of rejected evidence','']
    for key in ['all_previously_excluded_markers_reevaluated','previously_unspecified_marker_records','previously_unspecified_unique_messages','previously_unspecified_now_recognized_or_ambiguous','previously_unspecified_now_accepted','remaining_unspecified_marker_records','newly_accepted_marker_records','previously_accepted_now_excluded_records']:
        lines.append(f'- {key}: {report[key]}')
    lines += ['', 'Prior unspecified geography transitions: '+json.dumps(report['previously_unspecified_transition_counts']), '',
              'Context among newly recognized city candidates: '+json.dumps(report['previously_unspecified_now_city_context_counts']), '',
              'Representative newly excluded cases for review: '+json.dumps(report['representative_newly_excluded_examples'],ensure_ascii=False), '',
              'Representative newly included cases for review: '+json.dumps(report['representative_newly_accepted_examples'],ensure_ascii=False), '',
              'Full geography transition counts: '+json.dumps(report['geography_transition_counts']), '',
              f"Newly classified alerts: {len(report['gained_classified_alert_ids'])}; previously classified now unknown: {len(report['lost_classified_alert_ids'])}.",'',
              'Named suburbs/oblast cities remain kyiv_region and do not enter city aggregation. Non-unique district names and general words (center, banks, forest, ambiguous Borshchahivka shorthand) need an explicit Kyiv or unambiguous city-locality anchor. Longest locality matches prevent Sofiivska/Petropavlivska Borshchahivka from being treated as Kyiv neighborhoods. Clause geography and original-name spans are recorded; an unambiguous message fallback remains explicitly identified. Mixed city/oblast/other-region geography is review-only. This intentionally preserved conservative rule can exclude clear routes such as "from Vyshhorod toward Kyiv" and even city-alert cause statements that mention an oblast location; these losses are limitations to adjudicate, not proof the old markers were wrong. New names never override old uncertain, negated or historical context.', '',
              '## Monthly classification coverage','', '| Month | Eligible | Before count | After count | Before rate | After rate |', '| --- | ---: | ---: | ---: | --- | --- |']
    def percent(x):return 'unavailable' if x is None else f'{100*x:.2f}%'
    for row in report['monthly_comparison']:
        lines.append(f"| {row['month']} | {row['eligible_alerts']} | {row['before_classified']} | {row['after_classified']} | {percent(row['before_rate'])} | {percent(row['after_rate'])} |")
    lines += ['', '## Human review and limitations', '',
              f"{report['human_review_sample_size']} unique changed alert/message examples; seed {report['sampling_seed']}; blank reviewer labels. Review all geography changes using geography_changes.csv, including losses and unchanged acceptance with newly named localities. This purposive sample is for error discovery, not an unbiased population precision estimate. Precision and recall remain unavailable.", '',
              'This is a finite first dictionary, not all Kyiv Oblast settlements. Colloquial aliases may name something else; names can indicate origin/transit rather than destination. Common/shared names may remain unresolved; distant oblast cities are not all suburbs. Sentence-to-message fallback can misattach locations. Locality recognition alone does not turn terse operational fragments into current_threat; the existing context rules remain conservative. Classification coverage is detection yield, not recall or proof of improved accuracy. Remaining unknown names should be added only after review under a new geography version.', '',
              'Remaining unspecified examples: '+json.dumps(report['remaining_unspecified_examples'],ensure_ascii=False), '',
              'Input SHA-256: '+json.dumps(report['input_sha256']), '',
              f"Comparison runtime seconds: {report['elapsed_seconds']}", '',
              'Reproduction: `python -m kyiv_alerts.classification --geography config/kyiv_geography.yaml --output data/processed/classification_v1_1 --report reports/classification_v1_1`, then `python -m kyiv_alerts.classification.geography_review`. No time-series analysis or forecasting.', '']
    return '\n'.join(lines)


def write_csv(rows,path):
    if not rows:return
    with path.open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before',type=Path,default=Path('data/processed'))
    parser.add_argument('--after',type=Path,default=Path('data/processed/classification_v1_1'))
    parser.add_argument('--messages',type=Path,default=Path('data/interim/telegram_messages.parquet'))
    parser.add_argument('--report',type=Path,default=Path('reports/classification_v1_1'))
    args=parser.parse_args(argv)
    started=time.perf_counter()
    inputs={}
    for prefix,directory in [('before',args.before),('after',args.after)]:
        for name in ['message_threat_markers','alert_threat_features']:
            path=directory/(name+'.parquet');inputs[prefix+'_'+name]=path
    inputs['messages']=args.messages
    hashes={k:file_hash(path) for k,path in inputs.items()}
    tables=[pq.read_table(inputs[k]).to_pylist() for k in ['before_message_threat_markers','before_alert_threat_features','after_message_threat_markers','after_alert_threat_features']]
    report,changes=compare(tables[0],tables[2],tables[1],tables[3],pq.read_table(args.messages).to_pylist())
    sample=sample_changes(changes)
    report.update(input_sha256=hashes,input_hashes_unchanged=True,sampling_seed=20261010,human_review_sample_size=len(sample),geography_change_records=len(changes),sample_stratum_counts=dict(Counter(s for row in sample for s in row['strata'].split(';'))))
    if hashes!={k:file_hash(path) for k,path in inputs.items()}:raise ValueError('Comparison input changed')
    args.report.mkdir(parents=True,exist_ok=True)
    write_csv(changes,args.report/'geography_changes.csv')
    write_csv(sample,args.report/'geography_review_sample.csv')
    report['elapsed_seconds']=round(time.perf_counter()-started,6)
    (args.report/'geography_expansion_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (args.report/'geography_expansion_report.md').write_text(markdown(report),encoding='utf-8')
    print(f"Task 004.1 comparison: before={report['before']['classified_alerts']}; after={report['after']['classified_alerts']}; prior unspecified={report['previously_unspecified_marker_records']}; review examples={len(sample)}")
    return 0


if __name__=='__main__':raise SystemExit(main())
