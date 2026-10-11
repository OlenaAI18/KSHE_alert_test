"""Reproducible full-data Task0049 diagnostics, comparison and analytical handoff."""
import argparse
import copy
import json
import math
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
import yaml
from .core import process, STATUS, scope, operational, HARD
from .lexical import Profile
from kyiv_alerts.classification.consolidation import summary, compare_versions, temporal_summaries, CATEGORIES, is_eligible
from kyiv_alerts.classification.coverage_audit import write_audit_csv
from kyiv_alerts.classification_v15.__main__ import validate as validate_previous, regressions
from kyiv_alerts.controlled_review.__main__ import digest
from kyiv_alerts.integration.__main__ import validate_h2, validate_links
from kyiv_alerts.attribution.core import pre_window
from kyiv_alerts.controlled_review.core import order

DATA=Path('data/processed/classification_v1_6')
REPORT=Path('reports/classification_v1_6')
FILES={'alerts':'data/interim/alerts.parquet','messages':'data/interim/telegram_messages.parquet','links':'data/processed/alert_message_links.parquet','coverage':'data/processed/alert_coverage.parquet',
       **{v:f'data/processed/classification_{v}/alert_threat_features.parquet' for v in ['v1_3','v1_4','v1_5']},
       'markers':'data/processed/classification_v1_5/message_threat_markers.parquet'}
CAUSES=['lexical','boilerplate','operational']
PROBES=re.compile(r'(?<!\w)(?:міг|миг|mig)(?:у|а|ів|и|ам)?(?![\w-])|балістиці|балістичн\w*\s+(?:ціл\w*|тра(?:є|е)кторі\w*)|ту[ -]?95(?![\w-])|брсд|\bкр\b',re.I)


def protected_snapshot(root):
    result={}
    for folder in ['data','reports','config','src/kyiv_alerts']:
        for p in sorted((root/folder).rglob('*')):
            if not p.is_file() or '__pycache__' in p.parts: continue
            rel=str(p.relative_to(root))
            if '/classification_v1_6/' in rel or '/classification_v16/' in rel or rel=='config/attribution_v1_6.yaml' or rel.startswith('config/task0049_'): continue
            result[rel]=digest(p)
    return result


def rule_hashes(root):
    return {str(p.relative_to(root)):digest(p) for p in sorted((root/'src/kyiv_alerts/classification_v16').glob('*.py'))}|{'config/attribution_v1_6.yaml':digest(root/'config/attribution_v1_6.yaml')}


def verify_baseline(features):
    s=summary(features)
    expected={'total_alerts':2594,'eligible_alerts':1803,'classified_alerts':1141,'no_marker_with_text':564,'no_linked_text':98,'outside_telegram_coverage':790,'unresolved':1}
    for key,value in expected.items():
        if s[key]!=value:raise ValueError(f'Baseline differs: {key}={s[key]}, expected {value}')
    return dict(**expected,minimum_for_70_percent=math.ceil(1803*.70),additional_unique_required=math.ceil(1803*.70)-1141)


def load_profile(root,policy):
    return Profile(root/'config/threat_dictionary_v1_3.yaml',root/'config/kyiv_geography_v1_1.yaml',yaml.safe_load((root/'config/attribution_v1_4.yaml').read_text()),yaml.safe_load((root/'config/attribution_v1_5.yaml').read_text()),policy)


def validate(markers,features,data):
    # Reuse frozen provenance/contamination/category reconciliation validator.
    view=[dict(m,v14_accepted=m['v15_accepted']) for m in markers]
    validate_previous(view,features,dict(data,v14=data['v1_5']))
    mm={m['message_id']:m for m in data['messages'] if m['message_id'] is not None}
    for m in markers:
        if m['classification_version']!='v1.6':raise ValueError('Incorrect version')
        if m['accepted_for_aggregation'] and m['subtype']=='mig_channel_model_unspecified' and not (m['uncertainty_flag'] and m['inferred_shorthand']):raise ValueError('MiG convention lost uncertainty')
        for span in m.get('context_view_excluded_spans',[]):
            if mm[m['message_id']]['text'][span['match_start']:span['match_end']]!=span['original_text']:raise ValueError('Boilerplate span changed')


