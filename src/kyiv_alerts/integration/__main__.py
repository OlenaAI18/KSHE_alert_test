"""Process normalized H2 Parquet inputs into temporal links and coverage reports."""
import argparse
import json
from pathlib import Path
import time
from importlib.metadata import version
import pyarrow as pa
import pyarrow.parquet as pq
from .linking import integrate
from kyiv_alerts.ingestion.__main__ import file_hash
from kyiv_alerts.ingestion.timeutils import parse_telegram_time
from kyiv_alerts.validation.quality import json_default

TIMESTAMP = pa.timestamp('us', tz='UTC')
LINK_SCHEMA = pa.schema([
    ('alert_id',pa.string()),('message_id',pa.string()),('message_time',TIMESTAMP),
    ('alert_start_time',TIMESTAMP),('alert_end_time',TIMESTAMP),
    ('match_method',pa.string()),('match_quality',pa.string()),
    ('source_file',pa.string()),('source_message_index',pa.int64()),
])
COVERAGE_SCHEMA = pa.schema([
    ('alert_id',pa.string()),('start_time',TIMESTAMP),('end_time',TIMESTAMP),
    ('duration_minutes',pa.float64()),('telegram_message_count',pa.int64()),
    ('telegram_text_message_count',pa.int64()),('has_telegram_coverage',pa.bool_()),
    ('coverage_status',pa.string()),('historical_range_relation',pa.string()),
    ('deterministic_message_count',pa.int64()),('deterministic_text_message_count',pa.int64()),
])


def validate_h2(messages):
    """Refuse stale H1 Parquet, rather than silently reinterpret normalized inputs."""
    for row in messages:
        if row.get('is_service_message') and row.get('message_time') is None:
            continue
        expected, _ = parse_telegram_time(row.get('message_time_original'))
        if row.get('message_time') != expected:
            raise ValueError(f"Message {row.get('message_id')} is inconsistent with approved H2; regenerate ingestion outputs")


def validate_links(links, coverage, alerts, messages):
    amap = {r['alert_id']: r for r in alerts}
    mmap = {r['message_id']: r for r in messages if r['message_id'] is not None}
    pairs = set()
    for link in links:
        pair = (link['alert_id'],link['message_id'])
        if pair in pairs:
            raise ValueError('Duplicate output link pair')
        pairs.add(pair)
        a,m = amap[link['alert_id']],mmap[link['message_id']]
        if not (a['start_time'] <= m['message_time'] < a['end_time']):
            raise ValueError('Link violates half-open source interval')
        for key in ['message_time','source_file','source_message_index']:
            if link[key] != m[key]:
                raise ValueError('Message source traceability mismatch')
        if link['alert_start_time'] != a['start_time'] or link['alert_end_time'] != a['end_time']:
            raise ValueError('Alert source traceability mismatch')
    if len(coverage) != len(alerts) or set(r['alert_id'] for r in coverage) != set(amap):
        raise ValueError('Coverage must retain every official alert exactly once')
    if sum(r['deterministic_message_count'] for r in coverage) != len(links):
        raise ValueError('Coverage counts do not reconcile with links')


def write_table(rows, path, schema):
    table=pa.Table.from_pylist(rows,schema=schema)
    pq.write_table(table,path,compression='zstd')
    if not pq.read_table(path).equals(table):
        raise ValueError('Parquet readback differs from output table')


