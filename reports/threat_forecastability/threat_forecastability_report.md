# Task006.1 — Threat-specific forecastability assessment

Status COMPLETE. This task does not inherit Task006's overall decision. Every category has its own observed-data gate and, if eligible, its own chronological experiment. **Counts mean detected reported-category alert markers, not true threat incidence, attacks, weapons or launches.** Generic UAV is not verified Shahed; MiG shorthand is uncertain channel terminology; categories overlap.

## Quality gate before forecast evaluation

The fixed protocol is config/threat_forecastability_v1.yaml and ADR029. quality_gate_snapshot.json is produced before forecast scoring. gate_threshold_sensitivity.csv shows which data gates would change at a Jaccard screen of.65; no forecast is rerun after relaxing a gate. Research sufficiency thresholds are conservative screens, not scientifically validated universal cutoffs:104 observed calendar weeks;100 labeled alerts;40 development/20 final positives;20/10 nonzero scored weeks;20 origins each phase;v15/v16 Jaccard>=.70; annual overall coverage range<=.25;<=40% observed weeks below60% classification. They screen reported-marker feasibility, not physical truth. Failed categories receive no forced forecasts or fabricated zeros.

| category | total_labeled_alerts_v16 | complete_observed_weeks | weeks_no_detected_category | development_origins | final_origins | development_positive_alerts | final_positive_alerts | v15_v16_jaccard | gate_status | failed_checks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| shahed_uav | 630 | 161 | 28 | 48 | 36 | 233 | 221 | 0.9479 | PASS_FOR_EXPLORATORY_REPORTED_MARKER_TEST |  |
| jet_uav | 131 | 161 | 133 | 48 | 36 | 5 | 98 | 0.9771 | INSUFFICIENT_DATA_FOR_RELIABLE_FORECAST_TEST | development_positive_alerts;development_nonzero_weeks |
| ballistic_high_speed | 458 | 161 | 23 | 48 | 36 | 145 | 119 | 0.7783 | PASS_FOR_EXPLORATORY_REPORTED_MARKER_TEST |  |
| cruise_missile | 99 | 161 | 87 | 48 | 36 | 29 | 17 | 0.9495 | INSUFFICIENT_DATA_FOR_RELIABLE_FORECAST_TEST | total_positive_alerts;development_positive_alerts;final_positive_alerts |
| mig31 | 293 | 161 | 49 | 48 | 36 | 45 | 44 | 0.6655 | INSUFFICIENT_DATA_FOR_RELIABLE_FORECAST_TEST | version_stability |
| strategic_aviation | 77 | 161 | 96 | 48 | 36 | 24 | 14 | 0.6951 | INSUFFICIENT_DATA_FOR_RELIABLE_FORECAST_TEST | total_positive_alerts;development_positive_alerts;final_positive_alerts;version_stability |
| other | 70 | 161 | 108 | 48 | 36 | 29 | 7 | 0.9189 | INSUFFICIENT_DATA_FOR_RELIABLE_FORECAST_TEST | total_positive_alerts;development_positive_alerts;final_positive_alerts;final_nonzero_weeks |

category_month_year_counts.csv retains month/year counts, eligible/unknown denominators and unavailable nulls. category_evidence_strength.csv reports accepted evidence levels and uncertainty; terminology_reporting_by_year.csv retains subtypes/inferred shorthand over years. Those occurrence counts are not unique-alert or weapon counts. Weekly coverage and reporting volume vary; retrospective vocabulary development, not just physical change, can alter detected counts. Gate-threshold sensitivity is documented: MiG would pass the other screens at Jaccard.65 instead of.70; no forecast is rerun using that relaxed screen. Its decision therefore reflects the predeclared stability requirement, not a mathematical impossibility of fitting a model. All seven source categories remain untouched.

## Availability, unknowns and retrospective annotation limitation

Complete Monday–Monday Kyiv weeks run from 2023-08-21 through week 2026-09-28. Official no-record weeks, DST-unresolved weeks and incomplete Telegram alert coverage are unavailable. Observed zero means no detected category marker among eligible recorded alerts, never a negative physical label. Unknown alert counts remain explicit and are not filled with any threat type. Each alert counted once/category; the same alert may count in multiple categories.

Finalization release is max(week end, all source alert ends, every accepted marker and supporting message time), using the later release in either version. At each origin, later-finalizing past weeks are unavailable for training/features; exact prior8 calendar-week windows required. Targets can be scored when their later labels finalize; their timestamps are recorded. No invented release for missing support. Development selection also excludes any development target finalized after2026-01-05; every supervised training row's features are reconstructed at its own historical origin, not merely at the later fitting origin. No edited timestamps were present; pipeline blocks if unmodeled edit timestamps appear. Source API/publication/revision latency is not certified.

**The taxonomy was developed retrospectively across the source history, including2026.** A holdout for numerical model selection is not an independently blind annotation holdout. Frozen labels can support conditional offline marker-target assessment, but cannot reconstruct a real historical service's as-of rules. This limitation is explicit; no claim of fully prospective or physical predictive validation follows even if conditional gains appear. Dictionary availability is not silently equated to message availability.

