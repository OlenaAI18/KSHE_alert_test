"""Synthetic locality fixtures, never independent semantic validation labels."""
import json
from pathlib import Path
import pytest
import pyarrow.parquet as pq
from kyiv_alerts.classification.rules import Dictionary
from kyiv_alerts.classification.pipeline import process
from kyiv_alerts.classification.__main__ import validate_outputs,MARKER_SCHEMA,write_table
from test_classification import DICT,dataset

GEO=DICT.with_name('kyiv_geography.yaml')

@pytest.fixture
def expanded():return Dictionary(DICT,GEO)


@pytest.mark.parametrize(('text','uid'),[
 ('На Троєщину рухається БпЛА','troieshchyna'),
 ('БпЛА летить до Трої','troieshchyna'),
 ('Над Троещиной загроза БпЛА','troieshchyna'),
 ('На Оболоні рух шахедів','obolon'),
 ('БпЛА рухається над Жулянами','zhuliany'),
 ('У Теремках загроза шахедів','teremky'),
 ('До Позняків летить БпЛА','pozniaky'),
 ('ДВРЗ: загроза БпЛА','dvrz'),
 ('На Русанівку летить БпЛА','rusanivka'),
 ('Бортничі: рух БпЛА','bortnychi'),
 ('На Дорогожичах загроза БпЛА','dorohozhychi'),
 ('На Голосіїв рух БпЛА','holosiiv'),
 ('На Виноградарі загроза БпЛА','vynohradar'),
 ('Киев: загроза БпЛА','kyiv_city'),
 ('Харківський масив: рух БпЛА','kharkivskyi_masyv'),
])
def test_city_localities(expanded,text,uid):
    markers=expanded.classify(text)
    assert markers and markers[0]['geography']=='explicit_kyiv'
    assert markers[0]['accepted_for_aggregation']
    assert any(m['locality_id']==uid for m in markers[0]['geography_mentions'])
    assert markers[0]['classification_version']=='v1.1-geo'
    assert markers[0]['geography_dictionary_version']=='kyiv-geography-v1.0'


@pytest.mark.parametrize('text',['Вишгород: рух БпЛА','До Вишгорода летить БпЛА','Васильків: загроза БпЛА','Васік: рух БпЛА','Бориспіль: рух БпЛА','До Борисполя летить БпЛА','У Броварах загроза БпЛА','На Гостомель летить БпЛА','У Бучі загроза БпЛА','Обухів: загроза БпЛА','Біла Церква: рух БпЛА','БЦр: рух БпЛА','До Українки летить БпЛА','У Вишневому загроза БпЛА','На Ірпінь рух БпЛА'])
def test_suburbs_never_city(expanded,text):
    markers=expanded.classify(text)
    assert markers and markers[0]['geography']=='kyiv_region'
    assert not markers[0]['accepted_for_aggregation']
    assert markers[0]['geography_mentions']


@pytest.mark.parametrize('text',['Центр: рух БпЛА','Лівий берег: рух БпЛА','ЛБ: загроза БпЛА','Лісовий: рух БпЛА','Шевченківський р-н: загроза БпЛА','Борщага: рух БпЛА','Академ: рух БпЛА','Пуща: рух БпЛА'])
def test_common_names_require_anchor(expanded,text):
    markers=expanded.classify(text)
    assert markers[0]['geography']=='uncertain' and not markers[0]['accepted_for_aggregation']
    assert markers[0]['geography_mentions'][0]['resolution_status']=='needs_kyiv_anchor'


@pytest.mark.parametrize('text',['Київ: лівий берег, рух БпЛА','Оболонь, ЛБ: рух БпЛА','Київ: Шевченківський р-н, загроза БпЛА','Київ: Борщага, рух БпЛА','Київ: Академ, рух БпЛА','Лісовий масив: рух БпЛА'])
def test_anchored_common_names(expanded,text):
    marker=expanded.classify(text)[0]
    assert marker['geography']=='explicit_kyiv' and marker['accepted_for_aggregation']


