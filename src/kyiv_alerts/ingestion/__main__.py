"""Portable CLI; independent sources still run when the other is unavailable."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import platform
from importlib.metadata import version
from zipfile import BadZipFile
from .alerts import parse_alerts
from .telegram import parse_telegram
from .storage import write_parquet
from kyiv_alerts.validation.quality import audit_alerts, audit_telegram, json_default, markdown_report


def file_hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--alerts',type=Path,required=True)
    parser.add_argument('--telegram',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=Path('data/interim'))
    parser.add_argument('--report',type=Path,default=Path('reports/data_quality'))
    args=parser.parse_args(argv)
    # Outputs must never resolve to an input path.
    destinations=[args.output/'alerts.parquet',args.output/'telegram_messages.parquet']+[args.report/n for n in ['source_inventory.json','data_quality_report.json','data_quality_report.md']]
    if len({p.resolve() for p in destinations}) != len(destinations) or any(p.resolve() in {args.alerts.resolve(),args.telegram.resolve()} for p in destinations):
        parser.error('Output destinations must be distinct from raw inputs')
    args.output.mkdir(parents=True,exist_ok=True)
    args.report.mkdir(parents=True,exist_ok=True)
    inventory={'sources':{}}
    report={'task_status':'COMPLETE','sources':{},'coverage_intersection':None,
            'software_versions': {k: version(k) for k in ['kyiv-air-alert-analysis','lxml','pyarrow','tzdata']},
            'python_version': platform.python_version(),
            'telegram_timestamp_normalization_rule': 'fixed_02_kyiv_wall_clock_v1 (Task 002.1 H2)',
            'diagnostic_thresholds':{'short_duration_minutes':1,'long_duration_minutes':1440,'alert_gap_hours':168,'posting_gap_hours':24}}
    for name,path,filename in [('alerts',args.alerts,'alerts.parquet'),('telegram',args.telegram,'telegram_messages.parquet')]:
        start=time.perf_counter()
        entry={'file_name':path.name,'format':'JSON array' if name=='alerts' else 'Telegram HTML ZIP',
               'size_bytes':None,'sha256':None,'html_members_discovered':None,'message_html_files_parsed':None,
               'processing_status':'BLOCKED'}
        inventory['sources'][name]=entry
        source={'processing_status':'BLOCKED','output_generated':False,'stage_seconds':{}}
        report['sources'][name]=source
        try:
            if not path.is_file():
                raise FileNotFoundError(f'Input file unavailable: {path}')
            stage=time.perf_counter()
            entry.update(size_bytes=path.stat().st_size,sha256=file_hash(path))
            source['stage_seconds']['input_hash']=round(time.perf_counter()-stage,6)
            stage=time.perf_counter()
            if name=='alerts':
                rows=parse_alerts(path)
                source['stage_seconds']['parse']=round(time.perf_counter()-stage,6)
                stage=time.perf_counter()
                quality=audit_alerts(rows)
                fatal=not rows or not any(r['duration_minutes'] is not None for r in rows)
            else:
                rows,metadata=parse_telegram(path)
                source['stage_seconds']['parse']=round(time.perf_counter()-stage,6)
                stage=time.perf_counter()
                entry.update(html_members_discovered=metadata['html_members_discovered'],message_html_files_parsed=len(metadata['message_html_files']))
                source['html_inventory']=metadata
                quality=audit_telegram(rows,metadata)
                fatal=not rows or not any(r['message_time'] is not None and not r['is_service_message'] for r in rows) or bool(metadata['unsafe_html_members_skipped']) or any('error' in e for e in metadata['html_parse_errors'])
            source['quality']=quality
            source['stage_seconds']['audit']=round(time.perf_counter()-stage,6)
            stage=time.perf_counter()
            write_parquet(rows,args.output/filename,name)
            source['output_generated']=True
            source['output_file']=filename
            source['stage_seconds']['parquet_write_and_readback']=round(time.perf_counter()-stage,6)
            unchanged=file_hash(path)==entry['sha256']
            source['raw_input_unchanged']=unchanged
            if not unchanged:
                raise ValueError('Raw input hash changed during ingestion')
            status='FAILED' if fatal else 'PROCESSED'
            entry['processing_status']=source['processing_status']=status
        except (OSError,ValueError,TypeError,RuntimeError,BadZipFile) as exc:
            source['error']=str(exc)
            entry['processing_status']=source['processing_status']='BLOCKED' if isinstance(exc,FileNotFoundError) else 'FAILED'
        source['elapsed_seconds']=round(time.perf_counter()-start,6)
        if source['processing_status']!='PROCESSED':
            report['task_status']='PARTIALLY COMPLETE' if any(s['processing_status']=='PROCESSED' for s in report['sources'].values()) else 'BLOCKED'
        print(f"{name}: {source['processing_status']}; records={source.get('quality',{}).get('total_extracted_records','unavailable')}; seconds={source['elapsed_seconds']}")
    complete=all(s['processing_status']=='PROCESSED' for s in report['sources'].values())
    report['task_status']='COMPLETE' if complete else ('PARTIALLY COMPLETE' if any(s['processing_status']=='PROCESSED' for s in report['sources'].values()) else 'BLOCKED')
    if complete:
        a,b=(report['sources'][k]['quality'] for k in ['alerts','telegram'])
        if all(q['earliest_timestamp'] is not None for q in [a,b]):
            first=max(a['earliest_timestamp'],b['earliest_timestamp'])
            last=min(a['latest_interval_boundary'],b['latest_timestamp'])
            report['coverage_intersection']={'start':first,'end':last} if first<=last else {'empty':True}
    for name,value in [('source_inventory.json',inventory),('data_quality_report.json',report)]:
        (args.report/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=json_default)+'\n',encoding='utf-8')
    (args.report/'data_quality_report.md').write_text(markdown_report(report),encoding='utf-8')
    print(f"Task status: {report['task_status']}; reports: {args.report}")
    return 0 if complete else 1


if __name__=='__main__':
    raise SystemExit(main())