def diagnostics(data,markers,features,dictionary,policy):
    """All 564 baselines receive nonexclusive auditable diagnostic signals."""
    mm={m['message_id']:m for m in data['messages'] if m['message_id'] is not None};seq=defaultdict(list);old=defaultdict(list);new=defaultdict(list)
    for l in data['links']:seq[l['alert_id']].append(mm[l['message_id']])
    for m in data['markers']:old[m['alert_id']].append(m)
    for m in markers:new[m['alert_id']].append(m)
    fm={f['alert_id']:f for f in features};result=[]
    for f in data['v1_5']:
        if f['classification_status']!='no_marker_with_text':continue
        aid=f['alert_id'];before=old[aid];after=new[aid]
        newlex=[m for m in after if m['evidence_role']=='lexical_anchor' and m['rule_id'] in dictionary.extension_ids]
        explicit_candidates=[m for m in before if m['evidence_role']=='lexical_anchor' and m['time_relation']=='inside_interval' and not any(x in (m['baseline_exclusion_reason'] or '') for x in HARD)]
        context=[m for m in after if m['evidence_role']=='context_reference']
        pre=[m for m in after if m['time_relation']=='before_alert' and m['evidence_role']=='lexical_anchor' and m['operational_status']=='operational']
        a=any(m['operational_status']=='operational' for m in newlex)
        b=bool(explicit_candidates)
        c=bool(context)
        d=bool(pre)
        e=bool(newlex) or any(PROBES.search(m['text'] or '') for m in seq[aid])
        supported=not fm[aid]['unknown'];insufficient=not supported
        groups=[name for name,value in zip('ABCDEF',[a,b,c,d,e,insufficient]) if value]
        primary=next((g for g in 'ABCD E'.replace(' ','') if g in groups),'F') if supported else 'F'
        result.append(dict(alert_id=aid,start_time=f['start_time'],end_time=f['end_time'],baseline_status=f['classification_status'],v16_status=fm[aid]['classification_status'],v16_categories=fm[aid]['threat_combination'],
                           **{'group_'+k:v for k,v in zip('ABCDEF',[a,b,c,d,e,insufficient])},diagnostic_groups=groups,primary_group=primary,
                           original_linked_message_ids=[m['message_id'] for m in sorted(seq[aid],key=order)],
                           lexical_gap_evidence=[dict(message_id=m['message_id'],category=m['category'],rule_id=m['rule_id'],matched_text=m['matched_text'],original_text=m['original_text'],timestamp_original=m['source_timestamp_original'],accepted=m['accepted_for_aggregation'],reason=m['exclusion_reason']) for m in newlex],
                           rejected_v15_reasons=dict(Counter(m['exclusion_reason'] for m in before if not m['accepted_for_aggregation'])),
                           pre_alert_candidate_ids=sorted({m['message_id'] for m in pre}),context_candidate_ids=sorted({m['message_id'] for m in context}),
                           supporting_source_ids=fm[aid]['supporting_message_ids'],remaining_cause='no_explicit_lexical_anchor_in_available_context' if insufficient and not after else 'only_nonoperational_negated_historical_or_geographically_unlinked_evidence' if insufficient and not any(m['operational_status']=='operational' for m in after) else 'operational_anchor_without_defensible_kyiv_or_pre_alert_correspondence' if insufficient else 'evidence_supported_experimental_correction',
                           diagnostic_status='NONEXCLUSIVE SIGNALS; NOT INDEPENDENT HUMAN ERROR LABELS'))
    assert len(result)==564 and len({r['alert_id'] for r in result})==564
    return result


def evidence_records(markers,ids,mm):
    rows=[]
    for m in markers:
        if m['alert_id'] not in ids or not m['accepted_for_aggregation']:continue
        rows.append(dict(alert_id=m['alert_id'],category=m['category'],message_id=m['message_id'],anchor_message_id=m['anchor_message_id'],
            original_text=m['original_text'],timestamp_original=m['source_timestamp_original'],message_time=m['source_message_time'],source_file=m['source_file'],source_message_index=m['source_message_index'],
            rule_id=m['rule_id'],subtype=m['subtype'],matched_text=m['matched_text'],match_start=m['match_start'],match_end=m['match_end'],evidence_role=m['evidence_role'],time_relation=m['time_relation'],
            linking_confidence=m['linking_confidence'],attribution_strength=m['attribution_strength'],operational_rule_id=m['operational_rule_id'],literal_geography=m['geography'],geography_rule=m['geography_attribution_rule'],
            uncertainty_flag=m['uncertainty_flag'],uncertainty_reasons=m['uncertainty_reasons'],scope_trace=m['scope_trace'],v16_correction_causes=m.get('v16_correction_causes',[]),
            support_message_ids=m['support_message_ids'],supporting_source_messages=[dict(message_id=mid,text=mm[mid]['text'],timestamp_original=mm[mid]['message_time_original'],message_time=mm[mid]['message_time'],source_file=mm[mid]['source_file'],source_message_index=mm[mid]['source_message_index']) for mid in m['support_message_ids']]))
    return rows


