"""Run isolated v1.4 experiment and reconcile every official alert with v1.3."""
from pathlib import Path
from collections import Counter,defaultdict
from importlib.metadata import version
import json,argparse,time,copy
import yaml
import pyarrow as pa
import pyarrow.parquet as pq
from .core import process,STATUS,CATEGORIES
from .lexical import LexicalProfile
from kyiv_alerts.controlled_review.__main__ import protected_snapshot,digest,FILES,validate_inputs
from kyiv_alerts.classification.consolidation import summary,compare_versions,temporal_summaries,category_metrics
from kyiv_alerts.classification.coverage_audit import write_audit_csv
from kyiv_alerts.ingestion.timeutils import KYIV


def snapshot(root):
    return {str(p.relative_to(root)):digest(p) for folder in ['data','config','reports'] for p in sorted((root/folder).rglob('*')) if p.is_file() and not p.is_relative_to(root/'data/processed/classification_v1_4') and not p.is_relative_to(root/'reports/classification_v1_4')}


def validate(markers,features,data):
    mm={m['message_id']:m for m in data['messages'] if m['message_id'] is not None};fm={f['alert_id']:f for f in features};old={f['alert_id']:f for f in data['features']};pairs={(l['alert_id'],l['message_id']) for l in data['links']}
    if len(fm)!=len(features) or set(fm)!=set(old):raise ValueError('Official alert IDs not retained')
    seen=set();accepted=defaultdict(list)
    for m in markers:
        identity=(m['alert_id'],m['message_id'],m['rule_id'],m['match_start'],m['match_end'],m['anchor_message_id'],m['anchor_rule_id'],m['anchor_match_start'],m['evidence_role'])
        if identity in seen:raise ValueError('Duplicate marker identity')
        seen.add(identity)
        if m['category'] not in CATEGORIES[:-1] or m['alert_id'] not in fm or m['anchor_message_id'] not in mm or m['message_id'] not in mm:raise ValueError('Marker foreign key/category invalid')
        source=mm[m['message_id']];anchor=mm[m['anchor_message_id']]
        if m['original_text']!=source['text'] or m['source_timestamp_original']!=source['message_time_original'] or m['source_message_time']!=source['message_time']:raise ValueError('Marker source text/time changed')
        if m['evidence_role']=='lexical_anchor' and source['text'][m['match_start']:m['match_end']]!=m['matched_text']:raise ValueError('Lexical span changed')
        if m['evidence_role']=='context_reference' and not source['message_time']>=anchor['message_time']:raise ValueError('Context anchor not preceding')
        if m['time_relation']=='before_alert':
            difference=(fm[m['alert_id']]['start_time']-source['message_time']).total_seconds()/60
            if not 0<m['minutes_before_alert']<=10 or m['minutes_before_alert']!=difference:raise ValueError('Pre-alert boundary invalid')
        if m['time_relation']=='inside_interval' and (m['alert_id'],m['message_id']) not in pairs:raise ValueError('Inside marker not Task003 linked')
        if m['accepted_for_aggregation']:
            if m['previous_alert_ids'] or m['intervening_boundary_alert_ids'] or m['unresolved_envelope_alert_ids']:raise ValueError('Contamination accepted')
            if not m['baseline_accepted'] and (not m['uncertainty_flag'] or not m['uncertainty_reasons']):raise ValueError('New experimental marker lost uncertainty')
            accepted[m['alert_id']].append(m)
    anchors={(m['alert_id'],m['message_id'],m['rule_id'],m['match_start'],m['match_end'],m['category']):m for m in markers if m['evidence_role']=='lexical_anchor'}
    for m in markers:
        if m['evidence_role']=='context_reference':
            key=(m['alert_id'],m['anchor_message_id'],m['anchor_rule_id'],m['anchor_match_start'],m['anchor_match_end'],m['category'])
            anchor=anchors.get(key)
            if not anchor or m['accepted_for_aggregation'] and not anchor['accepted_for_aggregation']:raise ValueError('Context reference has no accepted explicit anchor')
            if m['accepted_for_aggregation'] and (m['source_message_time']-anchor['source_message_time']).total_seconds()>600:raise ValueError('Context reference exceeded anchor age')
    baselines={(m['alert_id'],m['message_id'],m['rule_id'],m['match_start'],m['match_end']) for m in data['markers'] if m['accepted_for_aggregation']}
    retained={(m['alert_id'],m['message_id'],m['rule_id'],m['match_start'],m['match_end']) for m in markers if m['baseline_accepted'] and m['accepted_for_aggregation']}
    if baselines!=retained:raise ValueError('Baseline accepted evidence was not retained exactly')
    for aid,f in fm.items():
        previous=old[aid]
        for k in ['start_time','end_time','duration_minutes','coverage_status','historical_range_relation','telegram_message_count','telegram_text_message_count']:
            if f[k]!=previous[k]:raise ValueError('Original interval/coverage modified')
        cats={m['category'] for m in accepted[aid]}
        if cats!={c for c in CATEGORIES[:-1] if f[c] is True}:raise ValueError('Marker/feature categories do not reconcile')
        if previous['classification_status'] in {'unresolved','outside_telegram_coverage'}:
            if any(f[c] is not None for c in CATEGORIES[:-1]) or accepted[aid]:raise ValueError('Unavailable observation invented')
        if any(previous[c] is True and f[c] is not True for c in CATEGORIES[:-1]):raise ValueError('Baseline category lost')
        if f['supporting_message_ids'] is not None:
            if len(f['supporting_message_ids'])!=len(set(f['supporting_message_ids'])):raise ValueError('Duplicate message support')
            if set(f['supporting_message_ids'])!={mid for m in accepted[aid] for mid in m['support_message_ids']}:raise ValueError('Support does not reconcile')


