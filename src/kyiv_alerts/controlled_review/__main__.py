"""Build isolated controlled review outputs, without rerunning classification."""
import argparse,csv,hashlib,json,time
from pathlib import Path
from collections import Counter,defaultdict
from importlib.metadata import version
import pyarrow.parquet as pq
from .core import *
from .workbook import build
from kyiv_alerts.classification.coverage_audit import validate_consolidation,write_audit_csv
from kyiv_alerts.integration.__main__ import validate_h2,validate_links

FILES={'alerts':'data/interim/alerts.parquet','messages':'data/interim/telegram_messages.parquet','links':'data/processed/alert_message_links.parquet','coverage':'data/processed/alert_coverage.parquet','features':'data/processed/classification_v1_3/alert_threat_features.parquet','markers':'data/processed/classification_v1_3/message_threat_markers.parquet','inside':'data/processed/attribution_experiment_v1/inside_interval_candidates.parquet','pre':'data/processed/attribution_experiment_v1/pre_alert_candidates.parquet','progressive':'data/processed/attribution_experiment_v1/progressive_alert_coverage.parquet','experiment_report':'reports/attribution_experiment_v1/attribution_gap_report.json','dictionary':'config/threat_dictionary_v1_3.yaml','geography':'config/kyiv_geography_v1_1.yaml'}


def digest(path):
    with path.open('rb') as f:
        h=hashlib.sha256()
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
        return h.hexdigest()


def protected_snapshot(root):
    return {str(p.relative_to(root)):digest(p) for folder in ['data','config','reports'] for p in sorted((root/folder).rglob('*')) if p.is_file() and not p.is_relative_to(root/'reports/controlled_review')}


def validate_inputs(d):
    a,m,l,f,h=d['alerts'],d['messages'],d['links'],d['features'],d['markers']
    validate_h2(m);validate_links(l,d['coverage'],a,m);validate_consolidation(h,f,m,l)
    if any(r['classification_version']!='v1.3' for r in f+h):raise ValueError('Frozen v1.3 required')
    fm={r['alert_id']:r for r in f};am={r['alert_id']:r for r in a};mm={r['message_id']:r for r in m if r['message_id'] is not None};pairs={(r['alert_id'],r['message_id']) for r in l}
    if len(fm)!=len(f) or set(fm)!=set(am):raise ValueError('Official ID mismatch')
    for r in f:
        if any(r[k]!=am[r['alert_id']][k] for k in ['start_time','end_time','duration_minutes']):raise ValueError('Official intervals changed')
    progressive=d['progressive']
    if len(progressive)!=len(fm) or len({r['alert_id'] for r in progressive})!=len(fm):raise ValueError('Progressive duplicate/missing alerts')
    for r in progressive:
        if r['alert_id'] not in fm or any(r[k]!=v for k,v in fm[r['alert_id']].items()):raise ValueError('Task0044 changed baseline')
    for hrow in h:
        source=mm[hrow['message_id']]
        if (hrow['alert_id'],hrow['message_id']) not in pairs or source['text'][hrow['match_start']:hrow['match_end']]!=hrow['matched_text']:raise ValueError('Marker source identity/span mismatch')
    for relation in ['inside','pre']:
        for r in d[relation]:
            if r['alert_id'] not in fm or r['anchor_message_id'] not in mm:raise ValueError('Experimental foreign key invalid')
            if 'PROVISIONAL' not in r['confidence_or_review_status']:raise ValueError('Experimental evidence lost provisional status')
            if r['evidence_text']!=[mm[mid]['text'] for mid in r['source_message_ids']]:raise ValueError('Experimental source text differs')
            if relation=='inside' and any((r['alert_id'],mid) not in pairs for mid in r['source_message_ids']):raise ValueError('Inside association not linked')
            if relation=='pre' and not mm[r['anchor_message_id']]['message_time']<fm[r['alert_id']]['start_time']:raise ValueError('Pre-alert message not earlier')


def validate_review(selected,overview,timeline,trace,d):
    ids={r['alert_id'] for r in selected};mm={m['message_id']:m for m in d['messages'] if m['message_id'] is not None}
    if len(ids)!=len(selected) or ids!={r['alert_id'] for r in overview}:raise ValueError('Selected IDs duplicate/mismatch')
    pairs={(r['alert_id'],r['message_id']) for r in d['links'] if r['alert_id'] in ids}
    if len(timeline)!=len(pairs) or {(r['alert_id'],r['message_id']) for r in timeline}!=pairs:raise ValueError('Timeline omitted linked messages')
    expected=[m for m in d['markers'] if m['alert_id'] in ids]
    key=lambda r:(r['alert_id'],r['message_id'],r['rule_id'],r['match_start'],r['match_end'])
    if Counter(key(r) for r in expected)!=Counter(key(r) for r in trace):raise ValueError('Candidate occurrence omitted')
    groups=defaultdict(list)
    for r in timeline:
        m=mm[r['message_id']]
        if r['original_message_text']!=m['text'] or r['timestamp']!=m['message_time']:raise ValueError('Source changed')
        groups[r['alert_id']].append(m)
    for rows in groups.values():
        if rows!=sorted(rows,key=order):raise ValueError('Chronology changed')
    for r in trace:
        if r['original_text']!=mm[r['message_id']]['text']:raise ValueError('Trace text changed')
    for rows in [overview,timeline,trace]:
        for r in rows:
            if any(v is not None for k,v in r.items() if k.startswith('human_') or k=='review_notes'):raise ValueError('Human label invented')


