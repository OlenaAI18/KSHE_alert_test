from pathlib import Path
from datetime import datetime,timedelta,timezone
import csv,json
import pytest
from kyiv_alerts.external_validation import load_external,assign_intervals,group_state
ROOT=Path(__file__).resolve().parents[1]

def test_external_offsets_dedup_and_estimation_preserved(tmp_path):
    p=tmp_path/'data.csv';p.write_text('started_at,finished_at,naive,source_csv_line\n2025-01-01T02:00:00+02:00,2025-01-01T02:30:00+02:00,True,4\n2025-01-01T00:00:00+00:00,2025-01-01T00:30:00+00:00,True,8\n')
    rows=load_external(p);assert len(rows)==1 and rows[0]['source_csv_lines']==['4','8'] and rows[0]['naive']
    assert rows[0]['start_time'].hour==0
    p.write_text('started_at,finished_at,naive,source_csv_line\n2025-01-01T02:00:00,2025-01-01T02:30:00,True,4\n')
    with pytest.raises(ValueError,match='offset'):load_external(p)

def test_matching_maximizes_cardinality_not_greedy():
    t=datetime(2025,1,1,tzinfo=timezone.utc)
    def row(minutes):return dict(start_time=t+timedelta(minutes=minutes),end_time=t+timedelta(minutes=minutes+20))
    # Official0 can use both; Official1 can only use external0 under5min.
    a=[row(4),row(0)];b=[row(0),row(8)]
    pairs,edges=assign_intervals(a,b,300);assert set(pairs)=={(0,1),(1,0)}
    assert len(edges)==3

def test_halfopen_overlap_and_dst_unresolved_not_imputed():
    t=datetime(2025,1,1,tzinfo=timezone.utc)
    a=[dict(start_time=t,end_time=t+timedelta(minutes=1))];b=[dict(start_time=t+timedelta(minutes=1),end_time=t+timedelta(minutes=2))]
    assert assign_intervals(a,b)[0]==[]
    a[0]['end_time']=None
    with pytest.raises(ValueError,match='Unresolved'):assign_intervals(a,b)

def test_exclusive_group_reconciliation_and_category_subsets():
    import pyarrow.parquet as pq
    facts=pq.read_table(ROOT/'data/processed/temporal_analysis/alert_analysis_fact.parquet').to_pylist();eligible=[f for f in facts if f['eligible']]
    from collections import Counter
    counts=Counter(group_state(f) for f in eligible)
    assert counts=={'single_category':1015,'multiple_categories':280,'unknown':508}
    assert sum(counts.values())==1803
    assert all(not f['markers'] for f in eligible if group_state(f)=='unknown')

def test_reconciliation_foreign_keys_counts_sources_and_protection():
    from kyiv_alerts.external_validation.__main__ import digest
    report=ROOT/'reports/external_validation';s=json.loads((report/'external_validation_summary.json').read_text())
    assert all(digest(ROOT/p)==h for p,h in s['protected_hashes'].items())
    for r in s['historical_reconciliation']:
        assert r['official_resolved_common']==r['matched']+r['official_unmatched']
        assert r['external_unique_common']==r['matched']+r['external_unmatched']
        assert r['external_raw_kyiv_rows']==r['external_unique_kyiv_intervals']+r['duplicate_rows_removed']
    with (report/'historical_reconciliation.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
    for source in s['external_source_manifest']:
        matched=[r for r in rows if r['source']==source and r['status']=='matched']
        assert len(matched)==len({r['official_alert_id'] for r in matched})==len({r['external_record_id'] for r in matched})
        assert all(abs(float(r['start_delta_minutes']))<=5 for r in matched)
    assert s['external_label_agreement'] is None and s['external_weapon_labels_available_for_comparison']
    assert s['official_validation']['no_population_accuracy_estimated']

def test_external_claim_register_and_no_fabricated_label_scores():
    report=ROOT/'reports/external_validation'
    with (report/'source_register.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
    for r in rows:assert all(r[k] for k in ['source_id','title','publisher','url','access_date','source_type','access_status','evidence_note','independence_assessment'])
    with (report/'external_label_comparison.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
    assert len(rows)==209
    assert all(r['comparison_status']=='EXTERNAL_POSITIVE_CORROBORATION_ONLY' and 'not accuracy' in r['metric_scope'] for r in rows)

def test_primary_export_and_history_alignment_without_imputation():
    s=json.loads((ROOT/'reports/external_validation/official_validation_summary.json').read_text())
    assert s['all2594_records_equal'] and s['history_exact_start_clock_matches']==2594
    assert s['typed_matched_eligible_alerts']==194 and s['untyped_matched_alerts']==2400
    assert s['first_typed_history']=='2026-09-07 17:39:50'
    assert not s['export_independent_validation']
    with (ROOT/'reports/external_validation/official_warning_level_monthly.csv').open(encoding='utf-8-sig') as f:months=list(csv.DictReader(f))
    sept=next(r for r in months if r['month']=='2026-09')
    assert int(sept['all_official'])==190 and int(sept['yellow'])==139 and int(sept['excluding_observed_yellow'])==51
    assert all(int(r['all_official'])==int(r['yellow'])+int(r['red'])+int(r['untyped_level']) for r in months)

def test_exact_and_partial_crosswalk_not_model_confirmation():
    from kyiv_alerts.external_validation.official import CROSSWALK
    assert CROSSWALK['drone']==('uav_any','PARTIAL')
    assert CROSSWALK['mig']==('mig31','PARTIAL_MODEL')
    assert CROSSWALK['missile']==('cruise_missile','EXACT_GROUP')
    assert CROSSWALK['missile-drone']==('uav_any','PARTIAL_MISSILE_UNSPECIFIED')
    assert 'jet_uav' not in [v[0] for v in CROSSWALK.values()]