def regression_cases(root,features,markers,messages):
    cases=yaml.safe_load((root/'config/task0046_reviewed_cases.yaml').read_text())['review_cases'];fm={f['alert_id']:f for f in features};mm={m['message_id']:m for m in messages if m['message_id'] is not None}
    result=[]
    for case in cases:
        case.setdefault('clarification',None);case.setdefault('research_lead_decision',None)
        aid=case['alert_id'];f=fm[aid];cats=[c for c in CATEGORIES[:-1] if f[c] is True];expected=case['approved_categories'];evidence=[m for m in markers if m['alert_id']==aid and m['accepted_for_aggregation'] and m['evidence_role']=='lexical_anchor']
        missing=sorted(set(expected)-set(cats));extra=sorted(set(cats)-set(expected))
        result.append(dict(case,observed_categories=cats,missing_approved_categories=missing,additional_experimental_categories=extra,exact_match=not missing and not extra,review_status='WORKING_HYPOTHESIS_ONLY' if 'provisional' in case['label_status'] else 'SOURCE_DISCREPANCY_REQUIRES_RESEARCH_LEAD_REVIEW' if missing else 'REQUIRED_CATEGORIES_REPRODUCED_WITH_ADDITIONAL_EXPERIMENTAL_EVIDENCE' if extra else 'REQUIRED_CATEGORIES_REPRODUCED',support=[dict(category=m['category'],message_id=m['message_id'],text=mm[m['message_id']]['text'],time_relation=m['time_relation'],anchor_message_id=m['anchor_message_id'],strength=m['attribution_strength']) for m in evidence]))
    return result


