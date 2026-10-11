# Task005.1 — External validation and physical interpretation

Status: **COMPLETE_WITH_DOCUMENTED_SOURCE_LIMITATIONS**. No forecasts and no change to any classification version. Research conclusions remain exploratory. Full source metadata, access dates, publication/commit dates, short evidence notes and independence assessments are in [source_register.csv](source_register.csv). Source IDs below resolve there to exact URLs/pinned commits. Initial network restrictions were resolved for Kyiv/alerts websites; DSNS returned a browser challenge and a relevant direct Air Force source could not be retrieved. No challenge/authentication bypass was attempted. Unsupported category physics remains explicitly unverified.

## 1. Official provenance and warning semantics

The current municipal export **matches all2594 original records in every field**, including original timestamps, UID, cause and level. This confirms source identity; it is the identical origin, not independent ground truth. [official_export_confirmation.csv](official_export_confirmation.csv), source KYIV_EXPORT. The portal states2022-02-28 through2026-10-05 and weekly export updates. Its current API goes later; this does not extend Task005's frozen observation span or add future zeros.

The original file already contains194 typed records and2400 untyped:181 drone/yellow,10 missile/red,1 ballistic/red,2 massive-drone/red. This metadata was available but Task005 did not evaluate warning-level comparability. The static singular display cause and severity level are not the complete seven-category Telegram taxonomy.

Public API history has5330 state entries and all2594 project start clocks match exactly, with source indices retained in [official_history_start_alignment.csv](official_history_start_alignment.csv). Clock strings match original Kyiv-local strings empirically across winter/summer; no undocumented global offset is applied. The official ambiguous end remains null. The API does not expose project UIDs in its state history, so matching uses source clock evidence and the UID-bearing export.

KYIV_API documents coexisting causes, an empty list for untyped/clear states, and `last_cause` as only the most recently announced still-active cause. `mig` means MiG-31 takeoff; `missile` means cruise-missile threat. `drone` does not distinguish Shahed/generic/jet. Webhooks fire at official start/end, not each threat addition/clearing. A historical stored cause list is not certified here as a complete intra-alert threat timeline or as information available before the alert.

## 2. New limitation on the Task005 September increase

KYIV_POLICY, published2026-09-08, states the Defense Council decision was Sep7 with changes effective00:00 Sep10. It describes yellow drone notices, red massive-drone/missile/combined notices, distinct updates for emerging threats, uneven technical differentiated-siren coverage and official all-clear after threat passes. The first typed API record is Sep7 17:39:50; distinguish the observed recording date from the announced policy implementation date.

| month | all_official | untyped_level | yellow | red | excluding_observed_yellow | partial_month |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-07 | 59 | 59 | 0 | 0 | 59 | False |
| 2026-08 | 121 | 121 | 0 | 0 | 121 | False |
| 2026-09 | 190 | 38 | 139 | 13 | 51 | False |
| 2026-10 | 42 | 0 | 42 | 0 | 0 | True |

[Warning-level figure](figures/warning_level_transition.png), [full monthly table](official_warning_level_monthly.csv). August121→September190 is arithmetically correct, but exclusion of observed yellow records gives September51. Thus the apparent growth reverses under an explicitly different administrative-event definition. This is a sensitivity diagnostic, not a corrected series: older untyped records cannot be treated as verified red. October42 are all observed yellow and the month is partial. No causal claim that all growth was a procedure artifact follows; physical escalation and procedural/reporting change cannot be separated here. Task005 historical counts remain untouched, but its late increase must not be presented as pure physical escalation.

## 3. Historical reconciliation against other published records

Strict geography: `Kyiv City`, never `Kyivska oblast`; official-channel archive uses Kyiv City in the oblast field with empty lower-level fields. Pinned source hashes/CSV line provenance are in summary. Duplicate identical intervals retain all original row numbers. Explicit UTC offsets are respected. Common spans exclude endpoint calendar days; unresolved official ends are excluded from interval matching.

Primary one-to-one linkage maximizes matched count among positive-overlap intervals whose starts differ<=5min, then minimizes start error. [historical_reconciliation.csv](historical_reconciliation.csv), [summary](historical_reconciliation_summary.csv), [monthly/yearly counts](historical_count_periods.csv), [1/5/10-minute sensitivity](historical_match_sensitivity.csv), [split/merge candidates](overlap_disagreements.csv). Unmatched means not reconciled by this rule, not automatically source error.

| source | common_start | common_end_exclusive | official_resolved_common | external_unique_common | matched | official_unmatched | external_unmatched | official_matching_rate | start_delta_abs_median | end_delta_abs_median |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pavlo | 2022-03-01 | 2026-06-23 | 2161 | 2282 | 1807 | 354 | 475 | 0.836 | 0.317 | 0.333 |
| vadimkin | 2022-03-01 | 2026-10-05 | 2585 | 2625 | 1963 | 622 | 662 | 0.759 | 0.300 | 0.317 |
| official_archive | 2022-03-16 | 2026-09-06 | 2299 | 2265 | 2240 | 59 | 25 | 0.974 | 0.033 | 0.033 |

