"""Read-only provenance confirmation and restricted official-label corroboration."""
from collections import Counter,defaultdict
from pathlib import Path
from datetime import datetime,timezone
import json
import pyarrow.parquet as pq
from .__main__ import csvwrite,digest
from kyiv_alerts.temporal_analysis import KYIV

CROSSWALK={'drone':('uav_any','PARTIAL'), 'massive-drone':('uav_any','PARTIAL'), 'ballistic':('ballistic_high_speed','EXACT_GROUP'), 'missile':('cruise_missile','EXACT_GROUP'), 'mig':('mig31','PARTIAL_MODEL'), 'missile-drone':('uav_any','PARTIAL_MISSILE_UNSPECIFIED')}

def official_validation(root,facts):
    out=root/'reports/external_validation';base=root/'data/external/task0051'
    original=pq.read_table(root/'data/interim/alerts.parquet').to_pylist();live=json.loads((base/'kyiv_export_snapshot.json').read_text());mm={r['uid']:r for r in live}
    assert len(mm)==len(live)
    confirmation=[]
    for a in original:
        b=mm.get(a['alert_id']);confirmation.append(dict(alert_id=a['alert_id'],original_start=a['start_time_original'],published_start=b['dateTimeStart'] if b else None,original_end=a['end_time_original'],published_end=b['dateTimeEnd'] if b else None,entire_original_record_equal=bool(b==json.loads(a['raw_record_json'])),source='Kyiv Digital published export',independence='same originating source; provenance confirmation only'))
    assert all(r['entire_original_record_equal'] for r in confirmation)
    csvwrite(out/'official_export_confirmation.csv',confirmation)
    items=json.loads((base/'kyiv_history_snapshot.json').read_text())['items'];starts=defaultdict(list)
    for i,r in enumerate(items):
        if r['state']==1:starts[r['created_at']].append((i,r))
    matches=[];comparisons=[];untyped=[];missing=[]
    for f in facts:
        clock=f['start_local'].strftime('%Y-%m-%d %H:%M:%S');candidates=starts[clock]
        if len(candidates)!=1:
            missing.append(dict(alert_id=f['alert_id'],start_local=clock,candidates=len(candidates)));continue
        idx,r=candidates[0];matches.append(dict(alert_id=f['alert_id'],history_source_index=idx,history_created_at=r['created_at'],official_start_original=f['start_time_original'],same_kyiv_display_clock=True,causes=r['causes'],eligible=f['eligible'],v16_markers=f['markers']))
        if not r['causes']:untyped.append(f['alert_id']);continue
        if not f['eligible']:continue
        for cause in r['causes']:
            if cause not in CROSSWALK:continue
            category,quality=CROSSWALK[cause]
            detected=any(c in f['markers'] for c in ['shahed_uav','jet_uav']) if category=='uav_any' else category in f['markers']
            comparisons.append(dict(alert_id=f['alert_id'],start_local=clock,history_source_index=idx,external_cause=cause,crosswalk_target=category,crosswalk_quality=quality,official_cause_present=True,v16_detected=detected,v16_categories=f['markers'],classification_status=f['classification_status'],comparison_status='EXTERNAL_POSITIVE_CORROBORATION_ONLY',metric_scope='matched positive official cause vs whole-alert Telegram detection; not accuracy',source_url='https://kyiv.digital/open-api/air-alert/history',history_payload_sha256=digest(base/'kyiv_history_snapshot.json'),scope_limitation='stored history cause list temporal completeness unknown; additional v16 labels not scored as false positives'))
    csvwrite(out/'official_history_start_alignment.csv',matches);csvwrite(out/'official_history_missing_starts.csv',missing,fields=['alert_id','start_local','candidates']);csvwrite(out/'external_label_comparison.csv',comparisons)
    csvwrite(out/'external_label_disagreements.csv',[r for r in comparisons if not r['v16_detected']])
    aggregate=[]
    for cause in sorted({r['external_cause'] for r in comparisons}):
        rr=[r for r in comparisons if r['external_cause']==cause];n=sum(r['v16_detected'] for r in rr)
        aggregate.append(dict(external_cause=cause,target=rr[0]['crosswalk_target'],crosswalk_quality=rr[0]['crosswalk_quality'],positive_source_rows=len(rr),positive_correspondence=n,no_corresponding_v16_detection=len(rr)-n,positive_support_fraction=n/len(rr),metric_scope='positive-source correspondence, not accuracy/precision/whole-history recall'))
    csvwrite(out/'external_label_support_summary.csv',aggregate)
    crosswalk=[dict(source='Kyiv Digital schema',external_field='causes',external_value=cause,v16_categories=cat,match_type=quality,reason='direct warning-context grouping only; not technical weapon verification; empty list is untyped not absence') for cause,(cat,quality) in CROSSWALK.items()]
    for value,target,quality in [('drones','uav_any','PARTIAL'),('ballistic_missiles','ballistic_high_speed','EXACT_GROUP'),('cruise_missiles','cruise_missile','EXACT_GROUP'),('mig31k_departure','mig31','PARTIAL_MODEL'),('strategic_aircraft_activity','strategic_aviation','EXACT_GROUP'),('unspecified_missiles','other','PARTIAL'),('tactic_aircraft_activity',None,'NONCOMPARABLE'),('guided_aerial_bombs',None,'NONCOMPARABLE'),('air_defense',None,'NONCOMPARABLE'),('unknown',None,'NONCOMPARABLE')]:crosswalk.append(dict(source='alerts.in.ua documentation only',external_field='threats[].threat_type',external_value=value,v16_categories=target,match_type=quality,reason='published schema; no authenticated historical sample; no jet/non-jet distinction in drones'))
    csvwrite(out/'external_category_crosswalk.csv',crosswalk)
    typed=[r for i,r in enumerate(items) if r['state']==1 and r['causes']]
    levels=defaultdict(Counter)
    for r in live:levels[r['dateTimeStart'][:7]][r['level']]+=1
    levelrows=[dict(month=month,all_official=sum(v.values()),untyped_level=v['null'],yellow=v['Жовтий рівень'],red=v['Червоний рівень'],excluding_observed_yellow=sum(v.values())-v['Жовтий рівень'],partial_month=month in ('2022-02','2026-10'),interpretation='sensitivity exclusion only; untyped historical levels are not inferred red') for month,v in sorted(levels.items())]
    csvwrite(out/'official_warning_level_monthly.csv',levelrows)
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    selected=[r for r in levelrows if r['month']>='2026-01'];xx=list(range(len(selected)))
    plt.figure(figsize=(11,5));plt.bar(xx,[r['untyped_level'] for r in selected],label='Level untyped');plt.bar(xx,[r['yellow'] for r in selected],bottom=[r['untyped_level'] for r in selected],label='Observed yellow');plt.bar(xx,[r['red'] for r in selected],bottom=[r['untyped_level']+r['yellow'] for r in selected],label='Observed red');plt.xticks(xx,[r['month'] for r in selected],rotation=20);plt.title('Official warning-level recording changes — Jan to partial Oct2026');plt.ylabel('Official alert starts / month');plt.legend();plt.figtext(.01,.01,'Unchanged 2594-row export: observed typing starts Sep7; public decision Sep7 / announced implementation Sep10. Untyped ≠ red.',fontsize=8);plt.tight_layout(rect=(0,.06,1,1));plt.savefig(out/'figures/warning_level_transition.png',dpi=150);plt.close()
    result=dict(published_export_rows=len(live),all2594_records_equal=True,export_source_same_as_project=True,export_independent_validation=False,history_rows=len(items),history_first=min(r['created_at'] for r in items),history_last=max(r['created_at'] for r in items),history_exact_start_clock_matches=len(matches),history_missing_start_matches=len(missing),first_typed_history=min(r['created_at'] for r in typed),typed_matched_eligible_alerts=len({r['alert_id'] for r in comparisons}),untyped_matched_alerts=len(untyped),label_comparison_rows=len(comparisons),positive_cause_support=aggregate,export_cause_counts=dict(Counter(r['cause'] for r in live)),export_level_counts=dict(Counter(r['level'] for r in live)),api_time_policy='Compare original local clock strings; empirical agreement validates start association without undocumented timezone conversion; ambiguous DST end not imputed',historical_cause_scope='stored state1 causes; not independently certified complete intra-alert threat timeline',warning_level_months=[r for r in levelrows if r['month']>='2026-07'],no_population_accuracy_estimated=True,alerts_in_ua_sample='not obtained: personal token required; documented month_ago is an exposed period, not proof of total retention')
    (out/'official_validation_summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result