## Frozen forecasting design

First52 complete calendar weeks initialize training. First possible development origin 2024-08-19; final period begins2026-01-05 as Task006. Coverage and evidence-release exclusions reduce scored weeks, shared by all methods and versions. Actual scored origins: development 2024-08-26–2025-12-29; final 2026-01-05–2026-09-14; 27 origins excluded (availability_exclusions.csv). In particular, final scored origins stop at Sep14 rather than Sep28: the Sep21/Sep28 origins lack finalized prior-week labels. Some high late-September weeks are therefore outside the comparable-origin evaluation; final scores are conditional on this availability-selected subset and cannot summarize all39 Task006 weeks. Failed categories' decision-matrix scored-week counts are0; data-quality tables show possible origins only. B0 historical mean; B1 previous4; B2 previous8; B3 previousweek; Z0 observed-marker zero reference. Baseline selected on development MAE only. Optional M1 is the Task006 regularized log-link Poisson AR with lag1/2/4 and4/8 means, training-only scaler and supervised-row features reconstructed at each row's own historical origin, fixed alpha10, no per-category hyperparameter search. It runs only when a recent baseline has>=10% development gain over B0 and paired pointwise95%4-week block interval strictly favors it. Otherwise candidate MAE remains unavailable, never a zero or failed-model score.

| category | selected_baseline | development_recent_vs_mean_gain | development_difference_ci_low | development_difference_ci_high | model_enabled |
| --- | --- | --- | --- | --- | --- |
| shahed_uav | B1 | 0.3496 | -1.7981 | -0.3013 | True |
| ballistic_high_speed | B0 | -0.1543 | -0.0987 | 0.5881 | False |

## Final performance

| category | model | n | positive_alerts | nonzero_weeks | MAE | RMSE | mean_bias | skill_vs_selected_baseline |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| shahed_uav | B0 | 36 | 221 | 35 | 4.0746 | 7.4934 | -3.1632 | -0.3488 |
| shahed_uav | B1 | 36 | 221 | 35 | 3.0208 | 5.1213 | -1.5347 | 0.0000 |
| shahed_uav | B2 | 36 | 221 | 35 | 3.8646 | 6.2854 | -2.0521 | -0.2793 |
| shahed_uav | B3 | 36 | 221 | 35 | 2.9722 | 4.1265 | -0.6944 | 0.0161 |
| shahed_uav | Z0 | 36 | 221 | 35 | 6.1389 | 9.2180 | -6.1389 | -1.0322 |
| shahed_uav | M1 | 36 | 221 | 35 | 3.5633 | 6.1457 | -2.0166 | -0.1796 |
| ballistic_high_speed | B0 | 36 | 119 | 36 | 1.6881 | 2.3093 | -0.6206 | 0.0000 |
| ballistic_high_speed | B1 | 36 | 119 | 36 | 1.5764 | 2.1647 | -0.0903 | 0.0662 |
| ballistic_high_speed | B2 | 36 | 119 | 36 | 1.6181 | 2.2271 | -0.2986 | 0.0415 |
| ballistic_high_speed | B3 | 36 | 119 | 36 | 2.0000 | 2.7285 | -0.0556 | -0.1847 |
| ballistic_high_speed | Z0 | 36 | 119 | 36 | 3.3056 | 3.9896 | -3.3056 | -0.9581 |

MAE/RMSE/bias are reported-category alerts/week. Raw MAEs must not rank predictability across categories with different mean event counts; compare each method against its own frozen baseline with uncertainty instead. Sparse events also show Z0; WAPE/MAPE are not used. Development scores are retained but are not untouched validation. No unreported winner selection on final results.

## Uncertainty, stability and label sensitivity

Paired absolute-error differences use circular4-calendar-week blocks with unavailable-origin positions retained as missing slots (joint paired errors, no compressed timeline),4000 reps,seed20261011;8-week sensitivity. **14 planned contrasts remain in the family even when categories/models are not run.** Bonferroni-adjusted two-sided interval alpha=.05/14 controls the nominal familywise rate under the block approximation; pointwise95% intervals are also shown. Short nonstationary samples and tail Monte Carlo resolution limit nominal calibration. A wide interval spanning0 cannot establish gain. These are error-difference intervals, not predictive bands or threat probabilities.

| category | method | comparator | n | mean_absolute_error_difference | pointwise_ci_low | pointwise_ci_high | simultaneous_ci_low | simultaneous_ci_high |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| shahed_uav | B1 | B0 | 36 | -1.0538 | -2.9255 | 0.2141 | -3.8843 | 0.4308 |
| shahed_uav | M1 | B1 | 36 | 0.5425 | -0.1085 | 1.4840 | -0.2466 | 1.9631 |
| ballistic_high_speed | B0 | B0 | 36 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

