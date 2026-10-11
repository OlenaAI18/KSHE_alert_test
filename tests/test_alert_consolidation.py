"""Task 004.3: approved vocabulary and one-alert consolidation, not semantic labels."""
from copy import deepcopy
from datetime import timedelta
import csv
import json
from pathlib import Path
import pytest
import pyarrow.parquet as pq
from kyiv_alerts.classification.rules import Dictionary,CATEGORIES
from kyiv_alerts.classification.pipeline import process
from kyiv_alerts.classification.consolidation import STATES,consolidate,summary,category_metrics,temporal_summaries,compare_versions,unclassified_sample
from kyiv_alerts.classification.coverage_audit import validate_consolidation,marker_comparison
from kyiv_alerts.classification.__main__ import main,validate_outputs
from test_classification import dataset,a,m,BASE,DICT

D13=DICT.with_name('threat_dictionary_v1_3.yaml')
D12=DICT.with_name('threat_dictionary_v1_1.yaml')
GEO=DICT.with_name('kyiv_geography_v1_1.yaml')

@pytest.fixture
def dictionary():return Dictionary(D13,GEO)


def accepted(dictionary,text):return [r for r in dictionary.classify(text) if r['accepted_for_aggregation']]


@pytest.mark.parametrize('text,subtype,etype',[
 ('Троя БпЛА','generic_uav','generic_uav'),('ДВРЗ БПЛА','generic_uav','generic_uav'),('Київ: дрон','generic_uav','generic_uav'),('Київ: дрони','generic_uav','generic_uav'),
 ('Київ: ударний БпЛА','attack_uav','attack_uav_explicit'),('Київ: шахед','shahed','shahed_explicit'),('Київ: шах','shakh_shorthand','shahed_explicit'),
 ('Київ: Shahed','shahed','shahed_explicit'),('Київ: Герань','geran','shahed_explicit')])
def test_approved_broad_uav_group_preserves_lexical_type(dictionary,text,subtype,etype):
    rows=accepted(dictionary,text)
    assert any(r['category']=='shahed_uav' and r['subtype']==subtype and r['uav_evidence_type']==etype for r in rows)
    assert all(r['dictionary_version']=='v1.3' and r['classification_version']=='v1.3' for r in rows)
    if subtype=='generic_uav':assert all(r['uav_evidence_type']!='shahed_explicit' for r in rows)


@pytest.mark.parametrize('text,inferred',[
 ('Київ: реактивний шахед',False),('Київ: реактивний БпЛА',False),('Київ: реактив',True),('Центр: реактиви',True),('Київ: реактивний',True),('Київ: Shahed-238',False)])
def test_reactive_group_inference_flag_vs_explicit_reference(dictionary,text,inferred):
    rows=accepted(dictionary,text)
    assert len(rows)==1 and rows[0]['category']=='jet_uav'
    assert rows[0]['inferred_shorthand'] is inferred
    if inferred:
        assert rows[0]['uncertainty_flag'] is True and '238' not in rows[0]['subtype']
        assert rows[0]['uav_evidence_type']=='reactive_shorthand_inferred'
    else:assert rows[0]['uav_evidence_type']=='jet_uav_explicit'


@pytest.mark.parametrize('text',[
 'Вчора Київ: БПЛА','Київ: БПЛА немає','Київ: наші дрони','Київ: збір на дрон','Київ: реактивний двигун','Київ: реактивний снаряд',
 'Київ: реактивний літак','Київ: реактив на завтра','Київ: реактив?','Буча реактив','Буча БпЛА','Київ: дрон для фото',
 'Троя','ДВРЗ','ще один','1 на Київ','цей на Київ','кружляє','падає','БпЛА','реактив'])
def test_unapproved_or_nonoperational_cases_remain_excluded(dictionary,text):
    assert not accepted(dictionary,text)


def test_generic_family_does_not_suppress_itself(dictionary):
    rows=accepted(dictionary,'Київ: БПЛА БПЛА дрон')
    assert len(rows)==3 and all(r['subtype']=='generic_uav' for r in rows)
    assert not any(r['exclusion_reason'] for r in rows)


