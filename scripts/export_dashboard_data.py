"""Publish allowlisted aggregates only; never serialize a source record."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import pyarrow.parquet as pq

CATEGORIES = ['shahed_uav','jet_uav','ballistic_high_speed','cruise_missile','mig31','strategic_aviation','other']

def export(root, output):
    inputs = {}
    def read(relative):
        path = root / relative
        inputs[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        if path.suffix == '.json': return json.loads(path.read_text(encoding='utf-8'))
        return list(csv.DictReader(path.open(encoding='utf-8-sig', newline='')))
    def number(value): return None if value in ('',None) else float(value)
    def rows(relative, fields, numeric=(), boolean=()):
        return [{k: number(r[k]) if k in numeric else r[k]=='True' if k in boolean else r[k] for k in fields} for r in read(relative)]
    summary = read('reports/temporal_analysis/temporal_summary.json')
    public = {
      'summary': {'schema_version':1,'classification_version':'v1.6','population':summary['baseline'],
        'duration':summary['duration_minutes'],'first_start':summary['official_source_first_start'],
        'last_end':summary['official_source_last_end'],'coverage':summary['baseline']['classified']/summary['baseline']['eligible'],
        'yearly':summary['yearly']},
      'official_monthly':rows('reports/temporal_analysis/monthly_official_summary.csv',
        ['month','days_observed','partial_month','all_record_starts','total_minutes_under_alert','eligible','classified','unknown','classification_coverage'],
        ['days_observed','all_record_starts','total_minutes_under_alert','eligible','classified','unknown','classification_coverage'],['partial_month']),
      'category_statistics':summary['category_summary'],
      'category_duration': [r for r in rows('reports/external_validation/single_multi_category_duration.csv',
        ['scope','period','category','group','n','median','median_messages'],['n','median','median_messages']) if r['scope']=='overall'],
      'category_overlap': rows('reports/temporal_analysis/category_overlap.csv',['category_a','category_b','unique_alerts'],['unique_alerts']),
      'forecast_comparison': [r for r in rows('reports/forecastability_validation/baseline_comparison.csv',['phase','model','n','MAE','RMSE'],['n','MAE','RMSE']) if r['phase']=='final_holdout'],
      'forecast_history':[r for r in rows('reports/forecastability_validation/walk_forward_results.csv',
        ['week_start','phase','actual','model','prediction','absolute_error'],['actual','prediction','absolute_error']) if r['phase']=='final_holdout'],
      'forecastability_by_category': rows('reports/threat_forecastability/category_decision_matrix.csv',
        ['category','decision','final_weeks','baseline_MAE','candidate_MAE','candidate_tested'],['final_weeks','baseline_MAE','candidate_MAE'],['candidate_tested']),
      'temporal_patterns':[r for r in rows('reports/temporal_analysis/statistical_tests.csv',
        ['test','effect','ci_low','ci_high','block_length','holm_p'],['effect','ci_low','ci_high','block_length','holm_p'])
        if r['test'].startswith('season_') or r['test']=='within_month_residual_acf_lag_1' or (r['test']=='daily_acf_lag_1' and r['block_length']==7)],
      'classification_quality':{'classified':summary['baseline']['classified'],'unknown_text':summary['baseline']['text_unknown'],
        'unknown_no_text':summary['baseline']['no_text'],'outside':summary['baseline']['outside'],'unresolved':summary['baseline']['unresolved'],
        'accuracy':None,'categories_overlap':True,'status':'EXPERIMENTAL — HUMAN VALIDATION REQUIRED'},
    }
    factpath=root/'data/processed/temporal_analysis/alert_analysis_fact.parquet'
    inputs[str(factpath.relative_to(root))]=hashlib.sha256(factpath.read_bytes()).hexdigest()
    durations=pq.read_table(factpath,columns=['valid_interval','duration_minutes','year']).to_pylist()
    bins=[0,15,30,60,120,240,480, float('inf')]
    public['duration_distribution']=[{'year':year,'bins':[{'label':f'{low:g}–{high:g}' if high!=float('inf') else '480+',
      'count':sum(r['valid_interval'] and r['year']==year and low<=r['duration_minutes']<high for r in durations)}
      for low,high in zip(bins,bins[1:])]} for year in range(2022,2027)]
    assert sum(r['all_record_starts'] for r in public['official_monthly'])==summary['baseline']['official']
    assert sum(b['count'] for r in public['duration_distribution'] for b in r['bins'])==summary['duration_minutes']['n']
    assert [r['count'] for r in public['category_statistics']]==[630,131,458,99,293,77,70]
    assert len(public['forecast_history'])==39*6
    output.mkdir(parents=True,exist_ok=True)
    for name,value in public.items():
        (output/f'{name}.json').write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    manifest={'schema_version':1,'inputs':inputs,'outputs':{f'{k}.json':hashlib.sha256((output/f'{k}.json').read_bytes()).hexdigest() for k in public}}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return public

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]); parser.add_argument('--output',type=Path)
    args=parser.parse_args(); export(args.root,args.output or args.root/'dashboard/public/data')