def report_markdown(r):
    lines=['# Task 004.5 — Controlled case review','',f"**{STATUS}**",'', '## Scope and baseline',f"Read-only diagnosis; no classifications, dictionary entries, context/geography rules, links or timestamps changed. Baseline: {json.dumps(r['baseline'],ensure_ascii=False)}.",f"Task0044 inside candidates remain provisional: {r['task0044_baseline_inside_candidates']}; text-unclassified remaining {r['task0044_baseline_remaining']}.",'','## Deterministic purposive sample',f"Seed: {r['seed']}. High volume means ≥20 linked text messages; low volume ≤3. Within each disjoint stratum sorted IDs are shuffled with the seed, then selected greedily for novel recorded diagnostic signals. Positive controls prioritize non-uncertain accepted category diversity, explicit alert causes and fewer linked messages. No population representativeness or precision/recall claims.",'', '| Stratum | Requested | Available | Selected | Missing |','|---|---:|---:|---:|---:|']
    for s in r['selection_strata']:lines.append(f"| {s['stratum']} | {s['requested']} | {s['available']} | {s['selected']} | {s['unavailable']} |")
    lines+=['', 'Selected IDs: '+', '.join(r['selected_alert_ids']),f"Sample: {r['selected_alerts']} alerts; {r['total_linked_messages']} complete linked messages ({r['messages_without_dictionary_hit']} without hits); {r['candidate_occurrences']} dictionary occurrences, {r['accepted_occurrences']} accepted and {r['rejected_occurrences']} rejected.",'','## Recorded decisions, not confirmed errors','Recorded exclusions (overlapping): '+json.dumps(r['recorded_exclusion_reasons'],ensure_ascii=False), 'Purposive sample signal counts (overlapping): '+json.dumps(r['diagnostic_signal_alert_counts'],ensure_ascii=False), 'Recorded experimental inside levels: '+json.dumps(r['task0044_evidence_level_occurrences'],ensure_ascii=False), f"Inside provisional alerts in sample: {r['sample_inside_provisional_alerts']}. Pre-alert evidence is shown separately: {r['sample_pre_alert_occurrences']} occurrences.",'','## Missing instrumentation']
    lines += ['- '+item for item in r['missing_instrumentation_description']]
    lines+=['','## Human review instructions','Read the full chronological message sequence before choosing a category or A–H failure reason. A lexical miss may be irrelevant text or insufficient information; a geography/context rejection may be correct. Proposed diagnostic groups list questions, not truth labels. Every human field is blank and workbook dropdowns are available. Positive controls are existing accepted evidence, not independent gold-standard labels. Task0044 experimental categories are never promoted into v1.3.', 'No-hit messages have empty marker arrays, not invented trace rows. They remain visible in Full Message Timeline and its companion CSV, allowing A/F/G/H to be investigated without asserting which applies.', '', '## Workbook and provenance','The workbook contains README, Alert Overview, Full Message Timeline, Classification Trace, Diagnostic Summary, and supplementary Pre-Alert Evidence. Overview IDs navigate to timelines; timeline/trace IDs return to overview. Dates in Excel display Kyiv local time; CSV retains timezone-aware instants and all original timestamp strings. Source strings are text, never formulas. Machine CSV keeps complete source text if Excel cannot represent a cell.',f"Excel cell representation adjustments: {len(r['excel_cell_adjustments'])}; details in JSON. Protected input/data/config/prior-report hashes are recorded and verified unchanged.", '',f"Elapsed generation time: {r['elapsed_seconds']} seconds. Software: {json.dumps(r['software_versions'])}.",'','## Output files','- controlled_alert_review.xlsx','- classification_error_trace.csv','- controlled_review_summary.md / .json','- full_message_timeline.csv / selected_alert_overview.csv / pre_alert_evidence.csv', '', 'No classifier correction, clustering, forecasting, time-series analysis or commit performed. Stop for research-lead review.']
    return '\n'.join(lines)+'\n'