def test_explicit_model_and_jet_overlap_evidence_retained(dictionary):
    rows=dictionary.classify('Київ: реактивний БпЛА')
    assert any(r['subtype']=='generic_uav' and not r['accepted_for_aggregation'] for r in rows)
    assert any(r['inferred_shorthand'] and r['uncertainty_flag'] and not r['accepted_for_aggregation'] for r in rows)
    assert len([r for r in rows if r['accepted_for_aggregation']])==1


def test_repeated_messages_and_mentions_do_not_inflate_alert_category_count(dictionary):
    source=dataset(['Київ: БпЛА БпЛА']*85+['Київ: балістика']*3)
    markers,features=process(*source,dictionary);f=features[0]
    assert f['unique_threat_category_count']==f['specific_threat_category_count']==2
    assert f['classification_status']=='multiple_types'
    assert f['threat_combination']=='shahed_uav+ballistic_high_speed'
    assert f['supporting_message_count']==88 and f['marker_evidence_count']==173
    assert len(f['supporting_message_ids'])==len(set(f['supporting_message_ids']))==88
    validate_outputs(markers,features,*source[:2],source[2],dictionary)
    validate_consolidation(markers,features,source[1],source[2])


def test_same_message_multiple_categories_single_support_id(dictionary):
    source=dataset(['Київ: шахед та балістика'])
    markers,features=process(*source,dictionary)
    assert features[0]['supporting_message_count']==1 and features[0]['unique_threat_category_count']==2
    assert len(features[0]['category_message_support'])==2
    metrics=category_metrics(features,markers)
    assert metrics['shahed_uav']['unique_supporting_messages']==1 and metrics['ballistic_high_speed']['unique_supporting_messages']==1


def test_other_not_masking_specific_or_inflating_specific_type_count(dictionary):
    source=dataset(['Київ: БпЛА','Київ: ракета летить'])
    markers,features=process(*source,dictionary);f=features[0]
    assert f['shahed_uav'] is True and f['other'] is True
    assert f['classification_status']=='single_type'
    assert f['unique_threat_category_count']==2 and f['specific_threat_category_count']==1
    assert summary(features)['multi_label_alerts_including_other']==1 and summary(features)['multiple_specific_category_alerts']==0


def test_first_evidence_chronological_not_lexical_id_order(dictionary):
    source=dataset(['Київ: БпЛА','Київ: шах'])
    source[1][0]['message_time']=BASE+timedelta(minutes=20)
    source[1][1]['message_time']=BASE+timedelta(minutes=5)
    from kyiv_alerts.integration.linking import integrate
    links,coverage,_=integrate(source[0],source[1]);source=(source[0],source[1],links,coverage)
    markers,features=process(*source,dictionary)
    assert features[0]['first_accepted_evidence_message_id']=='1'
    assert features[0]['supporting_message_ids']==['1','0']
    validate_consolidation(markers,features,source[1],links)


def test_preserves_explicit_cause_when_generic_uav_regrouped(dictionary):
    source=dataset(['Тривога в Києві через бпла біля Чабанів'])
    markers,features=process(*source,dictionary)
    assert features[0]['explicit_cause_categories']==['shahed_uav']
    assert markers[0]['evidence_status']=='explicit_alert_cause' and markers[0]['subtype']=='generic_uav'
    assert category_metrics(features,markers)['shahed_uav']['explicit_cause_alert_count']==1


