"""Synthetic rule/aggregation fixtures; no fabricated human reference labels."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import csv
import json
from pathlib import Path
import pytest
import pyarrow.parquet as pq
from kyiv_alerts.classification.rules import Dictionary,CATEGORIES
from kyiv_alerts.classification.pipeline import process,diagnostics,review_sample
from kyiv_alerts.classification.__main__ import main,validate_outputs
from kyiv_alerts.integration.linking import integrate
from kyiv_alerts.integration.__main__ import write_table,LINK_SCHEMA,COVERAGE_SCHEMA
from kyiv_alerts.ingestion.storage import schema_for

DICT=Path(__file__).resolve().parents[1]/'config/threat_dictionary.yaml'
BASE=datetime(2024,1,1,10,tzinfo=timezone.utc)

@pytest.fixture
def dictionary():return Dictionary(DICT)


def a(aid='a',start=BASE,end=BASE+timedelta(hours=1)):
    return dict(alert_id=aid,start_time=start,end_time=end,duration_minutes=(end-start).total_seconds()/60 if end else None,start_time_original=start.isoformat(),end_time_original=end.isoformat() if end else None,validation_status='valid')


def m(text,mid='m',instant=BASE+timedelta(minutes=10)):
    return dict(message_id=mid,message_time=instant,message_time_original=instant.isoformat(),text=text,has_text=bool(text and text.strip()),is_service_message=False,source_file='synthetic/messages.html',source_message_index=2,timestamp_status='valid_explicit_offset')


def dataset(texts=None,alerts=None):
    alerts=alerts or [a()]
    messages=[m(t,str(i)) for i,t in enumerate(texts or [])]+[m('Outside','before',BASE-timedelta(days=1)),m('Outside','after',BASE+timedelta(days=1))]
    links,coverage,_=integrate(alerts,messages)
    return alerts,messages,links,coverage


def accepted(d,text):return [r for r in d.classify(text) if r['accepted_for_aggregation']]


@pytest.mark.parametrize(('text','cat','sub'),[
 ('Київ: загроза Shahed-136','shahed_uav','shahed'),
 ('Київ: рух шахедів','shahed_uav','shahed'),
 ('Київ: загроза герані','shahed_uav','geran'),
 ('Київ: рух ударних БпЛА','shahed_uav','attack_uav'),
 ('Київ: рух дронів-камікадзе','shahed_uav','attack_uav'),
 ('Київ: загроза реактивний БпЛА','jet_uav','jet_attack_uav'),
 ('Київ: Shahed-238 рухається','jet_uav','shahed_238'),
 ('Київ: балістична загроза','ballistic_high_speed','ballistic'),
 ('Київ: загроза Іскандер-М','ballistic_high_speed','iskander_m'),
 ('Київ: загроза KN-23','ballistic_high_speed','kn23'),
 ('Київ: загроза Кинджал','ballistic_high_speed','kinzhal'),
 ('Київ: загроза Циркон','ballistic_high_speed','zircon'),
 ('Київ: рух крилатих ракет','cruise_missile','cruise'),
 ('Київ: загроза Х-101','cruise_missile','kh101'),
 ('Київ: загроза Kh-555','cruise_missile','kh555'),
 ('Київ: загроза Калібр','cruise_missile','kalibr'),
 ('Київ: загроза Іскандер-К','cruise_missile','iskander_k'),
 ('Київ: загроза X-59','cruise_missile','kh59'),
 ('Київ: загроза Х-69','cruise_missile','kh69'),
 ('Київ: зліт МіГ-31К','mig31','mig31k'),
 ('Київ: зліт МиГ-31К','mig31','mig31k'),
 ('Київ: зліт MIG-31K','mig31','mig31k'),
 ('Київ: активність стратегічної авіації','strategic_aviation','strategic'),
 ('Київ: зліт Ту-95МС','strategic_aviation','tu95ms'),
 ('Київ: зліт Tu-160','strategic_aviation','tu160'),
 ('Київ: зліт Ту-22М3','strategic_aviation','tu22m3'),
 ('Київ: рух БпЛА','other','generic_uav'),
 ('Київ: ракета летить','other','unspecified_missile'),
])
def test_categories_variants_subtypes(dictionary,text,cat,sub):
    hits=accepted(dictionary,text)
    assert any(r['category']==cat and r['subtype']==sub for r in hits)
    assert all(r['dictionary_version']=='v1.0' for r in hits)


@pytest.mark.parametrize('text',['Цирконієва голова','Шахедобан','суперShahedXYZ','МіГ-29','МіГ-31','MIG-31KD','Х-1010','Ту-1600','зліт МіГа'])
def test_boundaries_and_ambiguous_aircraft(dictionary,text):
    assert not accepted(dictionary,'Київ: загроза '+text)


def test_multi_label_and_order(dictionary):
    source=dataset(['Київ: загроза Кинджал та шахеди','Київ: зліт MIG-31K'])
    markers,features=process(*source,dictionary)
    f=features[0]
    assert f['threat_combination']=='shahed_uav+ballistic_high_speed+mig31'
    assert f['classification_status']=='multiple_categories'
    assert f['marker_evidence_count']==3
    assert f['explicit_cause_categories']==[]
    validate_outputs(markers,features,*source[:2],source[2],dictionary)


@pytest.mark.parametrize('text',['Київ: відбій загрози шахедів','Київ: загрози немає, шахеди','Київ: шахедів немає','Київ: МіГ-31К не злетів','Київ: ракетних пусків немає, Х-101'])
def test_negation(dictionary,text):
    markers=dictionary.classify(text)
    assert markers and not accepted(dictionary,text)
    assert any(r['evidence_status']=='negated_or_cancelled' for r in markers)


def test_no_launch_required(dictionary):
    hits=accepted(dictionary,'Київ: зліт МіГ-31К без пусків')
    assert [r['category'] for r in hits]==['mig31']


@pytest.mark.parametrize('text',['Вчора Київ: рух шахедів','Підсумки за ніч: Київ, балістика','За добу: Київ, загроза Калібр'])
def test_historical(dictionary,text):
    assert dictionary.classify(text)
    assert all(r['evidence_status']=='historical_or_summary' for r in dictionary.classify(text))
    assert not accepted(dictionary,text)


def test_explicit_cause_vs_explanation(dictionary):
    hits=accepted(dictionary,'Тривогу по країні оголошено через зліт МіГ-31К.\nМіГ-31К — носій ракети Кинджал.')
    assert len(hits)==1 and hits[0]['category']=='mig31'
    assert hits[0]['evidence_status']=='explicit_alert_cause'
    source=dataset(['Київ: причина тривоги — балістична загроза'])
    _,features=process(*source,dictionary)
    assert features[0]['explicit_cause_categories']==['ballistic_high_speed']


def test_generic_uav_and_jet_no_double_count(dictionary):
    assert {r['category'] for r in accepted(dictionary,'Київ: рух дронів')}=={'other'}
    assert {r['category'] for r in accepted(dictionary,'Київ: загроза реактивний шахед')}=={'jet_uav'}
    assert {r['category'] for r in accepted(dictionary,'Київ: загроза Shahed-238')}=={'jet_uav'}
    assert {r['category'] for r in accepted(dictionary,'Київ: рух ударний БпЛА')}=={'shahed_uav'}
    assert any(r['exclusion_reason'] and 'overlapping_specific_rule' in r['exclusion_reason'] for r in dictionary.classify('Київ: рух ударний БпЛА'))


@pytest.mark.parametrize(('text','geo','included'),[
 ('Київ: рух шахедів','explicit_kyiv',True),
 ('Київська область: рух шахедів','kyiv_region',False),
 ('Київщина: рух шахедів','kyiv_region',False),
 ('Київ обл.: рух шахедів','kyiv_region',False),
 ('Одеса: рух шахедів','other_region',False),
 ('По всій Україні загроза шахедів','nationwide',True),
 ('Загроза шахедів','unspecified',False),
 ('Київ та Одеса: рух шахедів','uncertain',False),
 ('Чернігів: шахеди рухаються на Київ','uncertain',False),
])
def test_geography(dictionary,text,geo,included):
    hits=dictionary.classify(text)
    assert hits and hits[0]['geography']==geo
    assert bool(accepted(dictionary,text))==included


def test_sentence_geography_over_message(dictionary):
    hits=dictionary.classify('Київ: рух шахедів. Одеса: загроза Калібр.')
    assert hits[0]['geography']=='explicit_kyiv' and hits[0]['accepted_for_aggregation']
    assert hits[-1]['geography']=='other_region' and not hits[-1]['accepted_for_aggregation']


@pytest.mark.parametrize('text',[None,'','   '])
def test_missing_text(dictionary,text):
    assert dictionary.classify(text)==[]
    _,f=process(*dataset([text]),dictionary)
    assert f[0]['classification_status']=='no_linked_text'
    assert f[0]['shahed_uav'] is None and f[0]['marker_evidence_count'] is None


def test_unknown_available_not_absence(dictionary):
    _,f=process(*dataset(['Невизначена інформація']),dictionary)
    assert f[0]['classification_status']=='no_identifiable_marker'
    assert f[0]['unknown'] and f[0]['shahed_uav'] is False
    assert f[0]['marker_evidence_count']==0


def test_uncovered_dst_retained(dictionary):
    alerts=[a('old',BASE-timedelta(days=4),BASE-timedelta(days=3)),a('normal'),a('dst',BASE+timedelta(days=2),None)]
    source=dataset(['Київ: зліт МіГ-31К'],alerts)
    markers,features=process(*source,dictionary)
    assert len(features)==len(alerts)
    byid={f['alert_id']:f for f in features}
    assert byid['old']['classification_status']=='no_telegram_historical_coverage'
    assert byid['dst']['classification_status']=='unresolved_temporal_ambiguity'
    for aid in ['old','dst']:
        assert byid[aid]['mig31'] is None and byid[aid]['marker_evidence_count'] is None
        assert byid[aid]['explicit_cause_categories'] is None
        assert byid[aid]['unknown']
    assert byid['dst']['end_time'] is None


def test_original_spans_dash_normalization(dictionary):
    text='КИЇВ: загроза МІГ–31К та Shahed‑238'
    hits=dictionary.classify(text)
    assert {r['category'] for r in accepted(dictionary,text)}=={'mig31','jet_uav'}
    for r in hits:assert text[r['match_start']:r['match_end']]==r['matched_text']


def test_repeatability_and_review_sample(dictionary):
    source=dataset(['Київ: зліт МіГ-31К','Київ: рух шахедів','Київ: відбій загрози БпЛА','Вчора Київ: балістична загроза','Невизначене повідомлення'])
    one=process(*source,dictionary)
    two=process(*[list(reversed(rows)) for rows in source],dictionary)
    assert one==two
    sample=review_sample(source[1],source[2],*one,seed=7,target=5)
    assert sample==review_sample(source[1],source[2],*two,seed=7,target=5)
    assert len(sample)==5 and len({(r['alert_id'],r['message_id']) for r in sample})==5
    assert all(not r[k] for r in sample for k in r if k.startswith('reviewer_'))
    report=diagnostics(one[1],one[0],source[1],source[2])
    assert report['unique_processed_messages']==5 and report['multi_label_alerts']==1
    assert report['messages_with_candidate_markers']==4 and report['messages_with_accepted_markers']==2
    assert report['monthly_classification_coverage'][0]['classified_share_of_eligible']==1


@pytest.mark.parametrize('defect',['duplicate_link','bad_message_provenance','bad_alert_bounds','duplicate_message','coverage_counts'])
def test_input_integrity(dictionary,defect):
    source=[deepcopy(rows) for rows in dataset(['Київ: зліт МіГ-31К'])]
    if defect=='duplicate_link':source[2].append(dict(source[2][0]))
    if defect=='bad_message_provenance':source[2][0]['source_file']='different'
    if defect=='bad_alert_bounds':source[2][0]['alert_end_time']+=timedelta(seconds=1)
    if defect=='duplicate_message':source[1].append(dict(source[1][0]))
    if defect=='coverage_counts':source[3][0]['deterministic_message_count']+=1
    with pytest.raises(ValueError):process(*source,dictionary)


def test_output_integrity(dictionary):
    source=dataset(['Київ: зліт МіГ-31К'])
    markers,features=process(*source,dictionary)
    markers[0]['matched_text']='different'
    with pytest.raises(ValueError):validate_outputs(markers,features,*source[:2],source[2],dictionary)


def test_invalid_dictionary(tmp_path):
    import yaml
    config=yaml.safe_load(DICT.read_text())
    config['rules'].append(config['rules'][0])
    path=tmp_path/'dict.yaml';path.write_text(yaml.safe_dump(config))
    with pytest.raises(ValueError):Dictionary(path)


def test_cli_immutable_idempotent(tmp_path):
    source=dataset(['Київ: зліт МіГ-31К','Невизначене повідомлення'])
    names=['alerts','messages','links','coverage']
    schemas=[schema_for('alerts'),schema_for('messages'),LINK_SCHEMA,COVERAGE_SCHEMA]
    argv=[]
    hashes=[]
    for rows,name,schema in zip(source,names,schemas):
        path=tmp_path/(name+'.parquet');write_table(rows,path,schema)
        hashes.append(path.read_bytes());argv+=['--'+name,str(path)]
    out=tmp_path/'output';report=tmp_path/'report'
    argv+=['--dictionary',str(DICT),'--output',str(out),'--report',str(report),'--sample-size','2']
    assert main(argv)==0
    table=pq.read_table(out/'alert_threat_features.parquet')
    markers=pq.read_table(out/'message_threat_markers.parquet')
    sample=(report/'validation_sample.csv').read_bytes()
    assert main(argv)==0
    assert table.equals(pq.read_table(out/'alert_threat_features.parquet'))
    assert markers.equals(pq.read_table(out/'message_threat_markers.parquet'))
    assert sample==(report/'validation_sample.csv').read_bytes()
    assert hashes==[(tmp_path/(name+'.parquet')).read_bytes() for name in names]
    r=json.loads((report/'classification_report.json').read_text())
    assert r['reviewed_reference_examples']==0 and r['precision'] is None and r['recall'] is None
    assert r['input_hashes_unchanged'] and r['task_status']=='TECHNICALLY COMPLETE'
    assert r['semantic_validation_status']=='PROVISIONAL — HUMAN VALIDATION REQUIRED'


def test_cli_missing_inputs(tmp_path):
    assert main(['--alerts',str(tmp_path/'absent'),'--report',str(tmp_path/'r')])==1
    assert json.loads((tmp_path/'r'/'classification_report.json').read_text())['task_status']=='BLOCKED'


def test_generic_specific_family_separate_spans(dictionary):
    assert {r['category'] for r in accepted(dictionary,'Київ: рух БпЛА Shahed-136')}=={'shahed_uav'}
    assert {r['category'] for r in accepted(dictionary,'Київ: ракета Х-101 летить')}=={'cruise_missile'}
    hits=dictionary.classify('Київ: ракета Х-101 летить')
    assert any('specific_family_in_clause' in (r['exclusion_reason'] or '') for r in hits)


@pytest.mark.parametrize('text',['Київ: потенційно Кинджал в повітрі','Так нагнітають ніби на Київ летить Калібр','Київ: шахеди можуть становити загрозу'])
def test_uncertain_language(dictionary,text):
    hits=dictionary.classify(text)
    assert hits and all(r['evidence_status']=='uncertain' for r in hits)
    assert not accepted(dictionary,text)


def test_kyiv_inflections_and_denied_direction(dictionary):
    hits=accepted(dictionary,'Шахеди рухаються до Києва')
    assert hits and hits[0]['geography']=='explicit_kyiv'
    assert not accepted(dictionary,'БпЛА рухається не на Київ')


def test_empty_marker_schema_and_output_protection(tmp_path):
    import pyarrow as pa
    from kyiv_alerts.classification.__main__ import MARKER_SCHEMA,FEATURE_SCHEMA
    path=tmp_path/'empty.parquet'
    write_table([],path,MARKER_SCHEMA)
    assert pq.read_table(path).schema==MARKER_SCHEMA
    assert pa.types.is_boolean(FEATURE_SCHEMA.field('unknown').type)
    with pytest.raises(SystemExit):main(['--alerts',str(tmp_path/'message_threat_markers.parquet'),'--output',str(tmp_path)])
