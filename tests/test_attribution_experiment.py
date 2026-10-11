from datetime import datetime,timedelta,timezone
from pathlib import Path
import copy
import pytest
from kyiv_alerts.attribution.core import *
from kyiv_alerts.classification.rules import Dictionary

T=datetime(2026,7,1,10,tzinfo=timezone.utc)
D=Dictionary(Path('config/threat_dictionary_v1_3.yaml'),Path('config/kyiv_geography_v1_1.yaml'))
def msg(mid,text,delta=0):return dict(message_id=str(mid),text=text,message_time=T+timedelta(minutes=delta),message_time_original='original '+str(mid),source_file='example.html',source_message_index=int(mid))
def analyze(messages):return inside_sequence('a',messages,{m['message_id']:D.classify(m['text']) for m in messages},D)

def test_locality_without_anchor_cannot_create_category():
    assert analyze([msg(1,'Троя'),msg(2,'ДВРЗ',1)])==[]

def test_anchor_and_bounded_locality():
    rows=analyze([msg(1,'Бпла курс на південь'),msg(2,'Троя',1)])
    assert any(r['evidence_level']=='contextually_supported_threat' and r['source_message_ids']==['1','2'] and r['anchor_message_id']=='1' for r in rows)
    assert all(r['category']=='shahed_uav' for r in rows)

@pytest.mark.parametrize('delay,allowed',[(5,True),(5.001,False)])
def test_context_boundary(delay,allowed):
    rows=analyze([msg(1,'Бпла курс на південь'),msg(2,'Троя',delay)])
    assert any(r['evidence_level']=='contextually_supported_threat' for r in rows)==allowed

@pytest.mark.parametrize('middle',['Відбій','Київ ракета курс на центр','Донат збір'])
def test_reset_and_competitor(middle):
    rows=analyze([msg(1,'Бпла курс на південь'),msg(2,middle,1),msg(3,'Троя',2)])
    assert not any(r['anchor_message_id']=='1' and r['evidence_level']=='contextually_supported_threat' for r in rows)

@pytest.mark.parametrize('text',['Вчора бпла курс на Київ','Бпла немає над Києвом','Бпла Київ?'])
def test_non_current_cannot_support(text):
    assert not any(r['evidence_level'] in SUPPORTED for r in analyze([msg(1,text),msg(2,'Троя',1)]))

@pytest.mark.parametrize('window',WINDOWS)
def test_strict_before_and_inclusive_lower(window):
    messages=[msg(1,'x',-window-.001),msg(2,'x',-window),msg(3,'x',-.001),msg(4,'x',0)]
    assert [m['message_id'] for m in pre_window(T,[m['message_time'] for m in messages],messages,window)]==['2','3']


def test_previous_membership_and_boundary():
    m=msg(1,'Бпла',-10);alerts=[dict(alert_id='old',start_time=T-timedelta(minutes=20),end_time=T-timedelta(minutes=5))]
    previous,boundaries,uncertain=contamination('new',T,m,alerts,{'1':{'old'}})
    assert previous==['old'] and boundaries==['old'] and not uncertain

def test_unresolved_envelope_not_forever():
    a=dict(alert_id='dst',start_time=T-timedelta(minutes=10),end_time=None,end_time_original=(T+timedelta(minutes=10)).isoformat())
    assert contamination('new',T+timedelta(minutes=30),msg(1,'x'),[a],{})[2]==['dst']
    assert not contamination('new',T+timedelta(days=1),msg(1,'x',60),[a],{})[2]

def test_multiple_and_repeated_categories_are_deduplicable():
    rows=analyze([msg(1,'Київ бпла'),msg(2,'Київ бпла',1),msg(3,'Київ ракета курс на центр',2)])
    assert len({r['category'] for r in rows if r['evidence_level'] in SUPPORTED})==2
    assert all(r['anchor_message_id'] in r['source_message_ids'] for r in rows)

def test_sources_unchanged_and_deterministic():
    messages=[msg(1,'Бпла курс на південь'),msg(2,'Троя',1)];before=copy.deepcopy(messages)
    assert analyze(messages)==analyze(messages);assert messages==before


def test_real_progressive_baseline_and_missingness():
    import pyarrow.parquet as pq
    old=pq.read_table('data/processed/classification_v1_3/alert_threat_features.parquet').to_pylist()
    new=pq.read_table('data/processed/attribution_experiment_v1/progressive_alert_coverage.parquet').to_pylist()
    current={r['alert_id']:r for r in new}
    assert len(current)==len(old)
    for f in old:
        r=current[f['alert_id']]
        assert all(r[k]==v for k,v in f.items())
        if f['classification_status'] in {'outside_telegram_coverage','unresolved'}:
            assert r['inside_new_candidate'] is None
            assert all(r[f'pre_{w}_candidate_categories'] is None for w in WINDOWS)
    unresolved=[r for r in new if r['classification_status']=='unresolved']
    assert all(r['end_time'] is None and r['duration_minutes'] is None for r in unresolved)


def test_real_evidence_and_waterfall():
    import pyarrow.parquet as pq
    import json
    root=Path('data/processed/attribution_experiment_v1')
    inside=pq.read_table(root/'inside_interval_candidates.parquet').to_pylist()
    pre=pq.read_table(root/'pre_alert_candidates.parquet').to_pylist()
    messages={m['message_id']:m for m in pq.read_table('data/interim/telegram_messages.parquet').to_pylist()}
    alerts={a['alert_id']:a for a in pq.read_table('data/interim/alerts.parquet').to_pylist()}
    for r in inside+pre:
        assert r['anchor_message_id'] in messages and r['anchor_message_id'] in r['source_message_ids']
        assert r['evidence_text']==[messages[mid]['text'] for mid in r['source_message_ids']]
        assert r['human_decision'] is None
    for r in pre:
        assert messages[r['anchor_message_id']]['message_time']<alerts[r['alert_id']]['start_time']
        assert r['candidate_windows']==[w for w in WINDOWS if r['minutes_before_alert']<=w]
        if r['contamination_flag']:assert r['evidence_level']!='direct_operational_threat'
    report=json.loads(Path('reports/attribution_experiment_v1/attribution_gap_report.json').read_text())
    b,s=report['baseline'],report['stage_b']
    assert s['evaluated_text_alerts']==s['new_provisional_alerts']+s['still_text_unclassified']==b['text_unclassified']
    assert b['accepted']+b['text_unclassified']+b['no_linked_text']==b['eligible']
    assert b['eligible']+b['outside']+b['unresolved']==b['total']
    for w in report['stage_c']['windows']:
        assert w['remaining_eligible_unclassified']+w['clean_kyiv_candidate_alerts']==s['still_text_unclassified']+b['no_linked_text']