def test_all_seven_states_and_missing_observations(dictionary):
    from kyiv_alerts.integration.linking import integrate
    alerts=[a('single'),a('multi',BASE+timedelta(hours=2),BASE+timedelta(hours=3)),a('other',BASE+timedelta(hours=4),BASE+timedelta(hours=5)),
      a('none',BASE+timedelta(hours=6),BASE+timedelta(hours=7)),a('no_text',BASE+timedelta(hours=8),BASE+timedelta(hours=9)),
      a('outside',BASE-timedelta(days=4),BASE-timedelta(days=4)+timedelta(hours=1)),a('unresolved',BASE+timedelta(hours=10),None)]
    messages=[m('Київ: БпЛА','s'),m('Київ: шахед та балістика','x',BASE+timedelta(hours=2,minutes=10)),m('Київ: ракета летить','o',BASE+timedelta(hours=4,minutes=10)),
      m('Троя','n',BASE+timedelta(hours=6,minutes=10)),m('Outside','before',BASE-timedelta(days=1)),m('Outside','after',BASE+timedelta(days=1))]
    links,coverage,_=integrate(alerts,messages)
    markers,features=process(alerts,messages,links,coverage,dictionary)
    assert set(f['classification_status'] for f in features)==set(STATES)
    assert sum(summary(features)['classification_state_counts'].values())==7
    for f in features:
        if f['classification_status'] in {'no_linked_text','outside_telegram_coverage','unresolved'}:
            assert all(f[c] is None for c in CATEGORIES[:-1]) and f['specific_threat_category_count'] is None and f['supporting_message_ids'] is None
        elif f['classification_status']=='no_marker_with_text':assert f['unique_threat_category_count']==0 and f['supporting_message_ids']==[]
    assert next(f for f in features if f['alert_id']=='unresolved')['end_time'] is None
    validate_consolidation(markers,features,messages,links)
    monthly,yearly=temporal_summaries(features)
    assert sum(r['total_alerts'] for r in monthly)==sum(r['total_alerts'] for r in yearly)==7


def test_2594_alerts_retained_without_history(dictionary):
    from kyiv_alerts.integration.linking import integrate
    alerts=[a(str(i),BASE+timedelta(days=i),BASE+timedelta(days=i,hours=1)) for i in range(2594)]
    links,coverage,_=integrate(alerts,[])
    markers,features=process(alerts,[],links,coverage,dictionary)
    assert len(features)==len({f['alert_id'] for f in features})==2594
    assert {f['alert_id'] for f in features}=={f['alert_id'] for f in alerts}
    assert all(f['classification_status']=='outside_telegram_coverage' and f['unique_threat_category_count'] is None for f in features)


def test_previous_version_comparison_category_transitions_not_new_coverage(dictionary):
    source=dataset(['Троя бпла','Київ: реактивний'])
    oldmarkers,oldfeatures=process(*source,Dictionary(D12,GEO))
    markers,features=process(*source,dictionary)
    report,rows=compare_versions(oldfeatures,features)
    assert report['previous_classified_alerts']==report['new_classified_alerts']==1
    assert report['gained_count']==report['lost_count']==0
    changes=marker_comparison(oldmarkers,markers)
    assert any(r['previous_category']=='other' and r['new_category']=='shahed_uav' for r in changes)
    assert any(r['previous_category']=='shahed_uav' and r['new_category']=='jet_uav' and r['new_uncertainty'] for r in changes)


def test_non_uav_classification_matches_previous_approved_profile(dictionary):
    old=Dictionary(D12,GEO)
    for text in ['Київ: балістика','Пуск Кинджалу','Київ: рух крилатих ракет','Київ: зліт МіГ-31К','Київ: активність Ту-95МС']:
        before=accepted(old,text);after=accepted(dictionary,text)
        assert len(before)==len(after)
        for a,b in zip(before,after):
            for key in ['category','subtype','matched_text','geography','evidence_status','accepted_for_aggregation']:
                assert a[key]==b[key]


def test_unclassified_selection_unique_deterministic_and_review_blank(dictionary):
    source=dataset(['Троя','Буча БпЛА','ще один на місто'])
    markers,features=process(*source,dictionary)
    rows=unclassified_sample(features,markers,source[1],source[2])
    assert len(rows)==1 and rows==unclassified_sample(features,markers,source[1],source[2])
    assert rows[0]['human_review_status']==rows[0]['human_decision']==rows[0]['review_notes']==''
    assert rows[0]['representative_original_texts'] and 'Буча БпЛА' in rows[0]['representative_original_texts']


@pytest.mark.parametrize('field,value',[('unique_threat_category_count',9),('supporting_message_ids',[]),('first_accepted_evidence_message_id','invalid'),('classification_status','multiple_types')])
def test_validation_detects_broken_consolidation(dictionary,field,value):
    source=dataset(['Троя БпЛА']);markers,features=process(*source,dictionary);features[0][field]=value
    with pytest.raises(ValueError):validate_consolidation(markers,features,source[1],source[2])


