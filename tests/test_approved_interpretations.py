"""User-approved rule regression cases; not independent population accuracy labels."""
from pathlib import Path
import pytest
from kyiv_alerts.classification.rules import Dictionary
from kyiv_alerts.classification.pipeline import process
from kyiv_alerts.classification.__main__ import validate_outputs
from test_classification import dataset,DICT

NEW_DICT=DICT.with_name('threat_dictionary_v1_1.yaml')
NEW_GEO=DICT.with_name('kyiv_geography_v1_1.yaml')

@pytest.fixture
def reviewed():return Dictionary(NEW_DICT,NEW_GEO)


def accepted(dictionary,text):return [m for m in dictionary.classify(text) if m['accepted_for_aggregation']]


@pytest.mark.parametrize(('text','category'),[
 ('Троя бпла','other'),('ДВРЗ бпла','other'),('Центр бпла','other'),
 ('Оболонь, шах','shahed_uav'),('Жуляни, шах','shahed_uav'),
 ('5 шахедів від Вишгорода на Київ','shahed_uav'),
 ('БпЛА від Борисполя на столицю','other'),
 ('Тривога в Києві через бпла біля Чабанів','other'),
 ('Пуск Кинджалу','ballistic_high_speed'),
 ('Київ: реактивний','shahed_uav'),
 ('Центр, знов реактивний','shahed_uav'),
 ('Київ: ймовірно Кинджал','ballistic_high_speed'),
 ('Київ увага, з обох сторін крилаті + в повітрі потенційно Кинджал!!!','cruise_missile'),
 ('Київ увага, з обох сторін крилаті + в повітрі потенційно Кинджал!!!','ballistic_high_speed'),
])
def test_authorized_positive_rules(reviewed,text,category):
    markers=accepted(reviewed,text)
    assert any(m['category']==category for m in markers)
    assert all(m['dictionary_version']=='v1.1' and m['classification_version']=='v1.2-reviewed-rules' for m in markers)


@pytest.mark.parametrize('text',[
 'Буча бпла','БпЛА від Києва на Бучу','Буча, ймовірно шах','Вишгород шах',
 'Вчора Троя бпла','Центр: відбій загрози шахедів','Київ: шахедів немає',
 'Завтра Київ, шах','Київ: МіГ-31К носій Кинджалу','Київ: реактивний двигун',
 'Київ: реактивний вогнемет','Київ: реактивний снаряд','Київ: якщо буде пуск Кинджалу',
 'Пуск Кинджалу на Харків','Київ: пусків Кинджалу немає','Київ: БпЛА летить не на Київ',
 'Київ: збір на БпЛА','Київ: можливо навчання по БпЛА','МіГ-29','шахматист на Оболоні',
])
def test_authorized_limits_negation_history_and_unrelated_language(reviewed,text):
    assert not accepted(reviewed,text)


def test_literal_geography_and_relevance_separate(reviewed):
    marker=accepted(reviewed,'5 шахедів від Вишгорода на Київ')[0]
    assert marker['geography']=='uncertain' and marker['relevant_to_kyiv']
    assert marker['relevance_rule_id']=='user.toward_kyiv'
    assert {m['category'] for m in marker['geography_mentions']}=={'explicit_kyiv','kyiv_region'}
    cause=accepted(reviewed,'Тривога в Києві через бпла біля Чабанів')[0]
    assert cause['evidence_status']=='explicit_alert_cause' and cause['relevance_rule_id']=='user.kyiv_alert_cause'
    launch=accepted(reviewed,'Пуск Кинджалу')[0]
    assert launch['geography']=='unspecified' and launch['relevance_rule_id']=='user.kinzhal_launch_warning'
    assert launch['geography_mentions']==[]


def test_short_context_promotion_and_probability_retained(reviewed):
    short=accepted(reviewed,'Троя бпла')[0]
    assert short['context_status_original']=='uncertain' and short['evidence_status']=='current_threat'
    assert short['context_rule_id']=='user.locality_threat_bulletin' and not short['uncertainty_flag']
    uncertain=accepted(reviewed,'Київ: ймовірно Кинджал')[0]
    assert uncertain['evidence_status']=='uncertain' and uncertain['uncertainty_flag']
    assert uncertain['evidence_qualifiers']==['ймовірно']
    source=dataset(['Тривога в Києві, ймовірно через Кинджал'])
    _,features=process(*source,reviewed)
    assert features[0]['ballistic_high_speed'] is True
    assert features[0]['explicit_cause_categories']==[]


