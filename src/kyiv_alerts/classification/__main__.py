"""Classify Task 003 linked text, preserving source inputs and review uncertainty."""
import argparse
from collections import Counter
import csv
from importlib.metadata import version
import json
from pathlib import Path
import re
import time
import yaml
import pyarrow as pa
import pyarrow.parquet as pq
from kyiv_alerts.ingestion.__main__ import file_hash
from kyiv_alerts.integration.__main__ import TIMESTAMP, write_table, validate_h2, validate_links
from kyiv_alerts.validation.quality import json_default
from .rules import Dictionary, CATEGORIES
from .pipeline import process, diagnostics, review_sample

GEOGRAPHY_MENTION = pa.struct([
    (key,pa.string()) for key in ['locality_id','canonical_name','locality_type','category','matched_text','rule_id','resolution_status']
]+[('match_start',pa.int64()),('match_end',pa.int64()),('requires_kyiv_anchor',pa.bool_())])
MARKER_SCHEMA = pa.schema([(k,pa.string()) for k in ['message_id','alert_id','category','subtype','matched_text','rule_id','evidence_context','evidence_status','geography','exclusion_reason','dictionary_version','source_file']] + [('source_message_index',pa.int64()),('match_start',pa.int64()),('match_end',pa.int64()),('accepted_for_aggregation',pa.bool_()),('geography_mentions',pa.list_(GEOGRAPHY_MENTION)),('geography_source',pa.string()),('geography_dictionary_version',pa.string()),('classification_version',pa.string()),('context_status_original',pa.string()),('context_rule_id',pa.string()),('relevant_to_kyiv',pa.bool_()),('relevance_rule_id',pa.string()),('uncertainty_flag',pa.bool_()),('evidence_qualifiers',pa.list_(pa.string()))])
FEATURE_SCHEMA = pa.schema([('alert_id',pa.string()),('start_time',TIMESTAMP),('end_time',TIMESTAMP),('duration_minutes',pa.float64()),('coverage_status',pa.string()),('historical_range_relation',pa.string()),('telegram_message_count',pa.int64()),('telegram_text_message_count',pa.int64())]+[(c,pa.bool_()) for c in CATEGORIES]+[('threat_combination',pa.string()),('explicit_cause_categories',pa.list_(pa.string())),('marker_evidence_count',pa.int64()),('candidate_marker_count',pa.int64()),('classification_status',pa.string()),('dictionary_version',pa.string()),('geography_dictionary_version',pa.string()),('classification_version',pa.string())])


CATEGORY_MESSAGE_SUPPORT=pa.struct([
    ('category',pa.string()),('first_message_id',pa.string()),('message_ids',pa.list_(pa.string())),
    ('supporting_message_count',pa.int64()),('supporting_marker_count',pa.int64()),('uncertain_marker_count',pa.int64())])
MARKER_SCHEMA_V13=pa.schema(list(MARKER_SCHEMA)+[('uav_evidence_type',pa.string()),('inferred_shorthand',pa.bool_())])
FEATURE_SCHEMA_V13=pa.schema(list(FEATURE_SCHEMA)+[
    ('legacy_classification_status',pa.string()),('unique_threat_category_count',pa.int64()),('specific_threat_category_count',pa.int64()),
    ('first_accepted_evidence_message_id',pa.string()),('supporting_message_ids',pa.list_(pa.string())),('supporting_message_count',pa.int64()),
    ('category_message_support',pa.list_(CATEGORY_MESSAGE_SUPPORT)),('category_semantics_version',pa.string())])