| category | version | model | n | MAE | skill_vs_selected_baseline |
| --- | --- | --- | --- | --- | --- |
| shahed_uav | v16 | B0 | 36 | 4.0746 | -0.3488 |
| shahed_uav | v15 | B0 | 36 | 3.9990 | -0.3582 |
| shahed_uav | v16 | B1 | 36 | 3.0208 | 0.0000 |
| shahed_uav | v15 | B1 | 36 | 2.9444 | 0.0000 |
| shahed_uav | v16 | B2 | 36 | 3.8646 | -0.2793 |
| shahed_uav | v15 | B2 | 36 | 3.7153 | -0.2618 |
| shahed_uav | v16 | B3 | 36 | 2.9722 | 0.0161 |
| shahed_uav | v15 | B3 | 36 | 2.6944 | 0.0849 |
| shahed_uav | v16 | Z0 | 36 | 6.1389 | -1.0322 |
| shahed_uav | v15 | Z0 | 36 | 6.0000 | -1.0377 |
| shahed_uav | v16 | M1 | 36 | 3.5633 | -0.1796 |
| shahed_uav | v15 | M1 | 36 | 3.4937 | -0.1865 |
| ballistic_high_speed | v16 | B0 | 36 | 1.6881 | 0.0000 |
| ballistic_high_speed | v15 | B0 | 36 | 1.6597 | 0.0000 |
| ballistic_high_speed | v16 | B1 | 36 | 1.5764 | 0.0662 |
| ballistic_high_speed | v15 | B1 | 36 | 1.6042 | 0.0335 |
| ballistic_high_speed | v16 | B2 | 36 | 1.6181 | 0.0415 |
| ballistic_high_speed | v15 | B2 | 36 | 1.6146 | 0.0272 |
| ballistic_high_speed | v16 | B3 | 36 | 2.0000 | -0.1847 |
| ballistic_high_speed | v15 | B3 | 36 | 2.1111 | -0.2720 |
| ballistic_high_speed | v16 | Z0 | 36 | 3.3056 | -0.9581 |
| ballistic_high_speed | v15 | Z0 | 36 | 3.0556 | -0.8410 |

Both versions use exactly matched final origins; selected v1.6 comparator and alpha stay fixed, no retuning. Version sensitivity is classifier uncertainty, not a new independent dataset. Baseline-vs-mean and candidate-vs-selected are different questions; a recent baseline can carry predictive information without a model improvement. Favorable signals require>=10% final gain, adjusted interval below0, same development/final direction, same direction underv1.5 and non-weak-month scoring (>=20 final weeks). Non-weak filtering is a retrospective scoring diagnostic only, never a future-informed training mask. Weak months: 2023-09, 2025-05, 2026-01, 2026-02, 2026-03, 2026-10. Calendar2024/2025/2026, September and pre/postSep10 errors are in category_robustness.csv; short post-change subset is descriptive. All real yellow/red official alerts remain included; no causal procedure explanation asserted.

## Category decisions and interpretation

| category | decision | development_weeks | final_weeks | selected_baseline | baseline_MAE | candidate_MAE | candidate_tested | reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| shahed_uav | INCONCLUSIVE | 48 | 36 | B1 | 3.0208 | 3.5633 | True | simultaneous interval/version/weak-month stability gates applied; findings exploratory due retrospective taxonomy |
| jet_uav | INSUFFICIENT_DATA_FOR_RELIABLE_FORECAST_TEST | 0 | 0 | None | None | None | False | development_positive_alerts;development_nonzero_weeks |
| ballistic_high_speed | NO_STABLE_GAIN_OVER_BASELINES | 48 | 36 | B0 | 1.6881 | None | False | simultaneous interval/version/weak-month stability gates applied; findings exploratory due retrospective taxonomy |
| cruise_missile | INSUFFICIENT_DATA_FOR_RELIABLE_FORECAST_TEST | 0 | 0 | None | None | None | False | total_positive_alerts;development_positive_alerts;final_positive_alerts |
| mig31 | INSUFFICIENT_DATA_FOR_RELIABLE_FORECAST_TEST | 0 | 0 | None | None | None | False | version_stability |
| strategic_aviation | INSUFFICIENT_DATA_FOR_RELIABLE_FORECAST_TEST | 0 | 0 | None | None | None | False | total_positive_alerts;development_positive_alerts;final_positive_alerts;version_stability |
| other | INSUFFICIENT_DATA_FOR_RELIABLE_FORECAST_TEST | 0 | 0 | None | None | None | False | total_positive_alerts;development_positive_alerts;final_positive_alerts;final_nonzero_weeks |

Insufficient means the specified reliable test lacks support, not physical unpredictability. No stable gain refers only to tested approaches. Inconclusive includes promising but statistically/label-unstable gains. Any EVIDENCE result is exploratory conditional marker-target evidence pending independent future annotation; no individual attack/safe-window inference. Overall Task006 B neither supplies nor precludes category evidence. Sources/classes/Task006 outputs remain hash-identical (331 prior files). No dashboard, chatbot or deployment started.

## Reproduction and checks

`.venv/bin/python -m kyiv_alerts.threat_forecastability --root . --quality-only` then `.venv/bin/python -m kyiv_alerts.threat_forecastability --root .`. Uses frozen v1.5/v1.6 alerts/markers and normalized Telegram timestamps. New tables are in data/processed/threat_forecastability_v1. No raw text exported in this task. Actual tests/repeat output checks are recorded in validation_results.json/reproducibility_results.json. Stop after Task006.1.