def calendars(versions):
    tables={v:temporal_summaries(fs) for v,fs in versions.items()};result=[]
    for i,label in [(0,'month'),(1,'year')]:
        rows=[]
        for n,ref in enumerate(tables['v1_6'][i]):
            row=dict(period=ref[label],**{label:ref[label]},eligible=ref['eligible_alerts'],eligible_with_text=ref['eligible_alerts_with_text'],no_text=ref['no_linked_text'],residual_with_text=ref['no_marker_with_text'],outside=ref['outside_telegram_coverage'],unresolved=ref['unresolved'])
            for v in versions:
                s=tables[v][i][n];assert s[label]==ref[label]
                row[v+'_classified']=s['classified_alerts'];row[v+'_coverage']=s['any_marker_yield_eligible']
            rows.append(row)
        result.append(rows)
    return result


def markdown(report):
    lines=['# Task 004.9 — Residual marker coverage v1.6','',f'**{STATUS}**','', '| Version | Classified | Eligible coverage | Text residual |','|---|---:|---:|---:|']
    for v,s in report['versions'].items():lines.append(f"| {v} | {s['classified_alerts']} | {s['any_marker_yield_eligible']:.2%} | {s['no_marker_with_text']} |")
    c=report['comparison_v15_v16'];lines+=['',f"Against v1.5: {c['gained_count']} newly classified, {c['lost_count']} lost, net {c['gained_count']-c['lost_count']}. 70% target reached: {report['target_reached']}. Minimum target count: 1263.",'','| Category | v1.3 | v1.4 | v1.5 | v1.6 |','|---|---:|---:|---:|---:|']
    for cat in CATEGORIES[:-1]:lines.append('| '+cat+' | '+' | '.join(str(s['per_category_alert_counts'][cat]) for s in report['versions'].values())+' |')
    lines+=['','## Diagnostics and corrections','All 564 v1.5 text residuals are represented in residual_diagnostics.csv. A–F are nonexclusive diagnostic signals, not human-confirmed error counts.',json.dumps(report['diagnostic_group_counts']),
            'A: new explicit operational lexical anchor; B: previously rejected in-alert lexical candidate; C: bounded chronological reference candidate; D: operational pre-anchor with possible correspondence (acceptance still requires inside support); E: dictionary gap/shorthand signal; F: no supported attribution after corrections.','',
            'Corrections: inflected ballistic targets/trajectories and балістиці; Tu-95 without model suffix; existing cruise inflections; БРСД abbreviation; user-approved finite MiG channel bulletins (model unspecified); exact known channel boilerplate excluded from context only; explicit current operational clauses, positions and type-only bulletins. Generic UAV never establishes Shahed model.',
            'Known donation footer is not current operational evidence. Broad donation paragraphs, carrier explanations, satire, conditional future events, denied threats and foreign-region bulletins remain excluded. Negative scope can withdraw invalid old evidence; removals are explicit.',
            'Chronological rules remain 5-minute ordinary gap and 10-minute anchor age; pre-alert lookback remains 10 minutes and requires in-alert correspondence. No widened window, locality-only labels, alert-ID exceptions or taxonomy expansion.',
            '', '## Correction gains','Overlapping supports are not added. Disjoint gain attribution uses lexical → boilerplate → operational → existing_context priority, an accounting convention, not independent causal contribution.',json.dumps(report['rule_gain_accounting']),
            '', '## Evidence and quality',json.dumps(report['evidence_strength_distribution']),
            'All newly accepted categories have full source evidence in category_changes_evidence.csv. Compact exception audit covers high-risk new rules, contradictions and removals; it is not a population precision estimate. Previously reviewed positives and known discrepancies remain in regression_cases.csv.',
            'Source data/previous versions/timestamps/links are hash-verified unchanged. Missing text, outside source span and unresolved DST remain distinct. All new associations retain uncertainty. Independent precision/recall remain null.',
            '', '## Remaining uncertainty',json.dumps(report['remaining_unknown_causes']),
            '2581 and 1096 remain confirmed-label/source-attribution discrepancies unless newly supported sources reproduce them; provisional cases stay provisional. Human acceptance remains required for analytical adoption.',
            '', 'Reproduce: `.venv/bin/python -m kyiv_alerts.classification_v16 --root .`. Stop marker development after this evidence-supported iteration; no forecasting or automatic commit.']
    return '\n'.join(lines)+'\n'