def test_cli_new_schemas_audit_csv_repeat_and_immutable_sources(tmp_path):
    from kyiv_alerts.ingestion.storage import schema_for
    from kyiv_alerts.integration.__main__ import write_table,LINK_SCHEMA,COVERAGE_SCHEMA
    source=dataset(['Троя бпла','Київ: реактив','Київ: балістика','Троя'])
    argv=[];files=[]
    for name,rows,schema in zip(['alerts','messages','links','coverage'],source,[schema_for('alerts'),schema_for('messages'),LINK_SCHEMA,COVERAGE_SCHEMA]):
        path=tmp_path/(name+'.parquet');write_table(rows,path,schema);files.append(path);argv+=['--'+name,str(path)]
    previous=tmp_path/'before';prior_report=tmp_path/'before_report'
    assert main(argv+['--dictionary',str(D12),'--geography',str(GEO),'--output',str(previous),'--report',str(prior_report)])==0
    frozen={p:p.read_bytes() for p in files+list(previous.glob('*'))+list(prior_report.glob('*'))}
    output=tmp_path/'new';report=tmp_path/'report'
    args=argv+['--dictionary',str(D13),'--geography',str(GEO),'--previous',str(previous),'--previous-report',str(prior_report/'classification_report.json'),'--output',str(output),'--report',str(report)]
    assert main(args)==0
    table=pq.read_table(output/'alert_threat_features.parquet');mark=pq.read_table(output/'message_threat_markers.parquet')
    assert 'category_message_support' in table.schema.names and 'inferred_shorthand' in mark.schema.names
    r=json.loads((report/'alert_coverage_audit.json').read_text())
    assert r['task_status']=='COMPLETE' and r['global_metrics']['specific_classified_alerts']==1
    assert not r['time_series_readiness']['time_series_analysis_performed']
    csv_before={p.name:p.read_bytes() for p in report.glob('*.csv')}
    assert main(args)==0
    assert pq.read_table(output/'alert_threat_features.parquet').equals(table)
    assert pq.read_table(output/'message_threat_markers.parquet').equals(mark)
    assert csv_before=={p.name:p.read_bytes() for p in report.glob('*.csv')}
    assert frozen=={p:p.read_bytes() for p in frozen}
    with (report/'classification_version_comparison.csv').open(encoding='utf-8-sig',newline='') as f:
        row=next(csv.DictReader(f));assert json.loads(row['added_categories'])==['shahed_uav','jet_uav']


def test_v13_missing_previous_baseline_reports_blocked(tmp_path):
    assert main(['--dictionary',str(D13),'--geography',str(GEO),'--previous',str(tmp_path/'missing'),'--output',str(tmp_path/'output'),'--report',str(tmp_path/'report')])==1
    report=json.loads((tmp_path/'report/classification_report.json').read_text())
    assert report['task_status']=='BLOCKED' and not (tmp_path/'output/alert_threat_features.parquet').exists()


def test_comparison_reports_new_and_lost_alert_ids(dictionary):
    source=dataset(['Київ: реактив'])
    oldmarkers,oldfeatures=process(*source,Dictionary(D12,GEO));markers,features=process(*source,dictionary)
    report,_=compare_versions(oldfeatures,features)
    assert report['gained_alert_ids']==['a'] and report['lost_alert_ids']==[]
    assert marker_comparison(oldmarkers,markers)[0]['new_category']=='jet_uav'
    _,no_marker_features=process(*dataset(['Троя']),dictionary)
    reversed_report,_=compare_versions(features,no_marker_features)
    assert reversed_report['gained_alert_ids']==[] and reversed_report['lost_alert_ids']==['a']


def test_probable_explicit_model_distinguishes_uncertainty_from_inferred_shorthand(dictionary):
    row=accepted(dictionary,'Київ: ймовірно Shahed-238')[0]
    assert row['category']=='jet_uav' and row['uncertainty_flag'] and not row['inferred_shorthand']
    assert row['uav_evidence_type']=='jet_uav_explicit' and row['subtype']=='shahed_238'
