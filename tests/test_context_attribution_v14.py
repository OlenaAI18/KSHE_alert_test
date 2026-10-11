"""Experimental v1.4: explicit anchors, negative boundaries and frozen baseline."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
from collections import Counter
import copy,json
import pytest,yaml
import pyarrow.parquet as pq
from kyiv_alerts.classification.rules import Dictionary,CATEGORIES
from kyiv_alerts.classification_v14.core import process,operational,confined_to_other_region
from kyiv_alerts.classification_v14.lexical import LexicalProfile
from kyiv_alerts.classification_v14.__main__ import validate
from kyiv_alerts.controlled_review.__main__ import FILES

ROOT=Path(__file__).resolve().parents[1]
POLICY=yaml.safe_load((ROOT/'config/attribution_v1_4.yaml').read_text())
D=Dictionary(ROOT/'config/threat_dictionary_v1_3.yaml',ROOT/'config/kyiv_geography_v1_1.yaml')
P=LexicalProfile(ROOT/'config/threat_dictionary_v1_3.yaml',ROOT/'config/kyiv_geography_v1_1.yaml',POLICY)
T=datetime(2026,7,1,10,tzinfo=timezone.utc)
TEMPLATE=next(f for f in pq.read_table(ROOT/'data/processed/classification_v1_3/alert_threat_features.parquet').to_pylist() if f['classification_status']=='no_marker_with_text')


def synthetic(texts,aid='synthetic',earlier=(),extra_alerts=(),extra_links=()):
    messages=[]
    for i,(delta,text) in enumerate([*earlier,*texts],1):
        messages.append(dict(message_id=str(i),message_time=T+timedelta(minutes=delta),message_time_original='original '+str(i),text=text,source_file='synthetic.html',source_message_index=i,message_type='message'))
    linked=[m for m in messages if m['message_time']>=T]
    f=copy.deepcopy(TEMPLATE);f.update(alert_id=aid,start_time=T,end_time=T+timedelta(hours=2),duration_minutes=120,telegram_message_count=len(linked),telegram_text_message_count=len(linked))
    a=dict(alert_id=aid,start_time=f['start_time'],end_time=f['end_time'],end_time_original=f['end_time'].isoformat())
    links=[dict(alert_id=aid,message_id=m['message_id']) for m in linked]+list(extra_links)
    markers=[]
    for m in linked:
        for h in D.classify(m['text']):
            # Unit fixtures model previously rejected candidates: never claim human labels.
            markers.append(dict(h,alert_id=aid,message_id=m['message_id'],source_file=m['source_file'],source_message_index=m['source_message_index'],accepted_for_aggregation=False))
    output,features=process([f],messages,links,markers,P,[a,*extra_alerts],POLICY)
    return output,features,messages


def cats(feature):return {c for c in CATEGORIES[:-1] if feature[c] is True}

@pytest.mark.parametrize('text',['БпЛА над водосховищем','БпЛА біля Обухова','Шахед курс на Бровари','Реактивний БпЛА з Черкащини на Кагарлик'])
def test_operational_uncertain_geography_is_experimental(text):
    markers,features,_=synthetic([(1,text)])
    accepted=[r for r in markers if r['accepted_for_aggregation']]
    assert accepted and cats(features[0])
    assert all(r['uncertainty_flag'] and r['uncertainty_reasons'] and r['experiment_status']=='EXPERIMENTAL — HUMAN VALIDATION REQUIRED' for r in accepted)
    assert all(r['baseline_evidence_status'] in {'uncertain','current_threat'} for r in accepted)

@pytest.mark.parametrize('text',[
 'Вчора БпЛА летів на Київ',
 'Київ БпЛА немає',
 'Київ не фіксується БпЛА',
 'Одеса БпЛА курс на центр',
 'Київ: стаття про характеристики БпЛА та принцип роботи',
 'Жарт: БпЛА летить на Київ',
 'Донат на БпЛА, Київ',
 'БпЛА Київ?',
 'Реактивна артилерія на Київ',
 'Шахова партія Київ',
 'БпЛА з Харкова на Полтаву',
 'МіГ-31К це носій ракети Кинджал, технічні характеристики',
 '🟢Станом на цю мить не відмічаємо ознак застосування стратегічної авіації',
])
def test_negative_regressions_do_not_create_accepted_evidence(text):
    markers,features,_=synthetic([(1,text)])
    assert not any(r['accepted_for_aggregation'] for r in markers)
    assert not cats(features[0])


def test_no_geography_only_category():
    markers,features,_=synthetic([(1,'Троя'),(2,'Оболонь'),(3,'Летить на Київ')])
    assert not markers and not cats(features[0])


def test_multiple_threats_repeated_mentions_deduplicate():
    markers,features,_=synthetic([(1,'БпЛА над водосховищем'),(2,'БпЛА біля Обухова'),(3,'Загроза балістики'),(4,'Троя')])
    assert cats(features[0])=={'shahed_uav','ballistic_high_speed'}
    assert features[0]['unique_threat_category_count']==2
    assert features[0]['classification_status']=='multiple_types'
    assert features[0]['supporting_message_count']==len(set(features[0]['supporting_message_ids']))


def test_explicit_jet_not_generic_model_or_second_type():
    markers,features,_=synthetic([(1,'Реактивний БпЛА на Кагарлик')])
    assert cats(features[0])=={'jet_uav'}
    assert all(m['category']=='jet_uav' for m in markers if m['accepted_for_aggregation'])
    assert any(m['category']=='shahed_uav' and not m['accepted_for_aggregation'] for m in markers)


def test_user_banderol_alias_is_jet_only():
    markers,features,_=synthetic([(1,'Бандероль з Чернігівщини на Згурівку')])
    assert cats(features[0])=={'jet_uav'}
    accepted=[m for m in markers if m['accepted_for_aggregation']]
    assert accepted[0]['subtype']=='banderol_user_confirmed_jet_uav'
    assert accepted[0]['lexical_rule_source']=='user_confirmed_v1.4_alias'
    assert accepted[0]['geography']=='other_region' # Origin is not silently rewritten.


def test_cross_message_anchor_and_reset():
    markers,features,_=synthetic([(1,'БпЛА над водосховищем'),(2,'Оболонь'),(3,'Не фіксується'),(4,'Троя')])
    refs=[m for m in markers if m['evidence_role']=='context_reference' and m['accepted_for_aggregation']]
    assert len(refs)==1 and refs[0]['anchor_message_id']=='1' and refs[0]['message_id']=='2'
    assert refs[0]['match_start'] is None and refs[0]['support_message_ids']==['1','2']


def test_competing_anchor_stops_previous_type_propagation():
    markers,_,_=synthetic([(1,'БпЛА над водосховищем'),(2,'Загроза балістики'),(3,'Оболонь')])
    refs=[m for m in markers if m['evidence_role']=='context_reference' and m['accepted_for_aggregation']]
    assert {r['category'] for r in refs}=={'ballistic_high_speed'}


def test_multiple_concurrent_types_make_ellipsis_ambiguous():
    markers,features,_=synthetic([(1,'Київ БпЛА і загроза балістики'),(2,'Троя')])
    assert cats(features[0])=={'shahed_uav','ballistic_high_speed'}
    assert not any(r['evidence_role']=='context_reference' and r['accepted_for_aggregation'] for r in markers)

@pytest.mark.parametrize('gap,expected',[(5,True),(5.001,False),(30,False)])
def test_bounded_context_not_whole_alert(gap,expected):
    markers,_,_=synthetic([(1,'БпЛА над водосховищем'),(1+gap,'Оболонь')])
    assert any(r['evidence_role']=='context_reference' and r['accepted_for_aggregation'] for r in markers)==expected

@pytest.mark.parametrize('delta,expected',[(-10,True),(-10.001,False),(-.001,True)])
def test_pre_alert_strict_ten_minute_boundaries(delta,expected):
    markers,features,_=synthetic([(1,'Оболонь')],earlier=[(delta,'Київ БпЛА курс на центр')])
    pre=[m for m in markers if m['time_relation']=='before_alert' and m['accepted_for_aggregation']]
    assert bool(pre)==expected
    assert all(0<m['minutes_before_alert']<=10 for m in pre)


def test_at_start_is_inside_not_pre_alert():
    markers,_,_=synthetic([(0,'Київ БпЛА курс на центр')])
    assert markers and all(m['time_relation']=='inside_interval' for m in markers)


def test_pre_alert_ambiguous_requires_local_inside_followup():
    markers,features,_=synthetic([(1,'Оболонь')],earlier=[(-2,'БпЛА біля Обухова')])
    assert cats(features[0])=={'shahed_uav'}
    pre=[m for m in markers if m['time_relation']=='before_alert' and m['accepted_for_aggregation']]
    assert pre[0]['attribution_strength']=='pre_alert_contextually_supported'
    markers,features,_=synthetic([(1,'Погода гарна')],earlier=[(-2,'БпЛА біля Обухова')])
    assert not cats(features[0])


def test_previous_alert_and_intervening_boundary_excluded():
    old=dict(alert_id='previous',start_time=T-timedelta(minutes=20),end_time=T-timedelta(minutes=1))
    markers,features,_=synthetic([(1,'Оболонь')],earlier=[(-3,'Київ БпЛА курс на центр')],extra_alerts=[old],extra_links=[dict(alert_id='previous',message_id='1')])
    assert not cats(features[0])
    pre=[m for m in markers if m['time_relation']=='before_alert']
    assert pre[0]['previous_alert_ids']==['previous'] and pre[0]['intervening_boundary_alert_ids']==['previous']


def test_pre_context_is_not_explicit_cause():
    markers,features,_=synthetic([(1,'Оболонь')],earlier=[(-2,'Тривога в Києві через БпЛА')])
    assert cats(features[0])=={'shahed_uav'}
    assert features[0]['explicit_cause_categories']==[]


def test_source_inputs_and_repeated_process_unchanged():
    first=synthetic([(1,'БпЛА над водосховищем'),(2,'Оболонь')])
    assert first==synthetic([(1,'БпЛА над водосховищем'),(2,'Оболонь')])


@pytest.fixture(scope='module')
def real():
    d={k:pq.read_table(ROOT/p).to_pylist() for k,p in FILES.items() if p.endswith('.parquet')}
    m=pq.read_table(ROOT/'data/processed/classification_v1_4/message_threat_markers.parquet').to_pylist()
    f=pq.read_table(ROOT/'data/processed/classification_v1_4/alert_threat_features.parquet').to_pylist()
    return d,m,f


def test_real_full_output_contract_and_baseline_preservation(real):
    d,m,f=real;validate(m,f,d)
    assert len(f)==len({r['alert_id'] for r in f})==len(d['alerts'])


def test_real_dst_and_history_remain_unknown(real):
    d,m,f=real;old={r['alert_id']:r for r in d['features']}
    for r in f:
        if old[r['alert_id']]['classification_status'] in {'outside_telegram_coverage','unresolved'}:
            assert all(r[c] is None for c in CATEGORIES[:-1]) and r['unknown']
            assert r['supporting_message_ids'] is None
        if old[r['alert_id']]['classification_status']=='unresolved':assert r['end_time'] is None and r['duration_minutes'] is None


def test_reviewed_cases_source_discrepancy_never_hardcoded(real):
    r=json.loads((ROOT/'reports/classification_v1_4/classification_comparison.json').read_text())
    cases={c['alert_id']:c for c in r['reviewed_cases']}
    assert {'2563','2565','2581','2578','2590'}==set(cases)
    for aid in ['2563','2565','2578']:assert not cases[aid]['missing_approved_categories']
    assert cases['2590']['review_status']=='WORKING_HYPOTHESIS_ONLY'
    # Research-lead supplied initial table currently conflicts with the explicit source anchors.
    assert cases['2581']['observed_categories']==['jet_uav']
    if 'shahed_uav' in cases['2581']['approved_categories']:assert cases['2581']['missing_approved_categories']==['shahed_uav']
    for module in ['core.py','lexical.py']:
        text=(ROOT/'src/kyiv_alerts/classification_v14'/module).read_text()
        assert all(aid not in text for aid in cases)

@pytest.mark.parametrize('disabled',['geography','context','cross_message','pre_alert'])
def test_ablation_removes_dependent_weak_pre_episode(disabled):
    f=copy.deepcopy(TEMPLATE);f.update(alert_id='ablation',start_time=T,end_time=T+timedelta(hours=1),telegram_message_count=1,telegram_text_message_count=1)
    messages=[dict(message_id='anchor',message_time=T-timedelta(minutes=2),message_time_original='original anchor',text='БпЛА біля Обухова',source_file='synthetic.html',source_message_index=1,message_type='message'),dict(message_id='ref',message_time=T+timedelta(minutes=1),message_time_original='original ref',text='Оболонь',source_file='synthetic.html',source_message_index=2,message_type='message')]
    links=[dict(alert_id='ablation',message_id='ref')];alerts=[dict(alert_id='ablation',start_time=f['start_time'],end_time=f['end_time'])]
    full=process([f],messages,links,[],P,alerts,POLICY)[1]
    config=dict(POLICY,enabled_corrections=[c for c in ['geography','context','cross_message','pre_alert'] if c!=disabled])
    ablated=process([f],messages,links,[],P,alerts,config)[1]
    assert cats(full[0])=={'shahed_uav'} and not cats(ablated[0])


def test_maximum_anchor_age_even_with_continuous_updates():
    markers,_,_=synthetic([(1,'БпЛА над водосховищем'),(5,'Оболонь'),(9,'Троя'),(11,'Оболонь'),(12,'Троя')])
    refs=[m for m in markers if m['evidence_role']=='context_reference' and m['accepted_for_aggregation']]
    assert {m['message_id'] for m in refs}=={'2','3','4'}


def test_inside_reference_of_pre_anchor_keeps_own_time_relation():
    markers,features,_=synthetic([(1,'Оболонь')],earlier=[(-2,'БпЛА біля Обухова')])
    refs=[m for m in markers if m['evidence_role']=='context_reference' and m['accepted_for_aggregation']]
    assert refs and all(m['time_relation']=='inside_interval' and m['anchor_time_relation']=='before_alert' and m['minutes_before_alert'] is None for m in refs)
    assert all(m['geography_mentions'] for m in refs)


def test_pre_reference_has_own_offset_not_anchor_offset():
    markers,features,_=synthetic([(1,'Оболонь')],earlier=[(-4,'Київ БпЛА курс на центр'),(-2,'Троя')])
    refs=[m for m in markers if m['evidence_role']=='context_reference' and m['time_relation']=='before_alert']
    assert refs and refs[0]['minutes_before_alert']==2


def test_explicit_negation_ends_previous_episode():
    markers,_,_=synthetic([(1,'БпЛА над водосховищем'),(2,'БпЛА немає'),(3,'Оболонь')])
    assert not any(m['message_id']=='3' and m['evidence_role']=='context_reference' for m in markers)


def test_unknown_movement_does_not_resolve_weak_pre_alert_geography():
    markers,features,_=synthetic([(1,'Летить на невідоме місто')],earlier=[(-2,'БпЛА біля Обухова')])
    assert not cats(features[0])
    assert any(m['attribution_strength']=='ambiguous_candidate' for m in markers)


def test_unrelated_short_preposition_is_not_an_operational_reference():
    markers,_,_=synthetic([(1,'БпЛА над водосховищем'),(2,'На вечерю')])
    refs=[r for r in markers if r['evidence_role']=='context_reference']
    assert refs and not any(r['accepted_for_aggregation'] for r in refs)