The third-party official-channel archive has4141 Kyiv rows but2267 unique intervals:1874 exact duplicates removed only in derived reconciliation. It is not an official institutional dataset merely because its file is named official. Its parser may fill unclosed episodes with start+1h without a CSV row-level estimated flag. Therefore nonflagged end comparisons are descriptive, not independently certified end observations. Volunteer data explicitly marks start+30min estimates; those ends are excluded from end-error summaries. Pavlo has127 such Kyiv endpoints; current volunteer snapshot214. No timestamps are corrected.

Official-channel archive matches all501 resolved2024 and510 resolved2025 official starts in its common span; the all-official2025 count remains511 including the unresolved end. Later archive undercoverage and volunteer disagreement prevent a full-history completeness certification. Monthly figures: [Pavlo](figures/historical_pavlo.png), [current volunteer](figures/historical_vadimkin.png), [official-channel archive](figures/historical_official_archive.png). Closest times for unmatched starts are exploratory in [unmatched_nearest_times.csv](unmatched_nearest_times.csv), not additional matches.

DST1837 has an official-channel record starting+2seconds and ending2025-10-26T00:05:17Z,5seconds after the first candidate fold (versus about60min from the other). This is useful review evidence in [dst_external_candidates.csv](dst_external_candidates.csv); it does not alter the official ambiguous endpoint, its masks, links or v1.6.

## 4. External threat labels: a restricted real comparison

Historical labels **are accessible from Kyiv Digital**, but only for a late typed subset.194 matched eligible alerts have209 mapped official cause positives;2400 project starts match untyped lists. No external absence is inferred from empty causes. alerts.in.ua documentation confirms a personal token is required; no authenticated sample or service token was used. Its exposed historical period is `month_ago` with2 requests/minute, which is not proof of total retention. `threats` is the list of currently open individual threats, with their own type/level/start/source message; omitted when none are open. It is not proof of retained closed-episode threat histories. Current field schema is richer than the older2025 SDK, which does not parse threats.

[Crosswalk](external_category_crosswalk.csv): exact warning-group ballistic/cruise, partial broad UAV/massive UAV/conditional MiG model, compound missile-drone partial, and noncomparable aircraft/bomb/air-defense categories as appropriate. None verifies launches, impacts or a UAV model.

| external_cause | target | crosswalk_quality | positive_source_rows | positive_correspondence | no_corresponding_v16_detection | positive_support_fraction |
| --- | --- | --- | --- | --- | --- | --- |
| ballistic | ballistic_high_speed | EXACT_GROUP | 4 | 2 | 2 | 0.500 |
| drone | uav_any | PARTIAL | 183 | 122 | 61 | 0.667 |
| massive-drone | uav_any | PARTIAL | 3 | 2 | 1 | 0.667 |
| missile | cruise_missile | EXACT_GROUP | 19 | 2 | 17 | 0.105 |

[external_label_comparison.csv](external_label_comparison.csv) and [disagreement sample](external_label_disagreements.csv) retain every source index and official UID. These fractions are **positive-source correspondence**, not accuracy, precision or whole-history recall. Stored official cause context and whole-alert Telegram detection have different scope. For drone positives, support means shahed_uav OR jet_uav, not confirmed Shahed. Ballistic sample4 and massive-drone3 are tiny. Cruise2/19 correspondence and61 drone nondetections require source review; no label is changed automatically and v1.6 extra labels are not scored as false positives. Official labels share the alert process and are not independent physical weapon verification.

## 5. Single/multiple/unknown and observation opportunity

All1803 eligible alerts remain in exactly one analytical group:

| group | n | median | mean | q25 | q75 | p90 | median_messages |
| --- | --- | --- | --- | --- | --- | --- | --- |
| single_category | 1015 | 32.350 | 59.750 | 20.625 | 66.675 | 137.527 | 5.000 |
| multiple_categories | 280 | 110.150 | 158.563 | 46.054 | 229.037 | 376.183 | 29.000 |
| unknown | 508 | 26.133 | 37.226 | 15.242 | 41.700 | 71.342 | 3.000 |

[Distribution chart](figures/single_multi_duration.png), [complete distributions by category/month/year](single_multi_category_duration.csv), [contrasts](single_multi_sensitivity.csv).

| category | single_n | single_median | multi_n | multi_median |
| --- | --- | --- | --- | --- |
| shahed_uav | 431 | 58.333 | 199 | 155.583 |
| jet_uav | 50 | 26.967 | 81 | 95.517 |
| ballistic_high_speed | 307 | 23.967 | 151 | 119.033 |
| cruise_missile | 9 | 37.800 | 90 | 179.083 |
| mig31 | 205 | 30.567 | 88 | 71.533 |
| strategic_aviation | 8 | 46.300 | 69 | 187.917 |
| other | 5 | 107.783 | 65 | 177.267 |

[Category chart](figures/category_single_multi.png). Nine of99 cruise and8 of77 strategic alerts are single-category; their small single samples do not sustain strong physical duration claims. All7 category overall medians are higher in co-occurring alerts. The original duration ordering changes substantially for single-only records; single jet median26.97 versus broad UAV58.33, strategic46.30 versus broad UAV58.33. This is descriptive selection, not an isolated type effect.

