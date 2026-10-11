"""Focused diagnostic correctness; no semantic label assertions."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import copy
import json
import pytest
from kyiv_alerts.pattern_discovery.core import (normalize_text,word_ngrams,population,POPULATIONS,PERIODS,period_for,frequency_analysis,group_similar)
from kyiv_alerts.pattern_discovery.pipeline import representative,baseline,october_review,discover_families
from kyiv_alerts.pattern_discovery.__main__ import main,write_csv
from kyiv_alerts.classification.geography import GeographyDictionary

UTC=timezone.utc
ROOT=Path(__file__).resolve().parents[1]


def feature(aid='a',specific=False,other=False,text=1,status=None):
    row=dict(alert_id=aid,start_time=datetime(2026,10,1,tzinfo=UTC),end_time=datetime(2026,10,1,1,tzinfo=UTC),
     classification_status=status or ('multiple_categories' if specific and other else 'classified' if specific or other else 'no_identifiable_marker' if text else 'no_linked_text'),
     telegram_text_message_count=text,telegram_message_count=text,historical_range_relation='within',coverage_status='covered' if text else 'no_messages_found',
     threat_combination='shahed_uav+other' if specific and other else 'shahed_uav' if specific else 'other' if other else 'unknown' if text else None,unknown=not(specific or other))
    for c in ['shahed_uav','jet_uav','ballistic_high_speed','cruise_missile','mig31','strategic_aviation']:row[c]=specific if c=='shahed_uav' else False
    row['other']=other
    return row


def record(aid,mid,text,pop='text_unclassified',month=10):
    return dict(alert_id=aid,message_id=mid,text=text,normalized_text=normalize_text(text),population=pop,
      alert_start_time=datetime(2026,month,1,tzinfo=UTC),message_time=datetime(2026,month,1,tzinfo=UTC),period=period_for(datetime(2026,month,1,tzinfo=UTC)),
      markers=[],message_time_original='original',source_file='source.html',source_message_index=1,current_classification='unknown',current_classification_status='no_identifiable_marker')


@pytest.mark.parametrize('text,expected',[
 ('БПЛА ТЕЦ-5','бпла тец 5'),('Зазимʼя—КИЇВ','зазим\'я київ'),('Ｒеактив ①','rеактив 1'),('ПОХ, КПІ, 1 на місто','пох кпі 1 на місто'),('', '')])
def test_unicode_analysis_normalization(text,expected):
    assert normalize_text(text)==expected


def test_short_words_preserved_and_stopwords_do_not_bridge():
    grams=word_ngrams('1 на пох і кпі')
    assert '1' in grams and 'пох' in grams and 'кпі' in grams and 'на пох' in grams
    assert 'і' not in grams and 'на' not in grams and 'пох кпі' not in grams


@pytest.mark.parametrize('specific,other,text,expected',[(True,False,1,0),(True,True,1,0),(False,True,1,1),(False,False,1,2),(False,False,0,3)])
def test_disjoint_populations(specific,other,text,expected):
    assert population(feature(specific=specific,other=other,text=text))==POPULATIONS[expected]


@pytest.mark.parametrize('status',['no_telegram_historical_coverage','unresolved_temporal_ambiguity','partial_historical_coverage'])
def test_unavailable_not_negative(status):
    f=feature(text=None,status=status);f['historical_range_relation']='outside'
    assert population(f)=='unavailable_or_unresolved'


def test_kyiv_calendar_period_boundary():
    assert period_for(datetime(2026,9,30,22,30,tzinfo=UTC))==PERIODS[-1]
    assert period_for(datetime(2026,7,31,22,30,tzinfo=UTC))==PERIODS[-2]
    assert period_for(datetime(2023,7,31,22,30,tzinfo=UTC))==PERIODS[0]
    assert period_for(datetime(2022,1,1,tzinfo=UTC))=='outside_requested_periods'


def test_unique_alert_support_beats_repeated_burst():
    rows=[record('burst',str(i),'повтор реактив') for i in range(20)]
    rows += [record(str(i),'r'+str(i),'бандероль') for i in range(3)]
    rows += [record('specific','s'+str(i),'реактив шахед','specific_classified') for i in range(3)]
    rows += [dict(record('dup','same','бандероль'),alert_id='x'),dict(record('dup','same','бандероль'),alert_id='y')]
    output,distinctive,meta=frequency_analysis(rows)
    by={r['ngram']:r for r in output}
    assert by['повтор']['unique_alert_support']==1
    assert by['бандероль']['unique_alert_support']==5
    assert by['бандероль']['unique_message_support']==4 # repeated ID only once
    assert output.index(by['бандероль'])<output.index(by['повтор'])
    assert by['реактив']['specific_alert_support']==1
    assert by['реактив']['target_alert_denominator']==6
    assert meta['sparse_nnz']>0 and meta['matrix_shape'][0]==len(rows)


def test_character_ngrams_lengths_and_months():
    rows=[record(str(i),str(i),'бандеролі',month=8+i%3) for i in range(6)]
    output,_,_=frequency_analysis(rows,'char')
    assert output and all(3<=len(r['ngram'])<=5 for r in output)
    assert all(sum(r['monthly_distribution'].values())==r['unique_alert_support'] for r in output)


def test_clustering_repeatable_and_duplicate_normalized_text_same_group():
    rows=[record(str(i%4),str(i),text) for i,text in enumerate(['Троя','троя','Оболонь','Реактив','реактив','Бандероль','ДВРЗ'])]
    a,b,meta=group_similar(rows,groups=3)
    a2,b2,meta2=group_similar(rows,groups=3)
    assert (a,b,meta)==(a2,b2,meta2)
    assert a[0]['cluster_id']==a[1]['cluster_id']
    assert meta['max_pairwise_matrix']=='none'
    assert all(-.0001<=x['cosine_to_centroid']<=1.0001 for x in a)


def test_empty_frequency_and_grouping():
    assert frequency_analysis([])==([],{},None)
    assert group_similar([])==([],[],{'groups':0})


def test_representative_spans_time_and_preserves_full_text():
    rows=[dict(record(str(i),str(i),'Оригінальний текст\n'+str(i)),message_time=datetime(2026,10,1,0,0,i,tzinfo=UTC)) for i in range(30)]
    selected=representative(rows)
    assert len(selected)==5 and len({r['alert_id'] for r in selected})==5
    assert [r['message_id'] for r in selected]==['0','7','14','22','29']
    assert all('\n' in r['text'] for r in selected)


def test_catalog_diagnostic_only_and_no_cross_message_inference():
    geo=GeographyDictionary(ROOT/'config/kyiv_geography_v1_1.yaml')
    rows=[record('a','1','Троя'),record('a','2','Реактив берковець'),record('b','3','Зʼявились 2 бандеролі'),record('c','4','Буча'),record('d','5','ще один на місто')]
    saved=copy.deepcopy(rows)
    patterns,examples,assign=discover_families(rows,geo)
    assert 'P01' in rows[0]['pattern_ids'] and 'P01' in rows[3]['pattern_ids'] # city/oblast both are diagnostic only
    assert 'P06' in rows[1]['pattern_ids'] and 'P07' in rows[2]['pattern_ids'] and 'P04' in rows[4]['pattern_ids']
    assert all(r['current_classification']=='unknown' and not r['markers'] for r in rows)
    assert all(p['human_decision']==p['review_notes']=='' for p in patterns)
    assert all(e['human_decision']==e['review_notes']=='' for e in examples)
    assert any(e['requires_context_review'] for e in examples)
    assert all({k:v for k,v in r.items() if k!='pattern_ids'}==original for r,original in zip(rows,saved))


def test_october_exhaustive_and_blank_human_fields():
    features=[feature('a'),feature('b',other=True),feature('c',text=0)]
    rows={'a':[record('a','1','Троя')],'b':[record('b','2','БПЛА')],'c':[]}
    out=october_review(features,rows)
    assert len(out)==3 and sum(r['linked_text_count'] for r in out)==2
    assert all(r['review_status']==r['human_decision']==r['review_notes']=='' for r in out)
    assert any(r['population']=='unavailable_or_unresolved' and r['linked_text_count']==0 for r in out)


def test_missing_current_inputs_blocked(tmp_path):
    output=tmp_path/'report'
    assert main(['--root',str(tmp_path),'--report',str(output)])==1
    r=json.loads((output/'pattern_discovery_report.json').read_text())
    assert r['task_status']=='BLOCKED'
    assert not (output/'candidate_patterns.csv').exists()


def test_report_collision_with_protected_directory(tmp_path):
    with pytest.raises(SystemExit):main(['--root',str(tmp_path),'--report',str(tmp_path/'data')])


def test_csv_preserves_original_multiline_and_blank_fields(tmp_path):
    import csv
    rows=[dict(original_text='Київ\n"БПЛА"',human_decision='',evidence=['Пуск'])]
    p=tmp_path/'sample.csv';write_csv(p,rows)
    with p.open(encoding='utf-8-sig',newline='') as f:out=list(csv.DictReader(f))
    assert out[0]['original_text']==rows[0]['original_text'] and out[0]['human_decision']==''
    assert json.loads(out[0]['evidence'])==['Пуск']


def test_analysis_noise_removed_without_losing_short_forms():
    raw='Реактив на ТЕЦ 5\nhttps://send.monobank.ua/jar/abcdef 1234567890123456\n✙ Український Єнот ✙ Підтримати канал ✙'
    normalized=normalize_text(raw)
    assert normalized=='реактив на тец 5'
    assert 'https' in raw and '1234567890123456' in raw # source immutable


def test_groups_only_stopwords_small_corpus():
    assigned,groups,meta=group_similar([record('a','1','на'),record('b','2','до'),record('c','3','у')],groups=2)
    assert len(assigned)==3 and groups and meta['word_features']==0


def test_grouped_bank_card_removed_but_year_and_small_counts_retained():
    assert normalize_text('4441 1111 2700 5449 Київ 2026 1 на місто')=='київ 2026 1 на місто'


@pytest.fixture
def reviewed_inputs():
    from test_classification import dataset
    from kyiv_alerts.classification.rules import Dictionary
    from kyiv_alerts.classification.pipeline import process
    source=dataset(['Троя','Реактив берковець','Київ: БпЛА','Зʼявились 2 бандеролі'])
    dictionary=Dictionary(ROOT/'config/threat_dictionary_v1_1.yaml',ROOT/'config/kyiv_geography_v1_1.yaml')
    markers,features=process(*source,dictionary)
    return dict(zip(['alerts','messages','links','coverage'],source),features=features,markers=markers)


def test_prepare_preserves_records_and_links(reviewed_inputs):
    from kyiv_alerts.pattern_discovery.pipeline import prepare
    saved=copy.deepcopy(reviewed_inputs)
    records,byalert,fm=prepare(**reviewed_inputs)
    assert len(records)==4 and len(byalert['a'])==4
    assert reviewed_inputs==saved
    assert {r['message_id'] for r in records}=={l['message_id'] for l in saved['links']}


@pytest.mark.parametrize('fault',['stale_version','span','unlinked','coverage_count','category'])
def test_prepare_refuses_corrupt_or_stale_baseline(reviewed_inputs,fault):
    from kyiv_alerts.pattern_discovery.pipeline import prepare
    if fault=='stale_version':reviewed_inputs['features'][0]['classification_version']='v1.1-geo'
    elif fault=='span':reviewed_inputs['markers'][0]['matched_text']='invented'
    elif fault=='unlinked':reviewed_inputs['markers'][0]['message_id']='not_linked'
    elif fault=='coverage_count':reviewed_inputs['coverage'][0]['deterministic_text_message_count']=99
    elif fault=='category':reviewed_inputs['features'][0]['shahed_uav']=True
    with pytest.raises(ValueError):prepare(**reviewed_inputs)


def test_full_synthetic_cli_reports_and_input_immutability(tmp_path,reviewed_inputs):
    import shutil
    import pyarrow as pa
    import pyarrow.parquet as pq
    from kyiv_alerts.classification.pipeline import diagnostics
    from kyiv_alerts.ingestion.__main__ import file_hash
    root=tmp_path/'repo';out=root/'reports/pattern_discovery'
    paths={k:root/p for k,p in dict(alerts='data/interim/alerts.parquet',messages='data/interim/telegram_messages.parquet',links='data/processed/alert_message_links.parquet',coverage='data/processed/alert_coverage.parquet',features='data/processed/classification_v1_2/alert_threat_features.parquet',markers='data/processed/classification_v1_2/message_threat_markers.parquet').items()}
    for k,p in paths.items():p.parent.mkdir(parents=True,exist_ok=True);pq.write_table(pa.Table.from_pylist(reviewed_inputs[k]),p)
    (root/'config').mkdir()
    for name,k in [('threat_dictionary_v1_1.yaml','dictionary'),('kyiv_geography_v1_1.yaml','geography')]:
        p=root/'config'/name;shutil.copy(ROOT/'config'/name,p);paths[k]=p
    reportdir=root/'reports/classification_v1_2';reportdir.mkdir(parents=True)
    report=diagnostics(reviewed_inputs['features'],reviewed_inputs['markers'],reviewed_inputs['messages'],reviewed_inputs['links'])
    report['classification_version']='v1.2-reviewed-rules';report['input_sha256']={k:file_hash(p) for k,p in paths.items() if k in ['alerts','messages','links','coverage','dictionary','geography']}
    (reportdir/'classification_report.json').write_text(json.dumps(report))
    (reportdir/'reviewed_rules_report.json').write_text(json.dumps(dict(after=dict(eligible_alerts=1),input_sha256=dict(after_alert_threat_features=file_hash(paths['features']),after_message_threat_markers=file_hash(paths['markers'])))))
    frozen={p:p.read_bytes() for p in paths.values()}
    argv=['--root',str(root),'--report',str(out),'--groups','2']
    assert main(argv)==0
    expected={p.name:p.read_bytes() for p in out.glob('*.csv')}
    result=json.loads((out/'pattern_discovery_report.json').read_text())
    assert result['baseline']['total_alerts']==1 and result['input_hashes_unchanged']
    assert result['baseline']['populations']=={'other_only':1}
    assert main(argv)==0
    assert expected=={p.name:p.read_bytes() for p in out.glob('*.csv')}
    assert frozen=={p:p.read_bytes() for p in paths.values()}