def test_generic_uav_not_shahed_and_explicit_jet_preserved(reviewed):
    assert {m['category'] for m in accepted(reviewed,'Троя бпла')}=={'other'}
    assert {m['category'] for m in accepted(reviewed,'Київ: реактивний БпЛА рухається')}=={'jet_uav'}
    assert {m['category'] for m in accepted(reviewed,'Київ: Shahed-238 рухається')}=={'jet_uav'}
    shorthand=reviewed.classify('Схоже на реактивну шляпу')[0]
    assert shorthand['category']=='shahed_uav' and shorthand['subtype']=='reactive_shorthand_user_inferred'
    assert not shorthand['accepted_for_aggregation']  # category assigned; no Kyiv geography invented


def test_original_modes_still_reproduce_old_rules():
    old=Dictionary(DICT,DICT.with_name('kyiv_geography.yaml'))
    assert not accepted(old,'Троя бпла')
    assert not accepted(old,'5 шахедів від Вишгорода на Київ')
    assert not accepted(old,'Центр бпла')
    assert not accepted(old,'Пуск Кинджалу')


def test_configuration_pairing():
    with pytest.raises(ValueError):Dictionary(NEW_DICT)
    with pytest.raises(ValueError):Dictionary(NEW_DICT,DICT.with_name('kyiv_geography.yaml'))
    with pytest.raises(ValueError):Dictionary(DICT,NEW_GEO)


def test_aggregation_provenance_and_repeatability(reviewed):
    source=dataset(['Центр шах','Пуск Кинджалу','Буча бпла'])
    markers,features=process(*source,reviewed)
    assert features[0]['threat_combination']=='shahed_uav+ballistic_high_speed'
    assert features[0]['explicit_cause_categories']==[]
    validate_outputs(markers,features,*source[:2],source[2],reviewed)
    assert (markers,features)==process(*source,reviewed)


@pytest.mark.parametrize('text',['Троя бпла?','БпЛА від Вишгорода на Київ?','Київ: можливо Кинджал у музеї','БпЛА на центр Бучі'])
def test_questions_nonwarning_and_other_city_center(reviewed,text):
    assert not accepted(reviewed,text)


def test_unspecified_mig_not_promoted_to_31k(reviewed):
    assert not accepted(reviewed,'Київ: підйом МіГа')


def test_may_warning_uncertainty_not_lost(reviewed):
    markers=accepted(reviewed,'Шахеди можуть рухатися на Київ')
    assert markers and markers[0]['uncertainty_flag'] and markers[0]['evidence_status']=='uncertain'


def test_reviewed_cli_comparison_and_immutable_inputs(tmp_path):
    import json
    import pyarrow.parquet as pq
    from kyiv_alerts.classification.__main__ import main,write_table
    from kyiv_alerts.classification.reviewed_rules_report import main as report_main
    from kyiv_alerts.ingestion.storage import schema_for
    from kyiv_alerts.integration.__main__ import LINK_SCHEMA,COVERAGE_SCHEMA
    source=dataset(['Троя бпла','Київ: ймовірно шах','Пуск Кинджалу'])
    argv=[];original=[]
    for name,rows,schema in zip(['alerts','messages','links','coverage'],source,[schema_for('alerts'),schema_for('messages'),LINK_SCHEMA,COVERAGE_SCHEMA]):
        path=tmp_path/(name+'.parquet');write_table(rows,path,schema)
        original.append(path.read_bytes());argv+=['--'+name,str(path)]
    before=tmp_path/'before';after=tmp_path/'after';report=tmp_path/'report'
    assert main(argv+['--dictionary',str(DICT),'--geography',str(DICT.with_name('kyiv_geography.yaml')),'--output',str(before),'--report',str(tmp_path/'before_report')])==0
    newer=argv+['--dictionary',str(NEW_DICT),'--geography',str(NEW_GEO),'--output',str(after),'--report',str(report)]
    assert main(newer)==0
    frozen=pq.read_table(after/'message_threat_markers.parquet')
    assert main(newer)==0
    assert frozen.equals(pq.read_table(after/'message_threat_markers.parquet'))
    assert original==[(tmp_path/(name+'.parquet')).read_bytes() for name in ['alerts','messages','links','coverage']]
    assert report_main(['--before',str(before),'--after',str(after),'--messages',str(tmp_path/'messages.parquet'),'--report',str(report)])==0
    r=json.loads((report/'reviewed_rules_report.json').read_text())
    assert r['before']['classified_alerts']==0 and r['after']['classified_alerts']==1
    assert r['new_lexical_candidates']>0 and r['precision'] is None