Year/month sensitivity with at least10 single AND10 multi observations per cell:

| category | scope | adequate_cells | multi_median_greater_cells | multi_median_not_greater_cells |
| --- | --- | --- | --- | --- |
| ALL | year | 4 | 4 | 0 |
| ALL | month | 7 | 7 | 0 |
| shahed_uav | year | 3 | 3 | 0 |
| shahed_uav | month | 2 | 2 | 0 |
| jet_uav | year | 1 | 1 | 0 |
| jet_uav | month | 2 | 2 | 0 |
| ballistic_high_speed | year | 3 | 3 | 0 |
| ballistic_high_speed | month | 1 | 1 | 0 |
| cruise_missile | year | 0 | 0 | 0 |
| cruise_missile | month | 0 | 0 | 0 |
| mig31 | year | 3 | 3 | 0 |
| mig31 | month | 0 | 0 | 0 |
| strategic_aviation | year | 0 | 0 | 0 |
| strategic_aviation | month | 0 | 0 | 0 |
| other | year | 0 | 0 | 0 |
| other | month | 0 | 0 | 0 |

This threshold defines descriptive sufficiency, not a significance/accuracy gate. Sparse month/year cells remain visible instead of being dropped or declared stable.

Classification yield versus duration:

| bin | eligible | classified | unknown | classification_yield | ci_low | ci_high | duration_median_messages |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [0,15) minutes | 249 | 128 | 121 | 0.514 | 0.445 | 0.590 | 2.000 |
| [15,30) minutes | 532 | 365 | 167 | 0.686 | 0.642 | 0.729 | 3.000 |
| [30,60) minutes | 481 | 329 | 152 | 0.684 | 0.634 | 0.736 | 5.000 |
| [60,120) minutes | 253 | 206 | 47 | 0.814 | 0.756 | 0.862 | 17.000 |
| [120,inf) minutes | 288 | 267 | 21 | 0.927 | 0.889 | 0.961 | 50.500 |

[Yield chart](figures/classification_duration_volume.png), [joint duration×message bins](classification_duration_bias.csv). Yield rises from51.4% below15min to92.7% at>=120min; message medians increase with duration. Mixed alerts have29 messages versus5 for single-category and3 for unknown. Long episodes have more opportunities for publication and label accumulation, but threat complexity may also lengthen episodes or stimulate messages. Direction cannot be inferred. Pointwise intervals use joint day-cluster14-day circular blocks,800 reps,seed20261011; nonstationarity and sparse joint bins limit calibration. No prediction or accuracy model was fitted.

## 6. Physical plausibility, with explicit evidence grades

[physical_plausibility_matrix.csv](physical_plausibility_matrix.csv) separates source evidence from inference. Primary policy/API evidence supports coexisting warnings, takeoff-based MiG cause semantics, administrative all-clear and procedural changes. Dated city accounts corroborate prolonged/repeated combined episodes. It does **not** independently validate category-specific median durations as flight characteristics, reactive-UAV behavior, individual launch identification or causal duration extension.

Four quantities are distinct: time from observation to impact (unobserved here), physical threat-episode duration (not fully observed), declared administrative alert duration (official start/end), and Telegram reporting duration/opportunity. No equation relates them automatically. A public all-clear is not an object-track endpoint in these files. Several threat causes and later updates can coexist; single-category detection does not prove only one threat occurred. Procedure/detection/reporting changes can alter declared or recorded duration without establishing a physical change.

## 7. Comparison with Pavlo and Task006 handoff

[Pavlo comparison](pavlo_research_comparison.md). Conceptual agreement: strong changing activity and caution about stable seasonality. His101705 nationwide events, midday/weekday patterns and2026 forecast are not Kyiv-only validation. His frozen Kyiv2299 records and our2594 cover different dates; only common-span comparison above is meaningful. The notebook fits Prophet to full available history (excluding last day) without a held-out walk-forward test; components/uncertainty cannot establish forecast skill. We neither rerun nor adopt that forecast. Pavlo and current Vadimkin volunteer files share one data lineage.

Recommendation remains **FURTHER_VALIDATION_NEEDED**. [task006_handoff.md](task006_handoff.md) requires a comparable official administrative target across the September policy/recording transition, chronological independent label review and specified feature availability. Task006 is not started; this task supplies no unconditional approval for forecasting.

## Reproduction and tests

Pinned external subset manifests, captured public export/history/schema and earlier inputs stay local under data/external/task0051; raw exports are excluded from Git. Clone pinned public repositories to reproduce interval subsets with original CSV line numbers. Run `python -m kyiv_alerts.external_validation --root .`, then `python scripts/write_external_validation_report.py --root .`; source_register is a reviewed research artifact, not generated claims. Actual checks are recorded in validation_results.json and reproducibility_results.json. All earlier data/classifier/Task005 file hashes are checked unchanged. Report sources, bibliography and evidence notes do not constitute independent semantic gold labels.