def handoff(report):
    s=report['versions']['v1_6']
    lines=['# Time-series handoff — Task 004.9','',f'**{STATUS}**','',
           'Selected technical candidate: experimental v1.6, conditional on research-lead acceptance. Frozen v1.5 remains the comparison baseline. This handoff does not start time-series modeling.',
           f"Coverage: {s['classified_alerts']}/1803 eligible ({s['any_marker_yield_eligible']:.2%}); 2594 official alerts. Marker improvement stops now, regardless of the target outcome.",'',
           'Use data/processed/classification_v1_6/alert_threat_features.parquet (one original alert per row) and message_threat_markers.parquet (accepted AND rejected evidence). Filter accepted_for_aggregation for evidence. Deduplicate by alert/category, not occurrence; multiple categories overlap and do not count weapons or attacks.',
           '', 'Unknown handling: available text without accepted attribution is unknown, never confirmed absence. Separate no-linked-text, outside historical coverage and unresolved temporal ambiguity. Retain nullable category observations; do not impute false for unavailable periods. Report eligible and text-observed denominators alongside any category fraction.',
           '', f"Source boundaries (UTC): Telegram {report['source_bounds']['messages']['min']} through {report['source_bounds']['messages']['max']}; official starts {report['source_bounds']['alerts']['min']} through {report['source_bounds']['alerts']['max']}; last resolved end {report['source_end']} (October 5 Kyiv local). October is partial. Pre-export official records support interval-only descriptions, not threat-specific comparisons. One DST-ambiguous interval remains unresolved; H2 Kyiv-seasonal Telegram normalization remains frozen.",
           '', 'Calendar grouping: Europe/Kyiv official start year/month. monthly_coverage.csv and yearly_coverage.csv provide every period, denominators and all four versions. Do not treat reporting-density and wording changes as physical threat regime changes.',
           '', 'Permitted after acceptance: retrospective descriptive alert frequency/duration, category-conditioned descriptions restricted to observed intervals, version/missingness sensitivity analysis. Unsupported: attack/weapon counts, verified cause, confirmed deployment/model, category absence from silence, forecasting individual threats, safety advice or claims that these retrospective markers were available before alert start.',
           '', 'Pre-alert and cross-message evidence may be confirmed only during an alert. It cannot be used as an at-start predictor without an explicit feature-availability reconstruction and an approved analytical protocol. MiG shorthand is a channel convention with unspecified model; generic UAV is a broad analytical group, not verified Shahed.',
           '', 'Prior diagnostic holdout remains unlabeled; all-residual v1.6 exploration is not blind independent evaluation. Compact audit is analyst source inspection, not research-lead gold.',
           '', 'Known unresolved review cases: 1096 target includes ballistic but pre-warning lacks admissible inside corroboration; 2581 target includes Shahed but recorded explicit sources support jet UAV. 1416 is provisional, 2590 a working hypothesis. Previous review sample/holdout has no newly inferred gold labels. Compact exception review cannot establish independent population accuracy.',
           '', 'Quality status: software/provenance/negative regression gates are recorded in validation_results.json. Semantic population accuracy is unmeasured; research-lead acceptance is pending. No time-series analysis or forecasting has been executed.',
           '', '| Year | Eligible | v1.6 classified | Coverage |', '|---|---:|---:|---:|']
    for r in report['yearly_coverage']:lines.append(f"| {r['year']} | {r['eligible']} | {r['v1_6_classified']} | {r['v1_6_coverage']:.2%} |" if r['v1_6_coverage'] is not None else f"| {r['year']} | {r['eligible']} | {r['v1_6_classified']} | unavailable |")
    return '\n'.join(lines)+'\n'