def markdown(report):
    a,b=report['v1_3'],report['v1_4'];cmp=report['comparison']
    lines=['# Task 004.6 — Context-aware attribution v1.4','',f"**{STATUS}**",f"Technical run: {report['task_status']}. Independent population accuracy is not established.",'','## Frozen baseline and full-dataset reconciliation',f"Official alerts {b['total_alerts']}; eligible {b['eligible_alerts']}; linked text {b['eligible_alerts_with_text']}. Accepted v1.3 alerts {a['classified_alerts']} → experimental v1.4 {b['classified_alerts']}. New unique alerts {cmp['gained_count']}; lost {cmp['lost_count']}. Baseline accepted categories and occurrences are retained. Classification yield is lexical/attribution coverage, not precision or recall.",f"Eligible yield: {a['any_marker_yield_eligible']:.2%} → {b['any_marker_yield_eligible']:.2%}; eligible-with-text: {a['any_marker_yield_eligible_with_text']:.2%} → {b['any_marker_yield_eligible_with_text']:.2%}.", f"Single category: {a['single_category_alerts']} → {b['single_category_alerts']}; unknown including unavailable: {a['unknown_alerts']} → {b['unknown_alerts']}.", 'States: '+json.dumps(b['classification_state_counts']),f"Multi-label (including other): {a['multi_label_alerts_including_other']} → {b['multi_label_alerts_including_other']}; multiple-specific: {a['multiple_specific_category_alerts']} → {b['multiple_specific_category_alerts']}; other-only {a['only_other_alerts']} → {b['only_other_alerts']}.",'','## Approved changes and explicit uncertainty','Within official Kyiv intervals, explicit current operational markers can contribute experimentally despite unspecified/nearby geography or legacy uncertain context. Literal geography and original exclusions remain separate. Negation/history, unrelated regional confinement, jokes, donations and explanatory articles do not create new accepted markers. No temporal association independently verifies direction or model.', 'Short explicit anchors define episodes with at most ten minutes anchor age and five minutes between consecutive messages. Resets and competing anchors stop propagation. Multiple types make elliptical references ambiguous. Geography alone never creates a category. Pre-alert retrieval is [start-10 minutes, start), excludes previous membership/intervening boundaries/unresolved envelopes; weak pre-alert anchors need coherent inside-interval followups before acceptance. Context and pre-alert evidence are not alert causes.', 'The frozen v1.3 lexical engine is reused, with one user-confirmed alias extension: бандероль → jet_uav. No specific model inference. Existing overlap/family suppression remains active. Profile v1.4 is explicit about its v1.3 base and authorized alias. All new accepted associations retain uncertainty and reasons.','', '## Categories','| Category | v1.3 | v1.4 | Delta |','|---|---:|---:|---:|']
    for c,v in cmp['per_category_changes'].items():lines.append(f"| {c} | {v['previous']} | {v['new']} | {v['delta']} |")
    lines+=['','## Correction contributions','Overlapping causes: '+json.dumps(report['rule_gain_breakdown'],ensure_ascii=False),'Do not add these nonexclusive counts. Support counts are not counterfactual causal gains. Each correction is also disabled in a separate full-data ablation; unique_alerts_lost_when_disabled measures coverage that depends on it under the remaining rules. Ablation counts can also overlap. Cross-message support can improve provenance without adding a category already identified by the explicit anchor. Pre-alert and cross-message gains often overlap; baseline-support preservation is excluded from new gains.','', '## Month and year classification yields','| Month | Eligible | v1.3 classified | v1.4 classified | v1.4 eligible yield |','|---|---:|---:|---:|---:|']
    for row in report['recent_months']:lines.append(f"| {row['month']} | {row['eligible_alerts']} | {row['previous_classified_alerts']} | {row['classified_alerts']} | {row['any_marker_yield_eligible']:.2%} |")
    lines+=['October official starts end Oct 4; final interval ends Oct 5. Telegram continues Oct 10. Partial October is not a full-month count comparison. All month/year rows with their distinct denominators are provided as CSV and JSON.','', '## Controlled regression cases']
    for case in report['reviewed_cases']:
        lines+=['',f"Alert {case['alert_id']}: approved {case['approved_categories']}; observed {case['observed_categories']}; {case['review_status']}."]
        for s in case['support'][:4]:lines+= [f"- Source {s['message_id']} ({s['time_relation']}, {s['category']}): {s['text']}"]
    lines+=['','Cases supplied for rule development are not held-out population accuracy evidence. Alert 2590 remains an unconfirmed working hypothesis. No missing source label is fabricated to force a reviewed ID match.','', '## Evidence strength, uncertainty and limitations','Accepted strength counts: '+json.dumps(report['accepted_strength_occurrences']), 'Accepted uncertainty-reason counts (overlapping): '+json.dumps(report['uncertainty_reasons']), 'Markers: '+json.dumps(report['marker_counts']), 'A broad UAV label is not a verified Shahed model. One channel can describe simultaneous unrelated episodes, omit locality/threat words, or use aliases not approved here. Operational filtering is deterministic lexical evidence, not semantic truth. A recorded other-region geography may identify the origin of a route rather than confinement; route target is inspected separately without rewriting the literal geography. Unclear associations remain rejected candidates. Unknown/missing coverage and unresolved DST remain unknown. Human review required before production adoption or threat-category analysis.', '',f"Runtime {report['elapsed_seconds']} seconds. Input hashes and all previously existing data/config/report hashes were checked unchanged. No time-series analysis or forecasting performed."]
    return '\n'.join(lines)+'\n'