@pytest.mark.parametrize('name',['Голосіївський','Дарницький','Деснянський','Дніпровський','Оболонський','Печерський','Подільський','Святошинський',"Солом'янський",'Шевченківський'])
def test_all_districts_and_abbreviations(expanded,name):
    marker=expanded.classify(f'Київ: {name} р-н, рух БпЛА')[0]
    assert marker['geography']=='explicit_kyiv'
    assert any(m['locality_type']=='administrative_district' for m in marker['geography_mentions'])


@pytest.mark.parametrize('settlement',['Софіївська Борщагівка','Петропавлівська Борщагівка'])
def test_longest_suburb_masks_nested_city_alias(expanded,settlement):
    marker=expanded.classify(f'{settlement}: рух БпЛА')[0]
    assert marker['geography']=='kyiv_region'
    assert len(marker['geography_mentions'])==1
    assert marker['geography_mentions'][0]['canonical_name']==settlement


def test_mixed_geography_and_fallback(expanded):
    mixed=expanded.classify('Троя та Вишгород: рух БпЛА')[0]
    assert mixed['geography']=='uncertain' and not mixed['accepted_for_aggregation']
    other=expanded.classify('Харків: рух БпЛА у Шевченківському районі')[0]
    assert other['geography']=='uncertain' and not other['accepted_for_aggregation']
    local=expanded.classify('Оболонь. Рух БпЛА.')[0]
    assert local['geography']=='explicit_kyiv' and local['geography_source']=='message_fallback'
    sentence=expanded.classify('Оболонь: рух БпЛА. Вишгород: рух шахедів.')
    assert [m['geography'] for m in sentence]==['explicit_kyiv','kyiv_region']


@pytest.mark.parametrize('text',['оболонськийгерой','троянський кінь','познякиXYZ','виноградарство','БПЛА рухається на НевідомеМісто'])
def test_boundaries_and_unknown_names(expanded,text):
    assert not any(m['geography']=='explicit_kyiv' for m in expanded.classify(text))


def test_geography_does_not_override_context(expanded):
    for text in ['Вчора на Оболоні рух БпЛА','Троя: відбій загрози БпЛА','На Жулянах можливий рух БпЛА','ДВРЗ: БпЛА']:
        markers=expanded.classify(text)
        assert markers and markers[0]['geography']=='explicit_kyiv'
        assert not markers[0]['accepted_for_aggregation']


def test_span_provenance_and_parquet_roundtrip(expanded,tmp_path):
    source=dataset(['На Троєщину рухається БпЛА. Над мостом Патона загроза шахедів.'])
    markers,features=process(*source,expanded)
    validate_outputs(markers,features,*source[:2],source[2],expanded)
    for m in markers:
        for location in m['geography_mentions']:
            text=source[1][0]['text']
            assert text[location['match_start']:location['match_end']]==location['matched_text']
    path=tmp_path/'m.parquet';write_table(markers,path,MARKER_SCHEMA)
    assert pq.read_table(path).to_pylist()==markers
    changed=[dict(m) for m in markers]
    changed[0]['geography_mentions']=[dict(x) for x in markers[0]['geography_mentions']]
    changed[0]['geography_mentions'][0]['matched_text']='different'
    with pytest.raises(ValueError):validate_outputs(changed,features,*source[:2],source[2],expanded)


def test_baseline_vs_expansion_same_threats_contexts(expanded):
    source=dataset(['На Оболоні рух БпЛА','Київ: загроза шахедів'])
    before,fb=process(*source,Dictionary(DICT))
    after,fa=process(*source,expanded)
    assert len(before)==len(after)
    for old,new in zip(before,after):
        for field in ['rule_id','category','subtype','match_start','match_end','matched_text','evidence_status','source_file','source_message_index']:
            assert old[field]==new[field]
    assert fb[0]['other'] is False and fa[0]['other'] is True
    assert fb[0]['shahed_uav']==fa[0]['shahed_uav']==True
    assert Dictionary(DICT).classify('Оболонь: рух БпЛА')[0]['geography']=='unspecified'


