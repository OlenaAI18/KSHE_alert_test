"""Small explicitly synthetic fixtures; no production exports are committed."""
import json
from pathlib import Path
from zipfile import ZipFile
import pytest
import pyarrow.parquet as pq
from kyiv_alerts.ingestion.alerts import parse_alerts, EXPECTED_REGION
from kyiv_alerts.ingestion.telegram import parse_telegram, safe_member
from kyiv_alerts.ingestion.timeutils import parse_time
from kyiv_alerts.ingestion.storage import write_parquet
from kyiv_alerts.ingestion.__main__ import main
from kyiv_alerts.validation.quality import audit_alerts, audit_telegram


def alert(uid='1', start='2024-01-01T23:30:00', end='2024-01-02T00:30:00', **extra):
    return {'uid':uid,'CATUTTC':EXPECTED_REGION,'addressPostName':'Київ',
            'type':'Повітряна тривога','cause':'null','level':None,
            'dateTimeStart':start,'dateTimeEnd':end,**extra}


def json_input(tmp_path, records):
    path=tmp_path/'alerts.json'
    path.write_text(json.dumps(records,ensure_ascii=False),encoding='utf-8')
    return path


def message(mid='1', text='Hello', timestamp='01.01.2024 12:00:00', classes='default', extra=''):
    date=f'<div class="date details" title="{timestamp}">12:00</div>' if timestamp is not None else ''
    content=f'<div class="text">{text}</div>' if text is not None else ''
    return f'<div class="message {classes}" id="message{mid}"><div class="body">{date}{content}{extra}</div></div>'


def archive(tmp_path, members):
    path=tmp_path/'telegram.zip'
    with ZipFile(path,'w') as z:
        for name,content in members.items():
            z.writestr(name,content)
    return path


def test_valid_alert_and_midnight(tmp_path):
    rows=parse_alerts(json_input(tmp_path,[alert(uid=12)]))
    assert rows[0]['source_uid']=='12'
    assert rows[0]['duration_minutes']==60
    assert rows[0]['validation_status']=='valid'
    assert rows[0]['start_time'].isoformat()=='2024-01-01T21:30:00+00:00'
    assert rows[0]['start_time_original']=='2024-01-01T23:30:00'
    assert json.loads(rows[0]['raw_record_json'])['level'] is None


def test_null_and_additional_fields(tmp_path):
    rows=parse_alerts(json_input(tmp_path,[alert(end='null',unknown={'value':7})]))
    assert rows[0]['source_cause'] is None
    assert rows[0]['end_time'] is None
    assert rows[0]['end_time_original']=='null'
    assert rows[0]['duration_minutes'] is None
    assert json.loads(rows[0]['raw_record_json'])['unknown']=={'value':7}
    assert audit_alerts(rows)['source_missing_or_null_fields']['cause']==1


@pytest.mark.parametrize('end',['2024-01-01T23:29:00','2024-01-01T23:30:00'])
def test_invalid_interval_retained(tmp_path,end):
    rows=parse_alerts(json_input(tmp_path,[alert(end=end)]))
    assert len(rows)==1 and 'end_not_after_start' in rows[0]['validation_status']
    assert rows[0]['duration_minutes'] is None


def test_duplicates_overlap_and_nested_intervals(tmp_path):
    rows=parse_alerts(json_input(tmp_path,[alert('1','2024-01-01T10:00:00','2024-01-01T14:00:00'),alert('1','2024-01-01T11:00:00','2024-01-01T12:00:00'),alert('3','2024-01-01T12:30:00','2024-01-01T13:00:00')]))
    q=audit_alerts(rows)
    assert q['duplicate_identifiers']=={'1':2}
    assert len(q['overlapping_interval_pairs'])==2
    assert len(rows)==3


def test_duplicate_records_and_intervals(tmp_path):
    rows=parse_alerts(json_input(tmp_path,[alert(),alert()]))
    q=audit_alerts(rows)
    assert len(q['duplicate_records'])==1 and len(q['duplicate_intervals'])==1


@pytest.mark.parametrize(('value','status'),[
    ('2024-03-31T03:30:00','nonexistent'),
    ('2024-10-27T03:30:00','ambiguous'),
    ('2024-03-31T02:30:00','valid'),
    ('2024-03-31T04:30:00','valid'),
    ('not a date','invalid'),(None,'missing'),('null','missing'),
    ('27.10.2024 03:30:00 UTC+03:00','valid_explicit_offset'),
    ('2024-10-27T03:30:00+02:00','valid_explicit_offset'),
])
def test_timestamp_cases(value,status):
    dt,actual=parse_time(value)
    assert actual==status
    assert (dt is not None)==status.startswith('valid')


def test_dst_elapsed_duration(tmp_path):
    rows=parse_alerts(json_input(tmp_path,[alert(start='2024-03-31T02:30:00',end='2024-03-31T04:30:00')]))
    assert rows[0]['duration_minutes']==60


