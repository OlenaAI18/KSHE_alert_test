"""Render reviewed Task005.1 evidence notes against reproducible numerical tables."""
import argparse,csv,json
from pathlib import Path
from kyiv_alerts.external_validation.__main__ import csvwrite,table

def write(root):
    out=root/'reports/external_validation';s=json.loads((out/'external_validation_summary.json').read_text());o=s['official_validation']
    def read(name):
        with (out/name).open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))
    matrix=[]
    def add(id,observation,evidence,mechanism,contradictions,limits,assessment):matrix.append(dict(hypothesis_id=id,empirical_observation=observation,external_evidence_source_ids=evidence,mechanism=mechanism,contradicting_examples=contradictions,limitations=limits,assessment=assessment))
    add('interval_provenance','2594 original records equal current municipal export','KYIV_EXPORT;KYIV_DATASET','Same published interval source and stable UIDs; provenance reconfirmed','Not an independent measurement','Same origin, not ground-truth accuracy','SUPPORTED_BY_EXTERNAL_EVIDENCE')
    add('unchanged_warning_regime','September2026 has190 starts,139 observed yellow','KYIV_POLICY;KYIV_API;KYIV_EXPORT','Documented differentiated warnings and additional threat notices change observation process','Policy decision Sep7; implementation Sep10; typed data begin Sep7','Changes do not quantify physical escalation; older null levels not red','CONTRADICTED')
    add('mig_trigger','mig31 median34.95; single30.57','KYIV_API','Official mig code explicitly denotes MiG-31 takeoff; warning need not certify a launch','v1.6 also uses conditional unspecified-model MiG shorthand','Supports trigger semantics, not duration explanation or model verification','PARTIALLY_SUPPORTED')
    add('ballistic_duration','Ballistic median30.37; single23.97; mixed119.03','KYIV_API;KYIV_SEP30','Official ballistic threat / launch-risk warning is an episode signal, not an observed missile track','Mixed ballistic episodes are much longer;4 official-positive rows only','No measured flight times or independent ballistic-duration sample','NOT_INDEPENDENTLY_VERIFIED')
    add('generic_uav_duration','Broad UAV median78.78; single58.33; mixed155.58','KYIV_POLICY;KYIV_COMBINED','Drone warnings and repeated/combined episodes documented; observation opportunity can accumulate','183 official drone-positive lists:122 v1.6 broad/jet correspondences,61 nondetections','Drone code does not prove Shahed; no independent flight-time measurement','PARTIALLY_SUPPORTED')
    add('jet_uav_duration','Jet median65.25 but single26.97 (n50)','KYIV_API;ALERTS_DOCS','Published drone group does not separate jet/non-jet; proposed propulsion explanation untested','81 of131 jet-category alerts are multi-label','No verified jet-specific public historical labels or dated technical mechanism source','INSUFFICIENT_EVIDENCE')
    add('cruise_duration','Cruise median153.47; single37.80 (n9); mixed179.08 (n90)','KYIV_API;KYIV_COMBINED','Official missile code denotes cruise threat; combined episodes plausible context','Only2 of19 positive official missile lists have v1.6 cruise detection','Single sample too small; source-positive mismatch; no causal speed/duration validation','NOT_INDEPENDENTLY_VERIFIED')
    add('strategic_duration','Strategic median174.12; single46.30 (n8); mixed187.92 (n69)','ALERTS_DOCS;KYIV_COMBINED','Official service schema separates strategic_aircraft_activity from missile types','69 of77 are mixed; single-only median below broad UAV single median','No retrieved strategic-positive historical service sample; activity is not verified launch','NOT_INDEPENDENTLY_VERIFIED')
    add('combined_duration','Single1015 median32.35 vs multiple280 median110.15','KYIV_POLICY;KYIV_COMBINED;KYIV_SEP30','Officially documented coexisting/newly emerging threats and repeated missile-drone episodes','More messages in mixed episodes:median29 vs5; can acquire more labels because episode longer','Plausibility supported, causal extension per object not identified','PARTIALLY_SUPPORTED')
    add('all_clear_is_one_object','Duration measured from official start to all-clear','KYIV_API;KYIV_POLICY','Clear state has no active causes; several causes may coexist; institutional all-clear signals episode end','No object-track identifiers in interval/API records','Cannot equate all-clear with disappearance of one particular object','NOT_INDEPENDENTLY_VERIFIED')
    add('duration_is_flight_time','Four distinct quantities:impact lead time,episode,declared alert,reporting window','KYIV_EXPORT;KYIV_API;VADIMKIN_DOC','Source interval records measure warning events; no impact/object trajectories','Volunteer missing ends may be filled+30min; official-channel parser can fill+1h','Flight/impact quantities not observed by these datasets','CONTRADICTED')
    add('same_origins_independent','Pavlo snapshot and Vadimkin volunteer stream share lineage','PAVLO_README;VADIMKIN_DOC','One eTryvoga-derived stream captured at two dates','Not two independent replications','Shared sources/official process; volunteer recording errors remain','CONTRADICTED')
    add('stable_seasonality','Task005 Holm-adjusted season contrasts not significant','PAVLO_README;PAVLO_NOTEBOOK','External author also cautions yearly component may absorb one-off trend effects','External results nationwide and fitted without held-out validation','Conceptual agreement only, no independent Kyiv-specific seasonal proof','PARTIALLY_SUPPORTED')
    csvwrite(out/'physical_plausibility_matrix.csv',matrix)
    grp=s['groups'];cat=s['category_single_multi'];paired=[]
    for c in ['shahed_uav','jet_uav','ballistic_high_speed','cruise_missile','mig31','strategic_aviation','other']:
        a=next(r for r in cat if r['category']==c and r['group']=='single_category');b=next(r for r in cat if r['category']==c and r['group']=='multiple_categories');paired.append(dict(category=c,single_n=a['n'],single_median=a['median'],multi_n=b['n'],multi_median=b['median']))
    sensitivity=read('single_multi_sensitivity_summary.csv');bias=[r for r in s['classification_bias'] if r['axis']=='duration']
    report=f'''# Task005.1 — External validation and physical interpretation

Status: **COMPLETE_WITH_DOCUMENTED_SOURCE_LIMITATIONS**. No forecasts and no change to any classification version. Research conclusions remain exploratory. Full source metadata, access dates, publication/commit dates, short evidence notes and independence assessments are in [source_register.csv](source_register.csv). Source IDs below resolve there to exact URLs/pinned commits. Initial network restrictions were resolved for Kyiv/alerts websites; DSNS returned a browser challenge and a relevant direct Air Force source could not be retrieved. No challenge/authentication bypass was attempted. Unsupported category physics remains explicitly unverified.

## 1. Official provenance and warning semantics

The current municipal export **matches all2594 original records in every field**, including original timestamps, UID, cause and level. This confirms source identity; it is the identical origin, not independent ground truth. [official_export_confirmation.csv](official_export_confirmation.csv), source KYIV_EXPORT. The portal states2022-02-28 through2026-10-05 and weekly export updates. Its current API goes later; this does not extend Task005's frozen observation span or add future zeros.

The original file already contains194 typed records and2400 untyped:181 drone/yellow,10 missile/red,1 ballistic/red,2 massive-drone/red. This metadata was available but Task005 did not evaluate warning-level comparability. The static singular display cause and severity level are not the complete seven-category Telegram taxonomy.

Public API history has5330 state entries and all2594 project start clocks match exactly, with source indices retained in [official_history_start_alignment.csv](official_history_start_alignment.csv). Clock strings match original Kyiv-local strings empirically across winter/summer; no undocumented global offset is applied. The official ambiguous end remains null. The API does not expose project UIDs in its state history, so matching uses source clock evidence and the UID-bearing export.

KYIV_API documents coexisting causes, an empty list for untyped/clear states, and `last_cause` as only the most recently announced still-active cause. `mig` means MiG-31 takeoff; `missile` means cruise-missile threat. `drone` does not distinguish Shahed/generic/jet. Webhooks fire at official start/end, not each threat addition/clearing. A historical stored cause list is not certified here as a complete intra-alert threat timeline or as information available before the alert.

## 2. New limitation on the Task005 September increase

KYIV_POLICY, published2026-09-08, states the Defense Council decision was Sep7 with changes effective00:00 Sep10. It describes yellow drone notices, red massive-drone/missile/combined notices, distinct updates for emerging threats, uneven technical differentiated-siren coverage and official all-clear after threat passes. The first typed API record is Sep7 17:39:50; distinguish the observed recording date from the announced policy implementation date.

{table(o['warning_level_months'],['month','all_official','untyped_level','yellow','red','excluding_observed_yellow','partial_month'])}

[Warning-level figure](figures/warning_level_transition.png), [full monthly table](official_warning_level_monthly.csv). August121→September190 is arithmetically correct, but exclusion of observed yellow records gives September51. Thus the apparent growth reverses under an explicitly different administrative-event definition. This is a sensitivity diagnostic, not a corrected series: older untyped records cannot be treated as verified red. October42 are all observed yellow and the month is partial. No causal claim that all growth was a procedure artifact follows; physical escalation and procedural/reporting change cannot be separated here. Task005 historical counts remain untouched, but its late increase must not be presented as pure physical escalation.

## 3. Historical reconciliation against other published records

Strict geography: `Kyiv City`, never `Kyivska oblast`; official-channel archive uses Kyiv City in the oblast field with empty lower-level fields. Pinned source hashes/CSV line provenance are in summary. Duplicate identical intervals retain all original row numbers. Explicit UTC offsets are respected. Common spans exclude endpoint calendar days; unresolved official ends are excluded from interval matching.

Primary one-to-one linkage maximizes matched count among positive-overlap intervals whose starts differ<=5min, then minimizes start error. [historical_reconciliation.csv](historical_reconciliation.csv), [summary](historical_reconciliation_summary.csv), [monthly/yearly counts](historical_count_periods.csv), [1/5/10-minute sensitivity](historical_match_sensitivity.csv), [split/merge candidates](overlap_disagreements.csv). Unmatched means not reconciled by this rule, not automatically source error.

{table(s['historical_reconciliation'],['source','common_start','common_end_exclusive','official_resolved_common','external_unique_common','matched','official_unmatched','external_unmatched','official_matching_rate','start_delta_abs_median','end_delta_abs_median'])}

The third-party official-channel archive has4141 Kyiv rows but2267 unique intervals:1874 exact duplicates removed only in derived reconciliation. It is not an official institutional dataset merely because its file is named official. Its parser may fill unclosed episodes with start+1h without a CSV row-level estimated flag. Therefore nonflagged end comparisons are descriptive, not independently certified end observations. Volunteer data explicitly marks start+30min estimates; those ends are excluded from end-error summaries. Pavlo has127 such Kyiv endpoints; current volunteer snapshot214. No timestamps are corrected.

Official-channel archive matches all501 resolved2024 and510 resolved2025 official starts in its common span; the all-official2025 count remains511 including the unresolved end. Later archive undercoverage and volunteer disagreement prevent a full-history completeness certification. Monthly figures: [Pavlo](figures/historical_pavlo.png), [current volunteer](figures/historical_vadimkin.png), [official-channel archive](figures/historical_official_archive.png). Closest times for unmatched starts are exploratory in [unmatched_nearest_times.csv](unmatched_nearest_times.csv), not additional matches.

DST1837 has an official-channel record starting+2seconds and ending2025-10-26T00:05:17Z,5seconds after the first candidate fold (versus about60min from the other). This is useful review evidence in [dst_external_candidates.csv](dst_external_candidates.csv); it does not alter the official ambiguous endpoint, its masks, links or v1.6.

## 4. External threat labels: a restricted real comparison

Historical labels **are accessible from Kyiv Digital**, but only for a late typed subset.194 matched eligible alerts have209 mapped official cause positives;2400 project starts match untyped lists. No external absence is inferred from empty causes. alerts.in.ua documentation confirms a personal token is required; no authenticated sample or service token was used. Its exposed historical period is `month_ago` with2 requests/minute, which is not proof of total retention. `threats` is the list of currently open individual threats, with their own type/level/start/source message; omitted when none are open. It is not proof of retained closed-episode threat histories. Current field schema is richer than the older2025 SDK, which does not parse threats.

[Crosswalk](external_category_crosswalk.csv): exact warning-group ballistic/cruise, partial broad UAV/massive UAV/conditional MiG model, compound missile-drone partial, and noncomparable aircraft/bomb/air-defense categories as appropriate. None verifies launches, impacts or a UAV model.

{table(o['positive_cause_support'],['external_cause','target','crosswalk_quality','positive_source_rows','positive_correspondence','no_corresponding_v16_detection','positive_support_fraction'])}

[external_label_comparison.csv](external_label_comparison.csv) and [disagreement sample](external_label_disagreements.csv) retain every source index and official UID. These fractions are **positive-source correspondence**, not accuracy, precision or whole-history recall. Stored official cause context and whole-alert Telegram detection have different scope. For drone positives, support means shahed_uav OR jet_uav, not confirmed Shahed. Ballistic sample4 and massive-drone3 are tiny. Cruise2/19 correspondence and61 drone nondetections require source review; no label is changed automatically and v1.6 extra labels are not scored as false positives. Official labels share the alert process and are not independent physical weapon verification.

## 5. Single/multiple/unknown and observation opportunity

All1803 eligible alerts remain in exactly one analytical group:

{table(grp,['group','n','median','mean','q25','q75','p90','median_messages'])}

[Distribution chart](figures/single_multi_duration.png), [complete distributions by category/month/year](single_multi_category_duration.csv), [contrasts](single_multi_sensitivity.csv).

{table(paired,['category','single_n','single_median','multi_n','multi_median'])}

[Category chart](figures/category_single_multi.png). Nine of99 cruise and8 of77 strategic alerts are single-category; their small single samples do not sustain strong physical duration claims. All7 category overall medians are higher in co-occurring alerts. The original duration ordering changes substantially for single-only records; single jet median26.97 versus broad UAV58.33, strategic46.30 versus broad UAV58.33. This is descriptive selection, not an isolated type effect.

Year/month sensitivity with at least10 single AND10 multi observations per cell:

{table(sensitivity,['category','scope','adequate_cells','multi_median_greater_cells','multi_median_not_greater_cells'])}

This threshold defines descriptive sufficiency, not a significance/accuracy gate. Sparse month/year cells remain visible instead of being dropped or declared stable.

Classification yield versus duration:

{table(bias,['bin','eligible','classified','unknown','classification_yield','ci_low','ci_high','duration_median_messages'])}

[Yield chart](figures/classification_duration_volume.png), [joint duration×message bins](classification_duration_bias.csv). Yield rises from51.4% below15min to92.7% at>=120min; message medians increase with duration. Mixed alerts have29 messages versus5 for single-category and3 for unknown. Long episodes have more opportunities for publication and label accumulation, but threat complexity may also lengthen episodes or stimulate messages. Direction cannot be inferred. Pointwise intervals use joint day-cluster14-day circular blocks,800 reps,seed20261011; nonstationarity and sparse joint bins limit calibration. No prediction or accuracy model was fitted.

## 6. Physical plausibility, with explicit evidence grades

[physical_plausibility_matrix.csv](physical_plausibility_matrix.csv) separates source evidence from inference. Primary policy/API evidence supports coexisting warnings, takeoff-based MiG cause semantics, administrative all-clear and procedural changes. Dated city accounts corroborate prolonged/repeated combined episodes. It does **not** independently validate category-specific median durations as flight characteristics, reactive-UAV behavior, individual launch identification or causal duration extension.

Four quantities are distinct: time from observation to impact (unobserved here), physical threat-episode duration (not fully observed), declared administrative alert duration (official start/end), and Telegram reporting duration/opportunity. No equation relates them automatically. A public all-clear is not an object-track endpoint in these files. Several threat causes and later updates can coexist; single-category detection does not prove only one threat occurred. Procedure/detection/reporting changes can alter declared or recorded duration without establishing a physical change.

## 7. Comparison with Pavlo and Task006 handoff

[Pavlo comparison](pavlo_research_comparison.md). Conceptual agreement: strong changing activity and caution about stable seasonality. His101705 nationwide events, midday/weekday patterns and2026 forecast are not Kyiv-only validation. His frozen Kyiv2299 records and our2594 cover different dates; only common-span comparison above is meaningful. The notebook fits Prophet to full available history (excluding last day) without a held-out walk-forward test; components/uncertainty cannot establish forecast skill. We neither rerun nor adopt that forecast. Pavlo and current Vadimkin volunteer files share one data lineage.

Recommendation remains **FURTHER_VALIDATION_NEEDED**. [task006_handoff.md](task006_handoff.md) requires a comparable official administrative target across the September policy/recording transition, chronological independent label review and specified feature availability. Task006 is not started; this task supplies no unconditional approval for forecasting.

## Reproduction and tests

Pinned external subset manifests, captured public export/history/schema and earlier inputs stay local under data/external/task0051; raw exports are excluded from Git. Clone pinned public repositories to reproduce interval subsets with original CSV line numbers. Run `python -m kyiv_alerts.external_validation --root .`, then `python scripts/write_external_validation_report.py --root .`; source_register is a reviewed research artifact, not generated claims. Actual checks are recorded in validation_results.json and reproducibility_results.json. All earlier data/classifier/Task005 file hashes are checked unchanged. Report sources, bibliography and evidence notes do not constitute independent semantic gold labels.
'''
    (out/'external_validation_report.md').write_text(report)
    (out/'pavlo_research_comparison.md').write_text('''# Pavlo Loiek comparison — pinned10b4d32f37843533f59f2197153993be338f7f51

Read README, committed snapshot and notebook, not just headline results. Source references PAVLO_README/PAVLO_DATA/PAVLO_NOTEBOOK in source_register.csv.

| Dimension | External research | This project | Consequence |
|---|---|---|---|
| Geography |25 regions,101705 starts; Kyiv City2299 |Kyiv City2594 official records |Nationwide rates/weekday/hour results cannot validate Kyiv rates |
| Source |Vadimkin volunteer eTryvoga snapshot |Municipal Kyiv Digital intervals; Telegram context |Different recording paths, shared underlying public alert events |
| Dates |2022-02-25 through frozen2026-06-23 |2022-02-28 through2026-10-05 |Reconcile only common complete days; endpoints partial |
| Durations |Naive+30min ends flagged |One DST end unresolved |Exclude volunteer estimates for end validation; do not repair originals |
| Trend/seasonality |README calls trend dominant and annual component unreliable |Holm-adjusted seasons not established; monthly-centering removes much raw ACF |Conceptual agreement, not independent Kyiv seasonal replication |
| Weekly/hour findings |Nationwide descriptive counts and Prophet components |Kyiv-only common-span weekday rates in kyiv_weekday_comparison.csv |Different denominators; no weekday forecast conclusion |
| Forecast |Nationwide Prophet fitted to available history minus final partial day |No forecasts in Task005/005.1 |No held-out forecast evaluation located; do not adopt external projection |
| Independence |Same dataset lineage as current Vadimkin volunteer |Distinct municipal file, but administrative alert process shared |Two volunteer snapshots do not constitute two ground truths |

The external README warns projection is extrapolation and strategic changes could break it. The statement that decomposition is “decisive” is stronger than a fitted component plot can establish: no independent calendar-seasonality or prospective skill validation is shown. No forecasts were executed or imported.

Quantified Kyiv disagreements and matching tolerance sensitivity are in historical_reconciliation_summary.csv/historical_count_periods.csv. No whole-history2299-vs2594 discrepancy is interpreted without date alignment. Current official-channel archive duplicates and incomplete later coverage are separate source-quality findings. Physical/context labels do not exist in Pavlo's four-column snapshot.
''')
    (out/'task006_handoff.md').write_text('''# Task006 handoff — Task005.1

**FURTHER_VALIDATION_NEEDED**. Task006 not started. No forecasting implementation or unconditional model approval.

1. Define comparable official target before any forecast validation: distinguish starts/alert-minutes, actual declared alert versus yellow/red threat notifications, overlap/episode boundaries and source completeness. September2026 is a documented warning-policy/recording transition.139/190 September rows are observed yellow; removing them reverses the apparent August→September count increase. Older null levels cannot be imputed red. Preserve the old2594 series; create an explicitly versioned target only after approval.
2. Resolve official DST1837 through a separate accepted source decision if needed. External official-channel archive supports the first fold within5seconds, but current originals/links remain unresolved.
3. Independently review194 typed official-history cases and disagreements against full timelines. Source-positive support is not accuracy: broad drones122/183, missiles2/19, ballistic2/4, massive-drone2/3. Missing official types beforeSep7, incomplete cause timing, generic/jet grouping and same-origin source dependence preclude global accuracy.
4. Separate singly detected from co-occurring categories and keep unknowns. Cruise single n9 and strategic single n8 are too sparse for strong type-specific temporal claims. Observation opportunity rises with duration/messages; account for this before physical or category trends.
5. If a comparable aggregate target is approved, plan strictly chronological walk-forward evaluation with an untouched future period, training-only transforms and available-at-origin features. Retrospective Telegram labels and stored causes may be known only during/after alert. Baselines: training-window mean, last observation, recent rolling mean, calendar historical rate with calibrated overdispersed reference uncertainty. No model was built here.
6. External regional/nationwide Prophet projections, duplicate archive rows, estimated ends, untyped-source zeros, random splits and source-selection effects must not become validation truth.

Official-source metadata and physical mechanism evidence are clearer; forecast readiness is not established. Direct reactive-UAV technical explanation and a historical authenticated alerts.in.ua sample remain unavailable. Do not infer safe periods or individual attack predictability from aggregate retrospective patterns.
''')
    print('Report and physical matrix written')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('.'));args=p.parse_args();write(args.root.resolve())