def run(root):
    root=root.resolve();tick=time.perf_counter();protected=protected_snapshot(root);frozen=rule_hashes(root);out=root/REPORT;out.mkdir(parents=True,exist_ok=True)
    data={k:pq.read_table(root/p).to_pylist() for k,p in FILES.items()}
    try:baseline=verify_baseline(data['v1_5'])
    except ValueError as exc:
        (out/'baseline_abort.json').write_text(json.dumps(dict(status='BLOCKED',reason=str(exc)),indent=2)+'\n');raise
    validate_h2(data['messages']);validate_links(data['links'],data['coverage'],data['alerts'],data['messages'])
    policy=yaml.safe_load((root/'config/attribution_v1_6.yaml').read_text());dictionary=load_profile(root,policy)
    markers,features=process(data['v1_5'],data['messages'],data['links'],data['markers'],dictionary,data['alerts'],policy)
    validate(markers,features,data);comparison,changes=compare_versions(data['v1_5'],features)
    mm={m['message_id']:m for m in data['messages'] if m['message_id'] is not None};diagnostic=diagnostics(data,markers,features,dictionary,policy)
    gained=set(comparison['gained_alert_ids']);changed={r['alert_id'] for r in changes if r['added_categories'] or r['removed_categories']}
    strengths=defaultdict(set);supports=defaultdict(set);new_pairs={(r['alert_id'],c) for r in changes for c in r['added_categories']};gained_causes=defaultdict(set)
    for m in markers:
        if not m['accepted_for_aggregation']:continue
        strengths[m['attribution_strength']].add(m['alert_id'])
        if (m['alert_id'],m['category']) in new_pairs:
            causes=[]
            if m['anchor_rule_id'] in dictionary.extension_ids:causes.append('lexical')
            if re.search('Новини з Сіверщини та Полтавщини|🔥 Збір помсти',m['original_text']):causes.append('boilerplate')
            if m['operational_rule_id'].startswith('v16_'):causes.append('operational')
            if not causes:causes=['existing_context']
            for cause in causes:supports[cause].add(m['alert_id']);gained_causes[m['alert_id']].add(cause)
    disjoint=Counter(next((c for c in [*CAUSES,'existing_context'] if c in gained_causes[aid]),'existing_context') for aid in sorted(gained))
    assert sum(disjoint.values())==len(gained)
    regression=regressions(root,features,markers,dict(data,v14=data['v1_5']))
    for r in regression:r['v16_categories']=r.pop('v15_categories');r['v15_categories']=r.pop('v14_categories')
    versions={v:data[v] for v in ['v1_3','v1_4','v1_5']}|{'v1_6':features};months,years=calendars(versions)
    added_evidence=evidence_records(markers,changed,mm)
    folder=root/DATA;folder.mkdir(parents=True,exist_ok=True)
    for name,rows in [('alert_threat_features',features),('message_threat_markers',markers)]:
        table=pa.Table.from_pylist(rows);pq.write_table(table,folder/(name+'.parquet'),compression='zstd');assert pq.read_table(folder/(name+'.parquet')).equals(table)
    for name,rows in [('residual_diagnostics',diagnostic),('newly_classified_alerts',[r for r in changes if r['gained_any_classification']]),
            ('lost_or_modified_classifications',[r for r in changes if r['lost_any_classification'] or r['added_categories'] or r['removed_categories']]),('all_alert_changes',changes),('category_changes_evidence',added_evidence),('monthly_coverage',months),('yearly_coverage',years),('regression_cases',regression)]:write_audit_csv(rows,out/(name+'.csv'))
    # Compact audit inputs are fixed after source inspection, never interpretation exceptions.
    audit_path=root/'config/task0049_exception_audit.yaml';audit=yaml.safe_load(audit_path.read_text())['cases'] if audit_path.exists() else []
    fmap={f['alert_id']:f for f in features};by=defaultdict(list)
    for m in markers:by[m['alert_id']].append(m)
    audit_rows=[]
    for case in audit:
        aid=str(case['alert_id']);observed={c for c in CATEGORIES[:-1] if fmap[aid][c] is True}
        candidates=[m for m in by[aid] if m['message_id']==str(case['message_id']) and m['category']==case['category']]
        observed_acceptance=any(m['accepted_for_aggregation'] for m in candidates)
        passed=bool(candidates) and observed_acceptance==case['accepted']
        audit_rows.append(dict(**case,v16_categories=sorted(observed),source_inspection_check='PASS' if passed else 'REVIEW_REQUIRED',assessor='ANALYST_SOURCE_INSPECTION_NOT_RESEARCH_LEAD_GOLD',all_candidate_evidence=by[aid]))
    write_audit_csv(audit_rows,out/'exception_audit.csv')
    if protected_snapshot(root)!=protected:raise ValueError('A prior source/classifier/artifact changed')
    if rule_hashes(root)!=frozen:raise ValueError('Rules changed during full inference')
    diagnostic_by={r['alert_id']:r for r in diagnostic}
    final_residual=[]
    for f in features:
        if f['classification_status']=='no_marker_with_text':
            diag=diagnostic_by.get(f['alert_id'])
            cause=diag['remaining_cause'] if diag else 'withdrawn_previous_false_absence_attribution'
            final_residual.append(dict(alert_id=f['alert_id'],start_time=f['start_time'],end_time=f['end_time'],remaining_cause=cause,was_v15_text_residual=diag is not None,source_candidate_ids=sorted({m['message_id'] for m in by[f['alert_id']]})))
    write_audit_csv(final_residual,out/'remaining_unknown_with_text.csv')
    report=dict(status=STATUS,baseline=baseline,versions={v:summary(fs) for v,fs in versions.items()},comparison_v15_v16=comparison,
                target_reached=summary(features)['classified_alerts']>=1263,diagnostic_group_counts={g:sum(r['group_'+g] for r in diagnostic) for g in 'ABCDEF'},
                remaining_unknown_causes=dict(Counter(r['remaining_cause'] for r in final_residual)),
                rule_gain_accounting=dict(overlapping_supports={k:len(v&gained) for k,v in supports.items()},disjoint_first_support=dict(disjoint),disjoint_total=sum(disjoint.values()),overlap_warning='Do not sum overlapping supports; disjoint priority is an accounting convention, not causal ablation.'),
                evidence_strength_distribution={k:len(v) for k,v in strengths.items()},monthly_coverage=months,yearly_coverage=years,
                category_changes=len(new_pairs),removed_category_pairs=sum(len(r['removed_categories']) for r in changes),modified_existing_alerts=sum(not r['gained_any_classification'] and not r['lost_any_classification'] and bool(r['added_categories'] or r['removed_categories']) for r in changes),
                reviewed_case_results=regression,exception_audit_cases=len(audit_rows),exception_audit_mismatches=[r['alert_id'] for r in audit_rows if r['source_inspection_check']!='PASS'],
                source_bounds={k:dict(min=min(x[field] for x in data[k] if x[field] is not None).isoformat(),max=max(x[field] for x in data[k] if x[field] is not None).isoformat()) for k,field in [('messages','message_time'),('alerts','start_time')]},
                source_end=max(x['end_time'] for x in data['alerts'] if x['end_time'] is not None).isoformat(),protected_hashes=protected,frozen_rule_hashes=frozen,compact_audit_fixture_hash=digest(audit_path) if audit_path.exists() else None,elapsed_seconds=time.perf_counter()-tick,
                prior_holdout_status='UNLABELED; v1.6 full-residual exploration is not a blind independent evaluation',
                independent_precision=None,independent_recall=None,research_lead_acceptance='PENDING',marker_development='STOPPED_AFTER_TASK0049',forecasting_started=False,automatic_commit=False)
    (out/'classification_comparison.json').write_text(json.dumps(report,ensure_ascii=False,default=str,indent=2)+'\n',encoding='utf-8')
    (out/'classification_comparison.md').write_text(markdown(report),encoding='utf-8');(out/'time_series_handoff.md').write_text(handoff(report),encoding='utf-8')
    validation=dict(status='STRUCTURAL_GATES_PASSED_TESTS_PENDING',full_data_provenance='PASSED',source_previous_versions_unchanged=True,original_ids_timestamps_links_unchanged=True,
                    all_new_categories_inspectable=True,pre_alert_warning_alone_accepted=0,exception_audit_mismatches=report['exception_audit_mismatches'],
                    confirmed_label_discrepancies=[r['alert_id'] for r in regression if r['regression_status']=='CONFIRMED_LABEL_DISCREPANCY'],semantic_population_accuracy=None,
                    human_acceptance='PENDING',tests_passed=None,tests_failed=None,tests_skipped=None)
    (out/'validation_results.json').write_text(json.dumps(validation,indent=2)+'\n')
    print(json.dumps(dict(classified=report['versions']['v1_6']['classified_alerts'],coverage=report['versions']['v1_6']['any_marker_yield_eligible'],gained=comparison['gained_count'],lost=comparison['lost_count'],target_reached=report['target_reached'],elapsed_seconds=report['elapsed_seconds'])))
    return report


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path('.'));args=parser.parse_args();run(args.root)


if __name__=='__main__':main()