def run(root):
    tick=time.perf_counter();root=root.resolve();out=root/'data/processed/classification_v1_4';rep=root/'reports/classification_v1_4'
    # Repeats exclude only this task's output directories from the protected set.
    protected=snapshot(root)
    hashes={k:digest(root/path) for k,path in FILES.items()};hashes['policy']=digest(root/'config/attribution_v1_4.yaml');hashes['reviewed_cases']=digest(root/'config/task0046_reviewed_cases.yaml')
    data={k:pq.read_table(root/p).to_pylist() for k,p in FILES.items() if p.endswith('.parquet')};validate_inputs(data)
    policy=yaml.safe_load((root/'config/attribution_v1_4.yaml').read_text());profile=LexicalProfile(root/FILES['dictionary'],root/FILES['geography'],policy)
    lexical_cache={}
    markers,features=process(data['features'],data['messages'],data['links'],data['markers'],profile,data['alerts'],policy,lexical_cache);validate(markers,features,data)
    comparison,versionrows=compare_versions(data['features'],features);monthly,yearly=temporal_summaries(features)
    oldmonths={r['month']:r for r in temporal_summaries(data['features'])[0]}
    for r in monthly:r['previous_classified_alerts']=oldmonths[r['month']]['classified_alerts'];r['previous_yield_eligible']=oldmonths[r['month']]['any_marker_yield_eligible']
    oldyears={r['year']:r for r in temporal_summaries(data['features'])[1]}
    for r in yearly:r['previous_classified_alerts']=oldyears[r['year']]['classified_alerts'];r['previous_yield_eligible']=oldyears[r['year']]['any_marker_yield_eligible']
    gained=set(comparison['gained_alert_ids']);breakdown=[]
    for cause in ['geography','context','cross_message','pre_alert']:
        rows=[m for m in markers if m['accepted_for_aggregation'] and not m['baseline_accepted'] and cause in m['correction_causes']]
        breakdown.append(dict(correction=cause,newly_classified_unique_alerts=len(gained&{m['alert_id'] for m in rows}),all_supported_unique_alerts=len({m['alert_id'] for m in rows}),accepted_marker_records=len(rows),overlapping_with_other_corrections=True))
    full_ids={f['alert_id'] for f in features if not f['unknown']};ablations=[]
    for disabled in ['geography','context','cross_message','pre_alert']:
        ablation_policy=dict(policy,enabled_corrections=[c for c in ['geography','context','cross_message','pre_alert'] if c!=disabled])
        _,ablation_features=process(data['features'],data['messages'],data['links'],data['markers'],profile,data['alerts'],ablation_policy,lexical_cache)
        ablation_ids={f['alert_id'] for f in ablation_features if not f['unknown']}
        lost_ids=sorted(full_ids-ablation_ids)
        ablations.append(dict(disabled_correction=disabled,classified_alerts=len(ablation_ids),unique_alerts_lost_when_disabled=len(lost_ids),lost_alert_ids=lost_ids))
        next(r for r in breakdown if r['correction']==disabled)['unique_alerts_lost_when_disabled']=len(lost_ids)
    cases=regression_cases(root,features,markers,data['messages'])
    # Record the reviewed discrepancy; the classifier never receives these IDs.
    unresolved=[c for c in cases if c['missing_approved_categories'] and not c['label_status'].startswith('provisional')]
    before_summary=summary(data['features']);after_summary=summary(features)
    for metrics,rows in [(before_summary,data['features']),(after_summary,features)]:
        metrics['single_category_alerts']=sum((f['unique_threat_category_count'] or 0)==1 for f in rows)
        metrics['unknown_alerts']=sum(f['unknown'] for f in rows)
    report=dict(task_status='TECHNICALLY_COMPLETE_WITH_REVIEW_DISCREPANCY' if unresolved else 'TECHNICALLY_COMPLETE',status=STATUS,policy=policy,v1_3=before_summary,v1_4=after_summary,comparison=comparison,rule_gain_breakdown=breakdown,rule_ablations=ablations,monthly=monthly,yearly=yearly,recent_months=[r for r in monthly if r['month'] in {'2026-08','2026-09','2026-10'}],reviewed_cases=cases,unresolved_reviewed_labels=[r['alert_id'] for r in unresolved],accepted_strength_occurrences=dict(Counter(m['attribution_strength'] for m in markers if m['accepted_for_aggregation'])),uncertainty_reasons=dict(Counter(x for m in markers if m['accepted_for_aggregation'] for x in m['uncertainty_reasons'])),marker_counts=dict(total=len(markers),accepted=sum(m['accepted_for_aggregation'] for m in markers),retained_baseline_accepted=sum(m['baseline_accepted'] for m in markers),pre_alert_accepted=sum(m['accepted_for_aggregation'] and m['time_relation']=='before_alert' for m in markers),context_reference_accepted=sum(m['accepted_for_aggregation'] and m['evidence_role']=='context_reference' for m in markers)),input_hashes=hashes,protected_hashes=protected,independent_semantic_validation=False,source_hashes_unchanged=True,software_versions={n:version(n) for n in ['pyarrow','PyYAML']})
    out.mkdir(parents=True,exist_ok=True);rep.mkdir(parents=True,exist_ok=True)
    pq.write_table(pa.Table.from_pylist(markers),out/'message_threat_markers.parquet');pq.write_table(pa.Table.from_pylist(features),out/'alert_threat_features.parquet')
    write_audit_csv([r for r in versionrows if r['alert_id'] in gained],rep/'newly_classified_alerts.csv',list(versionrows[0]))
    write_audit_csv([r for r in versionrows if r['alert_id'] in set(comparison['lost_alert_ids'])],rep/'lost_classifications.csv',list(versionrows[0]))
    write_audit_csv(breakdown,rep/'rule_gain_breakdown.csv');write_audit_csv(ablations,rep/'rule_ablation_comparison.csv');write_audit_csv(monthly,rep/'monthly_coverage.csv');write_audit_csv(yearly,rep/'yearly_coverage.csv');write_audit_csv(cases,rep/'reviewed_case_checks.csv')
    # Reproducible source-backed audit sample, prioritizing reviewed IDs then novel relation/cause/category strata.
    sample=[];seen=set();observed=set()
    rows=sorted(markers,key=lambda m:(m['alert_id'],m['source_message_time'],m['rule_id'],m['match_start'] if m['match_start'] is not None else -1,m['anchor_rule_id'],m['anchor_match_start']))
    for c in cases:
        pick=next((m for m in rows if m['alert_id']==c['alert_id'] and m['accepted_for_aggregation']),None)
        if pick:sample.append(pick);seen.add((pick['alert_id'],pick['message_id'],pick['rule_id'],pick['match_start']))
    alias=next((m for m in rows if m['rule_id']=='jet_uav.banderol_user_confirmed' and m['accepted_for_aggregation']),None)
    if alias:
        key=(alias['alert_id'],alias['message_id'],alias['rule_id'],alias['match_start'])
        if key not in seen:sample.append(alias);seen.add(key)
    for m in rows:
        key=(m['alert_id'],m['message_id'],m['rule_id'],m['match_start']);tags={m['time_relation'],m['attribution_strength'],m['category'],*m['correction_causes']}
        if key not in seen and tags-observed:
            sample.append(m);seen.add(key);observed.update(tags)
        if len(sample)>=60:break
    for m in rows:
        key=(m['alert_id'],m['message_id'],m['rule_id'],m['match_start'])
        if len(sample)>=60:break
        if key not in seen and m['accepted_for_aggregation'] and not m['baseline_accepted']:sample.append(m);seen.add(key)
    message_index={m['message_id']:m for m in data['messages'] if m['message_id'] is not None}
    sample=[dict(m,supporting_evidence_text=[message_index[mid]['text'] for mid in m['support_message_ids']]) for m in sample]
    write_audit_csv(sample,rep/'review_sample.csv')
    after=snapshot(root)
    if after!=protected:raise ValueError('Protected sources/dictionaries/prior results changed')
    report['elapsed_seconds']=round(time.perf_counter()-tick,6)
    (rep/'classification_comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=lambda v:v.isoformat() if hasattr(v,'isoformat') else str(v))+'\n',encoding='utf-8')
    (rep/'classification_comparison.md').write_text(markdown(report),encoding='utf-8')
    print(json.dumps(dict(status=report['task_status'],before=report['v1_3']['classified_alerts'],after=report['v1_4']['classified_alerts'],gained=comparison['gained_count'],lost=comparison['lost_count'],categories=report['v1_4']['per_category_alert_counts'],cases=[{k:r[k] for k in ['alert_id','observed_categories','missing_approved_categories','additional_experimental_categories','review_status']} for r in cases],elapsed_seconds=report['elapsed_seconds']),ensure_ascii=False))
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path('.'));args=parser.parse_args();run(args.root)