def run(root,seed=SEED):
    tick=time.perf_counter();root=root.resolve();out=root/'reports/controlled_review'
    protected=protected_snapshot(root);input_hashes={k:digest(root/p) for k,p in FILES.items()}
    d={k:pq.read_table(root/p).to_pylist() for k,p in FILES.items() if p.endswith('.parquet')}
    validate_inputs(d)
    experiment=json.loads((root/FILES['experiment_report']).read_text(encoding='utf-8'))
    # Validate experimental report is from exactly the same inputs, not stale outputs.
    for key in ['alerts','messages','links','coverage','features','markers','dictionary','geography']:
        if input_hashes[key]!=experiment['input_hashes'][key]:raise ValueError('Stale experimental report: '+key)
    baseline=baseline_counts(d['features']);inside_ids={r['alert_id'] for r in d['inside'] if r['evidence_level'] in SUPPORTED}
    if len(inside_ids)!=experiment['stage_b']['new_provisional_alerts'] or baseline!=experiment['baseline']:raise ValueError('Experimental report baseline mismatch')
    selected,strata=select(d['features'],d['markers'],d['inside'],seed)
    overview,timeline,trace,pre=reconstruct(selected,d['features'],d['messages'],d['links'],d['markers'],d['inside'],d['pre'])
    validate_review(selected,overview,timeline,trace,d)
    levels=[r for r in d['inside'] if r['alert_id'] in {s['alert_id'] for s in selected}]
    report=dict(task_status='COMPLETE' if not any(s['unavailable'] for s in strata) else 'INCOMPLETE_SELECTION_STRATA',review_status=STATUS,seed=seed,selection_method='sorted IDs, seeded shuffle, greedy novel recorded diagnostic signals; purposive, not random statistical sample',volume_thresholds=dict(high_min_text=20,low_max_text=3),baseline=baseline,task0044_baseline_inside_candidates=len(inside_ids),task0044_baseline_remaining=baseline['text_unclassified']-len(inside_ids),selection_strata=strata,selected_alert_ids=[s['alert_id'] for s in selected],selected_alerts=len(selected),sample_role_counts=dict(Counter(s['sample_role'] for s in selected)),classification_states=dict(Counter(r['current_status'] for r in overview)),total_linked_messages=len(timeline),total_linked_text_messages=sum(bool(r['original_message_text'] and r['original_message_text'].strip()) for r in timeline),messages_without_dictionary_hit=sum(not r['dictionary_hit'] for r in timeline),messages_with_dictionary_hit=sum(r['dictionary_hit'] for r in timeline),candidate_occurrences=len(trace),accepted_occurrences=sum(r['final_acceptance_status']=='accepted' for r in trace),rejected_occurrences=sum(r['final_acceptance_status']=='rejected' for r in trace),recorded_exclusion_reasons=dict(Counter(x for r in trace for x in r['exclusion_reasons'])),diagnostic_signal_alert_counts=dict(Counter(x for s in selected for x in s['diagnostic_signals'])),task0044_evidence_level_occurrences=dict(Counter(r['evidence_level'] for r in levels)),sample_inside_provisional_alerts=len(inside_ids&{s['alert_id'] for s in selected}),sample_pre_alert_occurrences=len(pre),missing_instrumentation_counts=dict(Counter(x for r in trace for x in r['missing_instrumentation'])),missing_instrumentation_description=['Legacy regex IDs/individual pattern hits that assigned initial context/geography were not recorded; do not reconstruct a fictional trace. Existing approved override IDs and locality rule matches are preserved.','A null approved override ID means no recorded override; it does not identify the underlying legacy context pattern or explain default uncertain.','Suppressed overlaps/family markers record exclusion strings but not the exact competing occurrence responsible.','Task0044 does not retain match_start/match_end; associations are matched at alert/anchor/rule/category/subtype level, which can be ambiguous for repeated same-rule occurrences.','No independent human truth labels exist; lexical misses and A–H root causes cannot be confirmed automatically.'],human_reviewed_alerts=0,population_precision=None,population_recall=None,input_hashes=input_hashes,protected_hashes=protected,source_hashes_unchanged=None,excel_cell_adjustments=[],software_versions={name:version(name) for name in ['openpyxl','pyarrow','et-xmlfile']})
    out.mkdir(parents=True,exist_ok=True)
    for name,rows in [('classification_error_trace',trace),('full_message_timeline',timeline),('selected_alert_overview',overview),('pre_alert_evidence',pre)]:write_audit_csv(rows,out/(name+'.csv'))
    if protected_snapshot(root)!=protected:raise ValueError('Protected sources changed before workbook export')
    report['source_hashes_unchanged']=True
    report['excel_cell_adjustments']=build(out/'controlled_alert_review.xlsx',overview,timeline,trace,pre,report)
    if protected_snapshot(root)!=protected:raise ValueError('Existing data/config/prior reports mutated')
    report['source_hashes_unchanged']=True;report['elapsed_seconds']=round(time.perf_counter()-tick,6)
    (out/'controlled_review_summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (out/'controlled_review_summary.md').write_text(report_markdown(report),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in {'protected_hashes','input_hashes'}},ensure_ascii=False))
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path('.'));parser.add_argument('--seed',type=int,default=SEED);args=parser.parse_args();run(args.root,args.seed)
