import importlib.util
import json
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('dashboard_export',ROOT/'scripts/export_dashboard_data.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

@pytest.fixture(scope='module')
def exported(tmp_path_factory):
    return module.export(ROOT,tmp_path_factory.mktemp('public'))

def test_reconciled_population(exported):
    s=exported['summary']; assert s['population']['official']==2594
    assert sum(r['all_record_starts'] for r in exported['official_monthly'])==2594
    assert sum(r['classified'] for r in exported['official_monthly'])==1295
    assert sum(r['eligible'] for r in exported['official_monthly'])==1803
    assert s['duration']['n']==2593
    assert s['coverage']==pytest.approx(1295/1803)

def test_overlap_not_partition(exported):
    assert sum(r['count'] for r in exported['category_statistics'])>1295
    for r in exported['category_statistics']:
        diagonal=next(x for x in exported['category_overlap'] if x['category_a']==r['category'] and x['category_b']==r['category'])
        assert diagonal['unique_alerts']==r['count']
        groups=[x for x in exported['category_duration'] if x['category']==r['category']]
        assert sum(x['n'] for x in groups)==r['count']

def test_partial_periods_and_histogram(exported):
    assert [r['period'] for r in exported['summary']['yearly'] if r['partial_period']]==[2022,2026]
    assert exported['official_monthly'][-1]['partial_month'] is True
    assert sum(b['count'] for r in exported['duration_distribution'] for b in r['bins'])==2593

def test_holdout_reconciliation(exported):
    rows=exported['forecast_history']
    assert len({r['week_start'] for r in rows})==39
    for model in exported['forecast_comparison']:
        subset=[r for r in rows if r['model']==model['model']]
        assert sum(r['absolute_error'] for r in subset)/39==pytest.approx(model['MAE'])
    assert sum(r['candidate_tested'] for r in exported['forecastability_by_category'])==1

def test_no_source_records_or_paths(exported):
    def visit(v):
        if isinstance(v,dict):
            assert not ({'message_id','text','alert_id','start_time_original','message_text'}&v.keys())
            for x in v.values():visit(x)
        elif isinstance(v,list):
            for x in v:visit(x)
        elif isinstance(v,str): assert '/workspace/' not in v and '/tmp/' not in v
    visit(exported)
    assert exported['classification_quality']['accuracy'] is None
    assert exported['official_monthly'][0]['classification_coverage'] is None

def test_export_deterministic(tmp_path):
    a=tmp_path/'a';b=tmp_path/'b';module.export(ROOT,a);module.export(ROOT,b)
    assert {p.name:p.read_bytes() for p in a.iterdir()}=={p.name:p.read_bytes() for p in b.iterdir()}