def markdown(report):
    lines=['# Temporal linking and coverage report','','Task status: **'+report['task_status']+'**.','']
    if report['task_status'] != 'COMPLETE':
        return '\n'.join(lines+['Error: '+report.get('error','unknown'),''])
    lines += ['Matching uses normalized H2 absolute timestamps and half-open official intervals: `start <= time < end`. Temporal association is not Kyiv relevance, weapon evidence, threat frequency, or attack probability. Empty-text messages can match. Original inputs are unchanged.','',
              '## Totals','']
    for key in ['total_official_alerts','total_input_message_records','ordinary_message_records','service_message_records','timestamped_message_records','alerts_with_known_full_range_containment','alerts_with_known_range_intersection','eligible_alerts_for_coverage_rate','overall_coverage_rate','alerts_with_at_least_one_link','alerts_without_linked_messages','total_temporal_links','total_linked_messages','timestamped_messages_outside_alerts','median_messages_per_covered_alert','linked_messages_with_nonempty_text','linked_message_nonempty_text_share']:
        lines.append(f'- {key}: {report[key]}')
    lines += ['', '## Coverage states', '']
    lines += [f'- {key}: {count}' for key,count in report['coverage_status_counts'].items()]
    lines += ['', 'Historical message date span: '+json.dumps(report['telegram_historical_range'],default=json_default), '',
              'No-history and unresolved intervals have nullable availability/count fields; zeros do not stand for unknown observations. Separate deterministic counts are lower bounds. Known links imply observed coverage even if an interval is partial or requires review. Partial boundary intervals are explicitly labeled and excluded from primary rate denominators. The global date span does not establish uninterrupted reporting.', '',
              '## Monthly coverage (Europe/Kyiv alert start month)', '',
              'Coverage rate = covered / fully range-contained resolved eligible alerts. Unresolved and historically unavailable alerts are excluded; unavailable rates are null, not zero. Median per eligible alert includes genuine zero-message alerts. Covered-alert median excludes zeros.', '',
              '| Month | All alerts | Eligible | Covered | Rate | Median messages / eligible | Median messages / covered |',
              '| --- | ---: | ---: | ---: | --- | ---: | ---: |']
    for row in report['monthly_coverage']:
        rate=f"{100*row['coverage_rate']:.2f}%" if row['coverage_rate'] is not None else 'unavailable'
        lines.append(f"| {row['month']} | {row['total_alerts']} | {row['eligible_fully_observed_resolved_alerts']} | {row['covered_alerts']} | {rate} | {row['median_messages_per_eligible_alert']} | {row['median_messages_per_covered_alert']} |")
    lines += ['', '## Exclusions and DST uncertainty', '']
    lines += [f'- {key}: {count}' for key,count in report['excluded_message_reason_counts'].items()]
    lines += ['', f"Affected official alert IDs: {', '.join(report['affected_alert_ids']) or 'none'}.", '',
              'Unresolved intervals never receive fabricated endpoints or links. Candidate DST folds are used only to form a potential envelope, not to select an end. All timestamped messages inside such an envelope are withheld conservatively, including the prefix that is before either possible end. Ambiguous messages remain excluded and their candidate-fold intersections flag potentially affected alerts. JSON lists original IDs, source files/indices and affected alert references. A fully missing endpoint produces an unbounded uncertainty envelope and remains unknown rather than guessed.', '',
              'Half-open intervals avoid adjacent-boundary duplication. Genuinely overlapping resolved intervals retain all valid links with `review_overlapping_intervals` quality. Exact repeated message input rows are deduplicated and reported; conflicting IDs fail the run. Missing source IDs are not invented. Links remain separate from source message text.', '',
              '## Reproduction and validation', '',
              '`python -m kyiv_alerts.integration --alerts data/interim/alerts.parquet --messages data/interim/telegram_messages.parquet --output data/processed --report reports/temporal_linking`', '',
              'The CLI checks UTC schemas, original-title/H2 consistency, foreign keys, half-open membership, source provenance, pair uniqueness, retained-alert cardinality, count reconciliation, Parquet readback and unchanged input hashes. No raw dataset is rewritten.', '',
              f"Execution seconds: {report['elapsed_seconds']}", '',
              'Input hashes: '+json.dumps(report['input_sha256']), '',
              'Software versions: '+json.dumps(report['software_versions']), '',
              'Reporting gaps, untimed service events and unresolved folds limit inference. No threat classification, NLP, forecasts or statistical hypothesis tests were performed. Task 004 has not started.', '']
    return '\n'.join(lines)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--alerts',type=Path,default=Path('data/interim/alerts.parquet'))
    parser.add_argument('--messages',type=Path,default=Path('data/interim/telegram_messages.parquet'))
    parser.add_argument('--output',type=Path,default=Path('data/processed'))
    parser.add_argument('--report',type=Path,default=Path('reports/temporal_linking'))
    args=parser.parse_args(argv)
    outputs=[args.output/'alert_message_links.parquet',args.output/'alert_coverage.parquet']+[args.report/n for n in ['coverage_report.json','coverage_report.md']]
    inputs={args.alerts.resolve(),args.messages.resolve()}
    if len({p.resolve() for p in outputs})!=len(outputs) or any(p.resolve() in inputs for p in outputs):
        parser.error('Outputs must be distinct from normalized inputs')
    start=time.perf_counter()
    report={'task_status':'BLOCKED','input_sha256':{}}
    try:
        for key,path in [('alerts',args.alerts),('messages',args.messages)]:
            if not path.is_file():
                raise FileNotFoundError(f'Missing input: {path}')
            report['input_sha256'][key]=file_hash(path)
        tables=[pq.read_table(args.alerts),pq.read_table(args.messages)]
        for table,columns in zip(tables,[['start_time','end_time'],['message_time']]):
            for name in columns:
                if table.schema.field(name).type != TIMESTAMP:
                    raise ValueError('Expected normalized timestamp[us, UTC] schema')
        alerts,messages=[table.to_pylist() for table in tables]
        validate_h2(messages)
        links,coverage,result=integrate(alerts,messages)
        validate_links(links,coverage,alerts,messages)
        args.output.mkdir(parents=True,exist_ok=True)
        write_table(links,args.output/'alert_message_links.parquet',LINK_SCHEMA)
        write_table(coverage,args.output/'alert_coverage.parquet',COVERAGE_SCHEMA)
        for key,path in [('alerts',args.alerts),('messages',args.messages)]:
            if file_hash(path)!=report['input_sha256'][key]:
                raise ValueError('Normalized input changed during execution')
        result['input_sha256']=report['input_sha256']
        result['software_versions']={name:version(name) for name in ['kyiv-air-alert-analysis','pyarrow','tzdata']}
        result['input_hashes_unchanged']=True
        result['validation_checks']='passed: H2, foreign keys, membership, provenance, unique pairs, coverage counts, Parquet readback'
        report=result
    except (OSError,ValueError,TypeError,KeyError) as exc:
        report['error']=str(exc)
    report['elapsed_seconds']=round(time.perf_counter()-start,6)
    args.report.mkdir(parents=True,exist_ok=True)
    (args.report/'coverage_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=json_default)+'\n',encoding='utf-8')
    (args.report/'coverage_report.md').write_text(markdown(report),encoding='utf-8')
    print(f"Task 003: {report['task_status']}; links={report.get('total_temporal_links','unavailable')}; covered alerts={report.get('alerts_with_at_least_one_link','unavailable')}; seconds={report['elapsed_seconds']}")
    if 'error' in report:
        print(report['error'])
    return 0 if report['task_status']=='COMPLETE' else 1


if __name__=='__main__':
    raise SystemExit(main())