def validate_outputs(markers,features,alerts,messages,links,dictionary):
    amap={a['alert_id']:a for a in alerts}
    mmap={m['message_id']:m for m in messages if m['message_id'] is not None}
    pairs={(l['alert_id'],l['message_id']) for l in links}
    if len(features)!=len(alerts) or len({f['alert_id'] for f in features})!=len(alerts) or {f['alert_id'] for f in features}!=set(amap):
        raise ValueError('Output must preserve all official alerts exactly once')
    seen=set()
    rule_ids={r['rule_id'] for r,_,_ in dictionary.rules}
    for m in markers:
        pair=m['alert_id'],m['message_id']
        identity=(*pair,m['rule_id'],m['match_start'],m['match_end'])
        if pair not in pairs or identity in seen or m['rule_id'] not in rule_ids:
            raise ValueError('Invalid/duplicate marker foreign key or rule ID')
        seen.add(identity)
        original=mmap[m['message_id']]
        if original['text'][m['match_start']:m['match_end']]!=m['matched_text']:
            raise ValueError('Marker text span differs from original source')
        for key in ['source_file','source_message_index']:
            if original[key]!=m[key]:
                raise ValueError('Marker provenance differs from original source')
        if m['dictionary_version']!=dictionary.version:
            raise ValueError('Marker dictionary version mismatch')
    for m in markers:
        original=mmap[m['message_id']]['text']
        for mention in m.get('geography_mentions',[]):
            if original[mention['match_start']:mention['match_end']]!=mention['matched_text']:
                raise ValueError('Locality span differs from original text')
            if not dictionary.localities or mention['locality_id'] not in dictionary.localities.entries:
                raise ValueError('Unknown locality dictionary ID')
            entry=dictionary.localities.entries[mention['locality_id']]
            if any(mention[k]!=entry[k] for k in ['canonical_name','locality_type','category','requires_kyiv_anchor']):
                raise ValueError('Locality metadata differs from dictionary entry')
        if m['classification_version']!=dictionary.classification_version or m['geography_dictionary_version']!=dictionary.geography_version:
            raise ValueError('Geographic/classification version mismatch')
    for f in features:
        for k in ['start_time','end_time','duration_minutes']:
            if f[k]!=amap[f['alert_id']][k]:
                raise ValueError('Alert feature modifies official interval')
        if f['dictionary_version']!=dictionary.version or f['classification_version']!=dictionary.classification_version or f['geography_dictionary_version']!=dictionary.geography_version:
            raise ValueError('Feature version mismatch')


