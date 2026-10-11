"""Evidence-supported Task0049 patterns and safeguards, including reused negatives."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import copy
import pytest
import pyarrow.parquet as pq
import yaml
from kyiv_alerts.classification.rules import CATEGORIES
from kyiv_alerts.classification_v16.lexical import Profile, mask_boilerplate
from kyiv_alerts.classification_v16.core import process

ROOT=Path(__file__).resolve().parents[1]
POLICY=yaml.safe_load((ROOT/'config/attribution_v1_6.yaml').read_text())
T=datetime(2026,7,1,10,tzinfo=timezone.utc)
TEMPLATE=next(f for f in pq.read_table(ROOT/'data/processed/classification_v1_5/alert_threat_features.parquet').to_pylist() if f['classification_status']=='no_marker_with_text')


def profile(policy=None):
    return Profile(ROOT/'config/threat_dictionary_v1_3.yaml',ROOT/'config/kyiv_geography_v1_1.yaml',yaml.safe_load((ROOT/'config/attribution_v1_4.yaml').read_text()),yaml.safe_load((ROOT/'config/attribution_v1_5.yaml').read_text()),policy or POLICY)


def synthetic(texts,earlier=(),baseline=(),policy=None,extra_alerts=(),extra_links=()):
    policy=policy or POLICY;messages=[dict(message_id=str(i),text=text,message_time=T+timedelta(minutes=dt),message_time_original='source '+str(i),message_type='message',source_file='synthetic.html',source_message_index=i) for i,(dt,text) in enumerate([*earlier,*texts])]
    linked=[m for m in messages if m['message_time']>=T];f=copy.deepcopy(TEMPLATE)
    f.update(alert_id='synthetic',start_time=T,end_time=T+timedelta(hours=2),duration_minutes=120,telegram_message_count=len(linked),telegram_text_message_count=len(linked))
    links=[dict(alert_id='synthetic',message_id=m['message_id']) for m in linked]+list(extra_links)
    a=dict(alert_id='synthetic',start_time=T,end_time=f['end_time'],end_time_original=f['end_time'].isoformat())
    ms,fs=process([f],messages,links,list(baseline),profile(policy),[a,*extra_alerts],policy)
    return ms,fs,{c for c in CATEGORIES[:-1] if fs[0][c] is True},messages


@pytest.mark.parametrize('text,expected',[
    ('МіГ',{'mig31'}),('+МіГ',{'mig31'}),('Міг\n2шт',{'mig31'}),('Міг в повітрі',{'mig31'}),('Міг зліт',{'mig31'}),('Тривога по МіГу',{'mig31'}),
    ('Традиційна тривога по балістиці',{'ballistic_high_speed'}),('Балістична ціль зі сходу',{'ballistic_high_speed'}),('З півночі цілі з балістичною траекторією',{'ballistic_high_speed'}),('Загроза застосування БРСД',{'ballistic_high_speed'}),('Балістика',{'ballistic_high_speed'}),
    ('Годину назад з Оленьї здійснило виліт 2 Ту-95',{'strategic_aviation'}),
    ('Загроза удару крилатою ракетою по Києву',{'cruise_missile'}),
    ('Крилата ракета схоже',{'cruise_missile'}),('Реактивний БпЛА від Славутича до нас в область',{'jet_uav'}),
    ('БпЛА північніше Києва',{'shahed_uav'}),('В районі Теремків БпЛА',{'shahed_uav'}),('Шах',{'shahed_uav'}),
    ('⚠️ Втретє за добу зліт винищувача МіГ-31К. Не ігноруйте тривоги',{'mig31'}),
    ('Для областей, у котрих оголошено тривогу - загроза застосування стратегічних бомбардувальників Ту-22м3, які є носіями ракет Х-22',{'strategic_aviation'}),
    ('Загроза застосування балістичного озброєння\n\n🦝 Новини з Сіверщини та Полтавщини\n✙ Український Єнот ✙',{'ballistic_high_speed'}),
    ('МіГ-31К відсутній, БпЛА над Києвом',{'shahed_uav'}),
    ('Ворожих ударів не було, ворожий БпЛА над Києвом',{'shahed_uav'}),
    ('МіГ-31К в повітрі, пусків немає',{'mig31'}),
])
def test_current_evidence(text,expected):
    ms,fs,cats,messages=synthetic([(1,text)]);assert cats==expected
    for m in ms:
        assert m['original_text']==text and m['source_timestamp_original']=='source 0'
        if m['accepted_for_aggregation']:assert m['uncertainty_flag']
        if m['evidence_role']=='lexical_anchor':assert text[m['match_start']:m['match_end']]==m['matched_text']


@pytest.mark.parametrize('text',[
    'Я міг працювати вчора','Міг бути пуск','Міг відбутися пуск БРСД','Міг іди в баню',
    'Уточнюємо, не МіГ','МіГ?', 'МіГ — відбій', 'Вчора МіГ в повітрі',
    'Вчора балістична ціль на Київ','Без цілей з балістичною траекторією',
    'Цілей з балістичною траєкторію на Київ немає і не було',
    'Зараз буде нестись істерика про повторні пуски з Ту-95',
    'Чисто. Про виліт стратегічної авіації ми сповістили першими',
    'Надіюсь не зустрінемось вранці на калібри або виліт Ту-95 (ОЗНАК АКТИВНОСТІ ЗАРАЗ НЕМАЄ)',
    'Короткі висновки за ніч. Ту-95 вже сіли, Ту-22м3 заходять на посадку',
    'Давайте коротко відповімо, чому ми можемо писати, що є ціль з балістичною траекторією на Київ. Курс на Київ, ракета може летіти далі',
    'Балістична ціль не спостерігається','Балістична ціль відсутня',
    'По балістиці поки тихо','По БпЛА чисто станом на зараз',
    'Якби була балістика, вона була б не одна',
    'Київ: характеристики БпЛА та принцип роботи',
    'В новинах пишуть «ворожий БпЛА над Києвом»',
    'Вивід бортів з-під удару\nВ повітрі Ту-95\nЗагрози не несуть, борти виводять з-під удару через атаку наших БпЛА',
    'Збили БпЛА - який жах, тепер 10 замість нього летітиме',
    'Буча БпЛА','Одеса БпЛА курс на центр','БпЛА з Харкова на Полтаву',
    'Реактивний двигун повернувся до сервісу','Реактивна артилерія на Київ',
    'Якщо БпЛА зайде на Київ - повідомимо','Київ увага, якщо завтра буде балістична ціль',
    'На Житомирщині БпЛА, курс на захід','Не на Київ БпЛА',
])
def test_negative_evidence(text):
    ms,fs,cats,_=synthetic([(1,text)]);assert not cats
    assert not any(m['accepted_for_aggregation'] for m in ms)


def test_mig_approval_is_required_and_no_specific_model_is_inferred():
    ms,_,cats,_=synthetic([(1,'+МіГ')]);assert cats=={'mig31'}
    accepted=[m for m in ms if m['accepted_for_aggregation']]
    assert all(m['subtype']=='mig_channel_model_unspecified' and m['inferred_shorthand'] for m in accepted)
    policy=copy.deepcopy(POLICY);policy['mig_shorthand_approved']=False
    assert not synthetic([(1,'+МіГ')],policy=policy)[2]


def test_footer_mask_preserves_offsets_and_only_exact_boilerplate():
    text='БпЛА над Києвом\n🦝 Новини з Сіверщини та Полтавщини\n✙ Український Єнот ✙'
    view=mask_boilerplate(text);assert len(text)==len(view)
    assert view.splitlines()[0]==text.splitlines()[0]
    assert mask_boilerplate('БпЛА на Полтавщині')=='БпЛА на Полтавщині'
    ms,_,cats,_=synthetic([(1,text)]);assert cats=={'shahed_uav'}
    assert any(m['context_view_excluded_spans'] for m in ms)


def test_pre_alert_correspondence_and_previous_alert_contamination():
    assert not synthetic([(1,'Погода гарна')],earlier=[(-1,'МіГ')])[2]
    assert synthetic([(1,'Тривога в столиці через нього')],earlier=[(-1,'МіГ')])[2]=={'mig31'}
    assert synthetic([(1,'Ворожий БпЛА над Києвом')],earlier=[(-1,'Загроза балістики')])[2]=={'shahed_uav'}
    previous=dict(alert_id='previous',start_time=T-timedelta(minutes=20),end_time=T-timedelta(minutes=0.5),end_time_original=(T-timedelta(minutes=0.5)).isoformat())
    assert not synthetic([(1,'Тривога в столиці через нього')],earlier=[(-1,'МіГ')],extra_alerts=[previous],extra_links=[dict(alert_id='previous',message_id='0')])[2]


def test_bounded_route_and_ambiguous_multiple_families():
    assert synthetic([(1,'Х-59 в напрямку Чернігівщини'),(5,'Змінила курс на схід Київщини')])[2]=={'cruise_missile'}
    assert not synthetic([(1,'Х-59 в напрямку Чернігівщини'),(7,'Змінила курс на схід Київщини')])[2]
    assert not synthetic([(1,'Одеса БпЛА'),(2,'Київ')])[2]
    ms,_,_,_=synthetic([(1,'БпЛА на Бровари і Х-59 на Чернігівщину'),(2,'Тривога в столиці через нього')])
    assert all(not m['accepted_for_aggregation'] for m in ms if m['evidence_role']=='context_reference')


def test_negative_trace_points_to_exact_source():
    ms,_,_,mm=synthetic([(1,'Без цілей з балістичною траекторією')]);source=mm[0]['text']
    assert any(m['scope_trace'] for m in ms)
    for m in ms:
        for trace in m['scope_trace']:assert source[trace['match_start']:trace['match_end']]==trace['matched_expression']


def test_foreign_launch_origin_is_not_a_course_word():
    assert not synthetic([(1,'Нові ракети з Курської на Сумщину йдуть'),(3,'Бориспіль, ціль заходить на вас')])[2]
    assert synthetic([(1,'Загроза балістики'),(2,'Цілі відсутні'),(3,'Київ увага')])[2] == {'ballistic_high_speed'}
    markers,_,_,_=synthetic([(1,'Загроза балістики'),(2,'Цілі відсутні'),(3,'Київ увага')])
    assert not any(m['message_id']=='2' and m['accepted_for_aggregation'] for m in markers)


@pytest.fixture(scope='module')
def real_v16():
    import json
    from kyiv_alerts.classification_v16.__main__ import FILES
    data={k:pq.read_table(ROOT/p).to_pylist() for k,p in FILES.items()}
    markers=pq.read_table(ROOT/'data/processed/classification_v1_6/message_threat_markers.parquet').to_pylist()
    features=pq.read_table(ROOT/'data/processed/classification_v1_6/alert_threat_features.parquet').to_pylist()
    report=json.loads((ROOT/'reports/classification_v1_6/classification_comparison.json').read_text())
    return data,markers,features,report


def test_full_source_and_frozen_versions_are_reconciled(real_v16):
    from kyiv_alerts.classification_v16.__main__ import validate,protected_snapshot,rule_hashes,verify_baseline
    data,markers,features,report=real_v16
    validate(markers,features,data)
    assert verify_baseline(data['v1_5'])['additional_unique_required']==122
    current_snapshot = protected_snapshot(ROOT)
    assert all(current_snapshot.get(path) == value for path, value in report['protected_hashes'].items())
    assert rule_hashes(ROOT)==report['frozen_rule_hashes']
    assert len(features)==2594 and len({f['alert_id'] for f in features})==2594
    changed=copy.deepcopy(data['v1_5']);changed.pop()
    with pytest.raises(ValueError,match='Baseline differs'):verify_baseline(changed)


def test_full_coverage_changes_and_nonexclusive_categories_reconcile(real_v16):
    from kyiv_alerts.classification.consolidation import summary,compare_versions
    data,markers,features,report=real_v16
    assert summary(features)==report['versions']['v1_6']
    compare,_=compare_versions(data['v1_5'],features)
    assert compare==report['comparison_v15_v16']
    assert sum(r['v1_6_classified'] for r in report['monthly_coverage'])==summary(features)['classified_alerts']
    assert sum(r['v1_6_classified'] for r in report['yearly_coverage'])==summary(features)['classified_alerts']
    assert sum(report['remaining_unknown_causes'].values())==summary(features)['no_marker_with_text']
    assert sum(report['rule_gain_accounting']['disjoint_first_support'].values())==compare['gained_count']
    for category in CATEGORIES[:-1]:
        assert {m['alert_id'] for m in markers if m['accepted_for_aggregation'] and m['category']==category}=={f['alert_id'] for f in features if f[category] is True}


def test_all_564_diagnostics_and_new_categories_have_source_evidence(real_v16):
    import csv,json
    data,markers,features,report=real_v16
    with (ROOT/'reports/classification_v1_6/residual_diagnostics.csv').open(encoding='utf-8-sig',newline='') as stream:diag=list(csv.DictReader(stream))
    assert {r['alert_id'] for r in diag}=={f['alert_id'] for f in data['v1_5'] if f['classification_status']=='no_marker_with_text'}
    assert len(diag)==564
    old={f['alert_id']:f for f in data['v1_5']};linked={(l['alert_id'],l['message_id']) for l in data['links']}
    for f in features:
        for category in CATEGORIES[:-1]:
            if f[category] is True and old[f['alert_id']][category] is not True:
                evidence=[m for m in markers if m['alert_id']==f['alert_id'] and m['category']==category and m['accepted_for_aggregation']]
                assert evidence and all(m['uncertainty_flag'] for m in evidence)
                assert all(m['original_text'] and m['support_message_ids'] for m in evidence)
                for m in evidence:
                    if m['time_relation']=='before_alert':assert any((m['alert_id'],mid) in linked for mid in m['support_message_ids'])
    assert report['independent_precision'] is None and report['research_lead_acceptance']=='PENDING'


def test_exception_sources_and_reviewed_positive_cases_remain_explainable(real_v16):
    data,markers,features,report=real_v16
    audit=yaml.safe_load((ROOT/'config/task0049_exception_audit.yaml').read_text())['cases']
    assert len(audit)==20 and report['exception_audit_mismatches']==[]
    for case in audit:
        rows=[m for m in markers if m['alert_id']==case['alert_id'] and m['message_id']==case['message_id'] and m['category']==case['category']]
        assert rows and any(m['accepted_for_aggregation'] for m in rows)==case['accepted']
    cases={r['alert_id']:r for r in report['reviewed_case_results']}
    for aid in ['833','1312','1500','2589','806','2563','2565','2578']:
        assert cases[aid]['regression_status']=='CONFIRMED_LABEL_REPRODUCED'
    assert cases['1096']['regression_status']=='CONFIRMED_LABEL_DISCREPANCY'
    assert cases['2581']['regression_status']=='CONFIRMED_LABEL_DISCREPANCY'
    assert cases['1416']['label_status']=='provisional_pending_formal_approval'
    assert cases['2590']['label_status']=='provisional_working_hypothesis_not_confirmed'
    for filename in ['core.py','lexical.py']:
        code=(ROOT/'src/kyiv_alerts/classification_v16'/filename).read_text()
        assert all("'"+case['alert_id']+"'" not in code for case in audit)