@pytest.mark.parametrize(('text','gained','lost'),[('Оболонь: рух БпЛА',1,0),('Київ: рух БпЛА до Вишгорода',0,1)])
def test_comparison_reports_gains_and_losses(expanded,text,gained,lost):
    from kyiv_alerts.classification.geography_review import compare,sample_changes
    source=dataset([text])
    before,fb=process(*source,Dictionary(DICT))
    after,fa=process(*source,expanded)
    r,changes=compare(before,after,fb,fa,source[1])
    assert len(r['gained_classified_alert_ids'])==gained
    assert len(r['lost_classified_alert_ids'])==lost
    assert r['after']['classified_alerts']-r['before']['classified_alerts']==gained-lost
    assert r['monthly_comparison'][0]['eligible_alerts']==1
    sample=sample_changes(changes,seed=11,target=180)
    assert sample==sample_changes(changes,seed=11,target=180)
    assert len(sample)==1
    assert all(not sample[0][k] for k in sample[0] if k.startswith('reviewer_'))
    assert sample[0]['matched_geography_names']


def test_comparison_rejects_context_or_identity_changes(expanded):
    from kyiv_alerts.classification.geography_review import compare
    source=dataset(['Оболонь: рух БпЛА'])
    before,fb=process(*source,Dictionary(DICT));after,fa=process(*source,expanded)
    after[0]['evidence_status']='historical_or_summary'
    with pytest.raises(ValueError):compare(before,after,fb,fa,source[1])
    with pytest.raises(ValueError):compare(before,[],fb,fa,source[1])


def test_expanded_cli_repeatability_and_geo_input_hash(tmp_path):
    from kyiv_alerts.classification.__main__ import main
    from kyiv_alerts.ingestion.storage import schema_for
    from kyiv_alerts.integration.__main__ import LINK_SCHEMA,COVERAGE_SCHEMA
    from kyiv_alerts.classification.geography_review import main as compare_main
    source=dataset(['На Оболонь рух БпЛА'])
    argv=[]
    for name,rows,schema in zip(['alerts','messages','links','coverage'],source,[schema_for('alerts'),schema_for('messages'),LINK_SCHEMA,COVERAGE_SCHEMA]):
        path=tmp_path/(name+'.parquet');write_table(rows,path,schema);argv+=['--'+name,str(path)]
    before=tmp_path/'before';after=tmp_path/'after';r=tmp_path/'r';br=tmp_path/'br'
    assert main(argv+['--dictionary',str(DICT),'--output',str(before),'--report',str(br)])==0
    assert main(argv+['--dictionary',str(DICT),'--geography',str(GEO),'--output',str(after),'--report',str(r)])==0
    frozen=pq.read_table(after/'message_threat_markers.parquet')
    assert main(argv+['--dictionary',str(DICT),'--geography',str(GEO),'--output',str(after),'--report',str(r)])==0
    assert frozen.equals(pq.read_table(after/'message_threat_markers.parquet'))
    report=json.loads((r/'classification_report.json').read_text())
    assert report['input_hashes_unchanged'] and 'geography' in report['input_sha256']
    assert report['classification_version']=='v1.1-geo'
    assert compare_main(['--before',str(before),'--after',str(after),'--messages',str(tmp_path/'messages.parquet'),'--report',str(r)])==0
    comparison=json.loads((r/'geography_expansion_report.json').read_text())
    assert comparison['before']['classified_alerts']==0 and comparison['after']['classified_alerts']==1
    assert comparison['reviewed_reference_examples']==0 and comparison['precision'] is None
    assert (r/'geography_review_sample.csv').is_file()