def markdown(r):
    lines=['# Dictionary classification report','',f"Status: **{r['task_status']}**",'']
    if 'error' in r:
        return '\n'.join(lines+['Error: '+r['error'],''])
    lines += ['**PROVISIONAL — HUMAN VALIDATION REQUIRED**. Frequencies below describe reported threat-context markers, never confirmed weapon attacks or deployments. No independently reviewed reference labels exist; precision and recall are unavailable.', '',
              'Legacy modes aggregate current/explicit-cause markers only with city/nationwide geography. Reviewed v1.2 mode additionally uses explicit target/city-cause/Kinzhal-launch relevance rules and accepts qualified warnings with uncertainty retained; literal text geography remains unchanged. In legacy modes, oblast, other-region, unspecified and mixed-geography candidates remain review-only; v1.2 accepts only the approved relevance exceptions described above. Sentence-local geography takes precedence; absent local geography falls back to the message only when unambiguous. Cancelled and historical text is excluded; general ambiguous context remains excluded, while v1.2 allows user-approved probable operational warnings. Before v1.3, generic UAVs use `other:generic_uav`. In v1.3 they enter broad analytical `shahed_uav` with generic_uav subtype, without inferring a Shahed model; reactive shorthand enters jet_uav with inferred uncertainty. Overlapping more specific spans suppress generic spans. Generic UAV/missile terms also stay review-only if a specific member of that family occurs in the same clause; all candidates remain traceable.', '',
              'False means not detected in available linked text. Missing historical coverage, no linked text and unresolved time yield null category booleans/counts; `unknown` is an analytical state. Existing source timestamps and Task 003 outputs are unchanged. Aircraft activity requires no missile launch; denial of launch does not cancel an aircraft activity marker.','', '## Totals','']
    for k in ['total_processed_alerts','total_input_messages','total_processed_links','unique_processed_messages','linked_messages_with_text','alerts_with_telegram_text','alerts_with_detected_category','single_label_alerts','multi_label_alerts','unknown_alerts','messages_with_candidate_markers','messages_with_accepted_markers','candidate_marker_records','accepted_marker_records','excluded_marker_records']:
        lines.append(f'- {k}: {r[k]}')
    for title,key in [('Classification states','classification_status_counts'),('Per-category alert counts','per_category_alert_counts'),('Combinations','combination_counts'),('Candidate contexts','context_counts'),('Candidate geography','geography_counts'),('Exclusion reasons (non-exclusive)','exclusion_reason_counts')]:
        lines += ['', '## '+title,'','| Value | Count |','| --- | ---: |']
        lines += [f'| {k} | {v} |' for k,v in r[key].items()]
    lines += ['', '## Monthly classification coverage and publication density','',
              'Eligible = fully historically contained and temporally resolved. Classification rate is classified / eligible; a second rate conditions on eligible alerts with linked text. Publication counts are descriptive reporting density, not threat incidence. Earlier no-history months have unavailable rates. Low-density and high-density strata are review diagnostics, not statistical regimes.','',
              '| Month | Eligible | With text | Classified | / Eligible | / Text | Published messages | Linked messages | Median linked / eligible |','| --- | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: |']
    def rate(x):return 'unavailable' if x is None else f'{100*x:.2f}%'
    for m in r['monthly_classification_coverage']:
        lines.append(f"| {m['month']} | {m['eligible_alerts']} | {m['alerts_with_text']} | {m['classified_alerts']} | {rate(m['classified_share_of_eligible'])} | {rate(m['classified_share_of_text_alerts'])} | {m['published_messages']} | {m['linked_messages']} | {m['median_linked_messages_per_eligible_alert']} |")
    lines += ['', '## Validation and limitations','',f"Review sample: {r['validation_sample_size']} unique alert/message pairs, seed {r['sampling_seed']}; reviewer fields intentionally blank. Round-robin sampling across overlapping year/category/context/geography/status/volume strata is for error discovery, not an unbiased population precision estimate. Absent real-data strata are reported, not fabricated.", '',
              'User-approved interpretation policy (if enabled): '+json.dumps(r.get('user_approved_interpretation_policy'),ensure_ascii=False), '',
              'Geographic dictionary version: '+str(r['geography_dictionary_version'])+'; classification version: '+r['classification_version']+'. Locality matches remain provisional; suburbs are oblast, shared/common names need a Kyiv anchor. The optional `--geography config/kyiv_geography.yaml` enables the extension.', '',
              'Known weaknesses: finite synonyms and place-name list; sentence-level negation may suppress another threat in the same sentence; a location mention can be an origin/transit point rather than a destination; inferred geography from another sentence may be incorrect; colloquial warnings, local districts and elliptical follow-ups are often excluded; summaries and hypothetical language can be mixed with current threats. Explicit-cause rules describe textual attribution, not independently established causation. Generic missiles retain other; generic UAVs enter broad analytical shahed_uav only in v1.3, preserving generic subtype. Human review must examine false positives AND no-marker messages, revise rules under a new version and independently label a held-out reference set before calculating metrics. Weak evidence is not evidence of a missing threat.', '',
              'Year-level reporting density (partial years are not directly comparable): '+json.dumps(r['publication_density_by_year']), '',
              'Representative review-only candidates: '+json.dumps(r['representative_review_cases'],ensure_ascii=False), '',
              'Per-category candidate support: '+json.dumps(r['category_support'],ensure_ascii=False), '',
              'Missing review strata: '+json.dumps(r['missing_review_strata']), '',
              'Input SHA-256: '+json.dumps(r['input_sha256']), '',
              'Software versions: '+json.dumps(r['software_versions']), '',
              f"Runtime seconds: {r['elapsed_seconds']}",'',
              'CLI: `python -m kyiv_alerts.classification --alerts data/interim/alerts.parquet --messages data/interim/telegram_messages.parquet --links data/processed/alert_message_links.parquet --coverage data/processed/alert_coverage.parquet --dictionary config/threat_dictionary.yaml --output data/processed --report reports/classification`','',
              'No time-series analysis or forecasting was performed.','']
    return '\n'.join(lines)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for name,default in [('alerts','data/interim/alerts.parquet'),('messages','data/interim/telegram_messages.parquet'),('links','data/processed/alert_message_links.parquet'),('coverage','data/processed/alert_coverage.parquet'),('dictionary','config/threat_dictionary.yaml'),('output','data/processed'),('report','reports/classification')]:
        p.add_argument('--'+name,type=Path,default=Path(default))
    p.add_argument('--geography',type=Path,default=None,help='Optional Kyiv locality dictionary; enables v1.1-geo')
    p.add_argument('--seed',type=int,default=20261010)
    p.add_argument('--sample-size',type=int,default=180)
    p.add_argument('--previous',type=Path,default=Path('data/processed/classification_v1_2'),help='Frozen reviewed v1.2 evidence/features for v1.3 audit')
    p.add_argument('--previous-report',type=Path,default=Path('reports/classification_v1_2/classification_report.json'))
    args=p.parse_args(argv)
    if args.sample_size<=0:
        p.error('Sample size must be positive')
    paths={k:getattr(args,k) for k in ['alerts','messages','links','coverage','dictionary']}
    if args.geography:
        paths['geography']=args.geography
    outputs=[args.output/n for n in ['message_threat_markers.parquet','alert_threat_features.parquet']]+[args.report/n for n in ['classification_report.json','classification_report.md','validation_sample.csv']]
    if len({x.resolve() for x in outputs})!=len(outputs) or {x.resolve() for x in outputs}&{x.resolve() for x in paths.values()}:
        p.error('Outputs must be distinct from all inputs')
    started=time.perf_counter()
    report={'task_status':'BLOCKED'}
    audit=None;version_rows=[];marker_changes=[];unclassified=[]
    try:
        dictionary=Dictionary(args.dictionary,args.geography)
        if dictionary.version=='v1.3':
            paths.update(previous_features=args.previous/'alert_threat_features.parquet',previous_markers=args.previous/'message_threat_markers.parquet',previous_report=args.previous_report)
            extra_outputs=[args.report/n for n in ['alert_coverage_audit.md','alert_coverage_audit.json','classification_version_comparison.csv','marker_version_comparison.csv','unclassified_alerts_review.csv','monthly_coverage.csv','yearly_coverage.csv']]
            if {x.resolve() for x in outputs+extra_outputs}&{x.resolve() for x in paths.values()}:
                raise ValueError('v1.3 outputs must not overwrite current or previous inputs')
            if args.output.resolve() in {args.previous.parent.resolve(),(args.previous.parent/'classification_v1_1').resolve()}:
                raise ValueError('v1.3 requires a separate output directory, e.g. classification_v1_3')
        hashes={k:file_hash(v) for k,v in paths.items()}
        alerts,messages,links,coverage=[pq.read_table(paths[k]).to_pylist() for k in ['alerts','messages','links','coverage']]
        validate_h2(messages)
        validate_links(links,coverage,alerts,messages)
        markers,features=process(alerts,messages,links,coverage,dictionary)
        validate_outputs(markers,features,alerts,messages,links,dictionary)
        if dictionary.version=='v1.3':
            from .coverage_audit import build_audit
            previous_features=pq.read_table(paths['previous_features']).to_pylist()
            previous_markers=pq.read_table(paths['previous_markers']).to_pylist()
            previous_report=json.loads(paths['previous_report'].read_text(encoding='utf-8'))
            if previous_report['classification_version']!='v1.2-reviewed-rules' or any(f['classification_version']!='v1.2-reviewed-rules' for f in previous_features+previous_markers):
                raise ValueError('v1.3 comparison requires frozen reviewed v1.2 inputs')
            for key in ['alerts','messages','links','coverage','geography']:
                if previous_report['input_sha256'][key]!=hashes[key]:
                    raise ValueError('Source/hash differs from reviewed v1.2: '+key)
            if sum(not f['unknown'] for f in previous_features)!=previous_report['alerts_with_detected_category']:
                raise ValueError('Previous classified baseline count differs from its report')
            audit,version_rows,marker_changes,unclassified=build_audit(features,markers,previous_features,previous_markers,messages,links,dictionary,args.seed)
        report=diagnostics(features,markers,messages,links)
        sample=review_sample(messages,links,markers,features,args.seed,args.sample_size)
        args.output.mkdir(parents=True,exist_ok=True)
        args.report.mkdir(parents=True,exist_ok=True)
        write_table(markers,args.output/'message_threat_markers.parquet',MARKER_SCHEMA_V13 if dictionary.version=='v1.3' else MARKER_SCHEMA)
        write_table(features,args.output/'alert_threat_features.parquet',FEATURE_SCHEMA_V13 if dictionary.version=='v1.3' else FEATURE_SCHEMA)
        if sample:
            with (args.report/'validation_sample.csv').open('w',encoding='utf-8-sig',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=list(sample[0]))
                writer.writeheader();writer.writerows(sample)
        if hashes!={k:file_hash(v) for k,v in paths.items()}:
            raise ValueError('Classification input changed during execution')
        support={c:dict(candidate_records=sum(m['category']==c for m in markers),accepted_records=sum(m['category']==c and m['accepted_for_aggregation'] for m in markers),accepted_alerts=report['per_category_alert_counts'][c],validation='human_review_required') for c in CATEGORIES[:-1]}
        observed={s for row in sample for s in row['strata'].split(';')}
        expected={f'category:{c}' for c in CATEGORIES[:-1]}|{f'context:{s}' for s in dictionary.context}|{f'geography:{s}' for s in ['explicit_kyiv','kyiv_region','nationwide','other_region','unspecified','uncertain']}
        report.update(task_status='TECHNICALLY COMPLETE',semantic_validation_status='PROVISIONAL — HUMAN VALIDATION REQUIRED',dictionary_version=dictionary.version,classification_version=dictionary.classification_version,geography_dictionary_version=dictionary.geography_version,user_approved_interpretation_policy=dictionary.config.get('interpretation_policy'),geography_dictionary_locality_count=len(dictionary.localities.entries) if dictionary.localities else 0,input_sha256=hashes,input_hashes_unchanged=True,sampling_seed=args.seed,validation_sample_size=len(sample),sample_stratum_counts=dict(Counter(s for row in sample for s in row['strata'].split(';'))),missing_review_strata=sorted(expected-observed),category_support=support,precision=None,recall=None,reviewed_reference_examples=0,software_versions={name:version(name) for name in ['kyiv-air-alert-analysis','pyarrow','PyYAML','tzdata']})
    except (OSError,ValueError,TypeError,KeyError,re.error,yaml.YAMLError) as exc:
        report={'task_status':'BLOCKED','error':str(exc)}
    report['elapsed_seconds']=round(time.perf_counter()-started,6)
    args.report.mkdir(parents=True,exist_ok=True)
    if audit is not None and 'error' not in report:
        from .coverage_audit import audit_markdown,write_audit_csv
        audit.update(input_sha256=hashes,input_hashes_unchanged=True,elapsed_seconds=report['elapsed_seconds'],software_versions=report['software_versions'])
        (args.report/'alert_coverage_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2,default=json_default)+'\n',encoding='utf-8')
        (args.report/'alert_coverage_audit.md').write_text(audit_markdown(audit),encoding='utf-8')
        write_audit_csv(version_rows,args.report/'classification_version_comparison.csv')
        write_audit_csv(marker_changes,args.report/'marker_version_comparison.csv')
        write_audit_csv(unclassified,args.report/'unclassified_alerts_review.csv')
        write_audit_csv(audit['monthly_statistics'],args.report/'monthly_coverage.csv')
        write_audit_csv(audit['yearly_statistics'],args.report/'yearly_coverage.csv')
    (args.report/'classification_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=json_default)+'\n',encoding='utf-8')
    (args.report/'classification_report.md').write_text(markdown(report),encoding='utf-8')
    print(f"Task 004: {report['task_status']}; category alerts={report.get('alerts_with_detected_category','unavailable')}; seconds={report['elapsed_seconds']}")
    if 'error' in report:print(report['error'])
    return 1 if 'error' in report else 0


if __name__=='__main__':
    raise SystemExit(main())