def test_bad_record_and_geography_retained(tmp_path):
    rows=parse_alerts(json_input(tmp_path,[alert(CATUTTC='unexpected'),42]))
    q=audit_alerts(rows)
    assert q['unexpected_geographic_records']==[0,1]
    assert q['parse_errors']==1 and len(rows)==2


def test_alert_non_array(tmp_path):
    with pytest.raises(ValueError,match='JSON array'):
        parse_alerts(json_input(tmp_path,{}))


def test_telegram_entities_multiline_and_metadata(tmp_path):
    extra='<div class="forwarded"><div class="from_name">Original &amp; sender</div></div><div class="reply_to"><a href="messages2.html#go_to_message9">Reply</a></div><span class="edited" title="01.01.2024 13:00:00">edited</span>'
    path=archive(tmp_path,{'folder/messages.html':message(text='А &amp; Б<br>Next &lt;line&gt;',extra=extra),'media/image.jpg':b'not loaded','index.html':'<html>index</html>'})
    rows,meta=parse_telegram(path)
    assert rows[0]['text']=='А & Б\nNext <line>'
    assert rows[0]['message_id']=='1'
    assert rows[0]['forwarded_from']=='Original & sender'
    assert rows[0]['reply_to_message_id']=='9'
    assert rows[0]['edited_at']=='01.01.2024 13:00:00'
    assert meta['html_members_discovered']==2 and len(meta['message_html_files'])==1


def test_empty_service_and_continuation(tmp_path):
    html=message('1',None)+message('2','Joined',classes='service')+message('3','Continued',timestamp=None,classes='default joined')
    rows,meta=parse_telegram(archive(tmp_path,{'messages.html':html}))
    assert not rows[0]['has_text']
    assert rows[1]['is_service_message']
    assert rows[2]['message_time'] is None and rows[2]['text']=='Continued'
    assert audit_telegram(rows,meta)['records_without_text']==1


def test_service_body_without_text_class(tmp_path):
    html='<div class="message service" id="message-1"><div class="body details">1 January 2024</div></div>'
    rows,_=parse_telegram(archive(tmp_path,{'messages.html':html}))
    assert rows[0]['text']=='1 January 2024'
    assert rows[0]['message_time'] is None


def test_telegram_duplicates_and_conflict_trace(tmp_path):
    rows,meta=parse_telegram(archive(tmp_path,{'messages2.html':message('1','Changed'),'messages.html':message('1','Original')}))
    assert len(rows)==1 and rows[0]['text']=='Original'
    occurrence=meta['duplicate_identifier_occurrences'][0]
    assert occurrence['conflicting_content']
    assert occurrence['duplicate_record']['text']=='Changed'


def test_malformed_html_missing_metadata(tmp_path):
    html='<div class="message default"><div class="body"><div class="text">Unclosed &amp; body'
    rows,_=parse_telegram(archive(tmp_path,{'odd.html':html}))
    assert len(rows)==1 and rows[0]['message_id'] is None
    assert rows[0]['message_time'] is None
    assert rows[0]['text']=='Unclosed & body'


def test_deterministic_member_order_and_parquet(tmp_path):
    path=archive(tmp_path,{'z.html':message('2'),'a.html':message('1')})
    first,_=parse_telegram(path)
    second,_=parse_telegram(path)
    assert first==second and [r['message_id'] for r in first]==['1','2']
    out=tmp_path/'messages.parquet'
    write_parquet(first,out,'telegram')
    before=pq.read_table(out)
    write_parquet(second,out,'telegram')
    assert pq.read_table(out).equals(before)


def test_unsafe_zip_members_are_skipped(tmp_path):
    rows,meta=parse_telegram(archive(tmp_path,{'../messages.html':message(),'safe/messages.html':message('2')}))
    assert len(rows)==1 and meta['unsafe_html_members_skipped']==['../messages.html']
    assert not safe_member('C:\\messages.html')


def test_monthly_zero_counts_and_gap(tmp_path):
    rows=parse_alerts(json_input(tmp_path,[alert(start='2024-01-01T10:00:00',end='2024-01-01T11:00:00'),alert('2',start='2024-03-01T10:00:00',end='2024-03-01T11:00:00')]))
    q=audit_alerts(rows)
    assert q['monthly_record_counts']=={'2024-01':1,'2024-02':0,'2024-03':1}
    assert len(q['suspicious_gaps'])==1


def test_cli_both_outputs_and_reproducibility(tmp_path):
    alerts=json_input(tmp_path,[alert()])
    telegram=archive(tmp_path,{'messages.html':message()})
    args=['--alerts',str(alerts),'--telegram',str(telegram),'--output',str(tmp_path/'out'),'--report',str(tmp_path/'report')]
    original=[alerts.read_bytes(),telegram.read_bytes()]
    assert main(args)==0
    table=pq.read_table(tmp_path/'out/alerts.parquet')
    assert main(args)==0
    assert pq.read_table(tmp_path/'out/alerts.parquet').equals(table)
    assert original==[alerts.read_bytes(),telegram.read_bytes()]
    report=json.loads((tmp_path/'report/data_quality_report.json').read_text())
    assert report['task_status']=='COMPLETE'
    assert report['coverage_intersection'] is not None
    assert (tmp_path/'out/telegram_messages.parquet').exists()


