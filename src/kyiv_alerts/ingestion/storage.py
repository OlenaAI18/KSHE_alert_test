"""Explicit Parquet schemas, including empty/partially invalid datasets."""
import json
import pyarrow as pa
import pyarrow.parquet as pq


def schema_for(kind):
    if kind == 'alerts':
        strings = ['alert_id','source_uid','source_region_code','source_region_name','alert_type','source_cause','start_time_original','end_time_original','validation_status','start_timestamp_status','end_timestamp_status','source_file','raw_record_json']
        fields = [(k,pa.string()) for k in strings] + [('start_time',pa.timestamp('us',tz='UTC')),('end_time',pa.timestamp('us',tz='UTC')),('duration_minutes',pa.float64()),('source_record_index',pa.int64())]
    else:
        strings = ['message_id','message_time_original','text','message_type','source_file','source_html_id','forwarded_from','reply_to_message_id','edited_at','parse_status','timestamp_status']
        fields = [(k,pa.string()) for k in strings] + [('message_time',pa.timestamp('us',tz='UTC')),('has_text',pa.bool_()),('is_service_message',pa.bool_()),('source_message_index',pa.int64())]
    return pa.schema(fields)


def write_parquet(rows, path, kind):
    schema = schema_for(kind)
    converted = []
    for row in rows:
        item = dict(row)
        for field in schema:
            value = item.get(field.name)
            if pa.types.is_string(field.type) and value is not None and not isinstance(value,str):
                item[field.name] = json.dumps(value,ensure_ascii=False,sort_keys=True)
        converted.append(item)
    table = pa.Table.from_pylist(converted,schema=schema)
    pq.write_table(table,path,compression='zstd')
    assert pq.read_table(path).equals(table)