def test_cli_partial_missing_source(tmp_path):
    alerts=json_input(tmp_path,[alert()])
    assert main(['--alerts',str(alerts),'--telegram',str(tmp_path/'absent.zip'),'--output',str(tmp_path/'out'),'--report',str(tmp_path/'report')])==1
    report=json.loads((tmp_path/'report/data_quality_report.json').read_text())
    assert report['task_status']=='PARTIALLY COMPLETE'
    assert report['sources']['telegram']['processing_status']=='BLOCKED'
    assert (tmp_path/'out/alerts.parquet').exists()


def test_cli_corrupt_zip(tmp_path):
    alerts=json_input(tmp_path,[alert()])
    zip_path=tmp_path/'broken.zip';zip_path.write_bytes(b'not a zip')
    assert main(['--alerts',str(alerts),'--telegram',str(zip_path),'--output',str(tmp_path/'out'),'--report',str(tmp_path/'report')])==1
    report=json.loads((tmp_path/'report/data_quality_report.json').read_text())
    assert report['sources']['telegram']['processing_status']=='FAILED'


def test_cli_protect_raw_input(tmp_path):
    alerts=json_input(tmp_path,[alert()])
    target=tmp_path/'alerts.parquet';target.write_bytes(alerts.read_bytes())
    with pytest.raises(SystemExit):
        main(['--alerts',str(target),'--telegram',str(tmp_path/'missing.zip'),'--output',str(tmp_path),'--report',str(tmp_path/'report')])
    assert target.read_bytes()==alerts.read_bytes()


def test_service_export_ids_are_not_genuine_message_ids(tmp_path):
    rows,metadata=parse_telegram(archive(tmp_path,{'a.html':message('-1','Heading',timestamp=None,classes='service'),'b.html':message('-1','Heading',timestamp=None,classes='service')}))
    assert len(rows)==2
    assert all(r['message_id'] is None and r['source_html_id']=='message-1' for r in rows)
    assert metadata['duplicate_identifier_occurrences']==[]


def test_parquet_empty_schema(tmp_path):
    output=tmp_path/'empty.parquet'
    write_parquet([],output,'telegram')
    table=pq.read_table(output)
    assert table.num_rows==0
    assert table.schema.field('message_time').type.tz=='UTC'


def test_telegram_posting_gap_and_dst_issue(tmp_path):
    rows,metadata=parse_telegram(archive(tmp_path,{'messages.html':message('1',timestamp='01.01.2024 12:00:00')+message('2',timestamp='04.01.2024 12:00:00')+message('3',timestamp='27.10.2024 03:30:00')}))
    quality=audit_telegram(rows,metadata)
    assert len(quality['large_posting_gaps'])==1
    assert len(quality['dst_ambiguous_records'])==1


def test_malformed_timestamp_field_remains_traceable(tmp_path):
    rows=parse_alerts(json_input(tmp_path,[alert(start={'unexpected':'object'},end=['bad'])]))
    assert len(rows)==1
    assert rows[0]['start_timestamp_status']=='invalid'
    assert audit_alerts(rows)['invalid_timestamps']==1
    output=tmp_path/'alerts.parquet'
    write_parquet(rows,output,'alerts')
    stored=pq.read_table(output).to_pylist()[0]
    assert json.loads(stored['start_time_original'])=={'unexpected':'object'}


def test_natural_export_page_order(tmp_path):
    path=archive(tmp_path,{'messages10.html':message('10',timestamp='10.01.2024 12:00:00'),'messages2.html':message('2',timestamp='02.01.2024 12:00:00'),'messages.html':message('1',timestamp='01.01.2024 12:00:00')})
    rows,metadata=parse_telegram(path)
    assert [r['message_id'] for r in rows]==['1','2','10']
    assert audit_telegram(rows,metadata)['timestamp_ordering_in_source']


def test_export_suffix_preserved_with_validated_kyiv_wall_clock(tmp_path):
    path=archive(tmp_path,{'messages.html':message('1',timestamp='01.08.2024 12:00:00 UTC+02:00')+message('-1','Date heading',timestamp=None,classes='service')})
    rows,metadata=parse_telegram(path)
    assert rows[0]['message_time'].isoformat()=='2024-08-01T09:00:00+00:00'
    assert rows[0]['message_time_original']=='01.08.2024 12:00:00 UTC+02:00'
    assert rows[0]['timestamp_status']=='valid_kyiv_wall_clock'
    quality=audit_telegram(rows,metadata)
    assert quality['explicit_export_offset_minutes_counts']=={120:1}
    assert quality['export_offsets_differing_from_kyiv_zone_records']==1
    assert quality['ordinary_messages_with_valid_timestamps']==1
    assert quality['service_messages_without_timestamps']==1
    assert quality['ordinary_message_date_parsing_success_rate']==1
