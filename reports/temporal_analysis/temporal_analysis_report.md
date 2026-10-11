# Task005 — Temporal analysis and quality diagnostics

Status: COMPLETE; retrospective exploratory diagnostics, no forecast model. v1.6 is the user-authorized primary experimental interpretation, not validated ground truth.

## Populations, time and observation

Baseline: {"official": 2594, "eligible": 1803, "classified": 1295, "text_unknown": 410, "no_text": 98, "outside": 790, "unresolved": 1}. Fact table retains all 2594 source IDs and original timestamps. Population A has 2593 resolved intervals; Population B has 1803 eligible alerts, 1295 classified and 508 unknown (410 text / 98 no text). Another 790 are outside Telegram history and one is unresolved. A never requires a threat label. Category flags denote detected context, not evidence of absence when false.

Official observed span: 2022-02-28T05:51:22+02:00 to 2026-10-05T00:38:04+03:00; Telegram: 2023-08-17T10:46:25+00:00 to 2026-10-10T15:49:45+00:00. Daily zeros are inserted only inside the official span; availability does not prove complete recording. The final official event predates the export cutoff; no silent zeros extend to October10. February2022 and October2026 are partial. Endpoint days are excluded from inferential daily checks. Source timestamps are never corrected here; accepted H2 and Europe/Kyiv calendars are reused. Calendar days can have 1380/1500 minutes.

## Official counts and durations

Yearly table (all records versus resolved intervals are separate; incomplete years are descriptive):

| period | days | partial_period | all_records | official_valid | starts_per_day | duration_median | union_minutes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2022 | 307 | True | 592 | 592 | 1.928 | 48.950 | 37311.933 |
| 2023 | 365 | False | 301 | 301 | 0.825 | 55.183 | 24106.917 |
| 2024 | 366 | False | 501 | 501 | 1.369 | 33.917 | 32485.300 |
| 2025 | 365 | False | 511 | 510 | 1.397 | 34.683 | 44347.367 |
| 2026 | 278 | True | 689 | 689 | 2.478 | 30.433 | 39719.617 |

[Monthly counts](figures/official_monthly_counts.png). Monthly and quarterly details: [monthly_official_summary.csv](monthly_official_summary.csv), [quarterly_summary.csv](quarterly_summary.csv); weekly counts: [weekly_summary.csv](weekly_summary.csv). [Monthly rate](figures/official_monthly_rate.png), [daily counts](figures/official_daily_counts.png).

Resolved duration median=37.37 minutes, mean=68.64, p90=158.00, maximum=764.07. Total calendar-split interval-union minutes=177971.13. Actual resolved source intervals do not overlap: sum durations equals union. Synthetic overlap regression tests verify union behavior rather than assuming that equality generally. [Duration distribution](figures/duration_distribution.png). Inter-start gaps (including the known start of the DST case) median=7.45 hours, p90=38.56; [gap distribution](figures/start_gap_distribution.png). These summaries do not identify safe periods.

Recent months (October partial, never treated as a whole month):

| month | days_observed | partial_month | official_alert_starts | official_starts_per_observed_day | eligible | classified | unknown_rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-07 | 31 | False | 59 | 1.903 | 59 | 37 | 0.373 |
| 2026-08 | 31 | False | 121 | 3.903 | 121 | 88 | 0.273 |
| 2026-09 | 30 | False | 190 | 6.333 | 190 | 131 | 0.311 |
| 2026-10 | 5 | True | 42 | 8.400 | 42 | 23 | 0.452 |

## Dependence-aware exploratory statistics

Analytical plan fixed in ADR026 before calculation: daily counts, 14-day circular moving blocks, seed20261011,1200 replicates, 7/28-day sensitivity; weekly blocks8 weeks. Effects and pointwise 95% intervals are exploratory, not simultaneous confidence sets. Nonstationarity limits pooled resampling. No IID Poisson test, uncalibrated change-point scan or independently validated seasonal conclusion is reported. All results and assumptions: [statistical_tests.csv](statistical_tests.csv).

Pooled daily variance/mean=2.073 (14-day block CI 1.485–2.632), relative to equidispersed reference1. This includes changing mean regimes. Raw daily lag1 correlation=0.466 (CI 0.224–0.566); after removing monthly means, lag1=0.073 (CI -0.038–0.195). Thus the strong-looking raw persistence largely disappears after controlling changing monthly activity; it is not evidence of stable day-level predictability. Long-lag bootstrap ACF is biased by block joins, especially lags at/above block size: interpret raw long-lag values descriptively and do not use their CIs as calibrated evidence. Daily/weekly persistence and changing mean activity justify prospective aggregate validation, not individual attack prediction.

Complete-year and seasonal contrasts:

| test | effect | ci_low | ci_high | p_value | holm_p | method |
| --- | --- | --- | --- | --- | --- | --- |
| season_DJF_vs_rest | -0.070 | -0.304 | 0.159 | 0.551 | 1.000 | equal-year seasonal differences; joint day block bootstrap; approximate bootstrap-SE Wald p |
| season_MAM_vs_rest | -0.161 | -0.361 | 0.021 | 0.097 | 0.291 | equal-year seasonal differences; joint day block bootstrap; approximate bootstrap-SE Wald p |
| season_JJA_vs_rest | 0.197 | 0.009 | 0.401 | 0.049 | 0.197 | equal-year seasonal differences; joint day block bootstrap; approximate bootstrap-SE Wald p |
| season_SON_vs_rest | 0.035 | -0.137 | 0.233 | 0.709 | 1.000 | equal-year seasonal differences; joint day block bootstrap; approximate bootstrap-SE Wald p |
| year_mean_2024_minus_2023 | 0.544 | 0.320 | 0.774 | None | None | separate within-year 14-day moving blocks |
| year_mean_2025_minus_2024 | 0.028 | -0.215 | 0.263 | None | None | separate within-year 14-day moving blocks |

Season contrasts use complete2023–2025, equal-year differences versus other months, not incomplete2022/2026. No seasonal contrast survives the four-comparison Holm screen; three annual cycles and regime/reporting changes cannot identify stable physical seasonality. Adjacent-year contrasts describe broad changes, not a uniquely located or causal structural break. Monthly evolution is plotted rather than tested in dozens of post-hoc pairwise tests.

## Reported categories and missingness

| category | count | share_classified | share_eligible | median | p90 |
| --- | --- | --- | --- | --- | --- |
| shahed_uav | 630 | 0.486 | 0.349 | 78.783 | 304.562 |
| jet_uav | 131 | 0.101 | 0.073 | 65.250 | 248.517 |
| ballistic_high_speed | 458 | 0.354 | 0.254 | 30.367 | 201.800 |
| cruise_missile | 99 | 0.076 | 0.055 | 153.467 | 474.983 |
| mig31 | 293 | 0.226 | 0.163 | 34.950 | 173.187 |
| strategic_aviation | 77 | 0.059 | 0.043 | 174.117 | 467.153 |
| other | 70 | 0.054 | 0.039 | 162.025 | 493.460 |

Categories are context attribution, never confirmed launches/impacts. shahed_uav includes generic non-jet UAV; mig31 includes approved uncertain channel shorthand without verified model. Multiple categories can occur in the same alert; totals must not be added into mutually exclusive counts. [Category overlap](category_overlap.csv), [yearly category table](category_yearly.csv), [monthly category table](threat_category_monthly.csv), [monthly shares](figures/category_monthly_shares.png).

Duration associations versus other classified alerts, monthly-demeaned log(1+minutes), daily cluster/block uncertainty and Holm correction across7 categories:

| test | effect | ci_low | ci_high | p_value | holm_p |
| --- | --- | --- | --- | --- | --- |
| duration_month_adjusted_shahed_uav | 0.770 | 0.634 | 0.915 | 0.000 | 0.000 |
| duration_month_adjusted_jet_uav | 0.435 | 0.271 | 0.663 | 0.000 | 0.000 |
| duration_month_adjusted_ballistic_high_speed | -0.203 | -0.328 | -0.079 | 0.001 | 0.003 |
| duration_month_adjusted_cruise_missile | 1.169 | 0.936 | 1.413 | 0.000 | 0.000 |
| duration_month_adjusted_mig31 | 0.023 | -0.109 | 0.163 | 0.744 | 0.744 |
| duration_month_adjusted_strategic_aviation | 1.152 | 0.916 | 1.402 | 0.000 | 0.000 |
| duration_month_adjusted_other | 1.077 | 0.811 | 1.347 | 0.000 | 0.000 |

Positive values mean longer reported-context intervals after retrospective month-centering. Categories overlap and month-centering does not adjust every confounder. Bootstrap-SE Wald p-values are approximate exploratory screening, not independent gold validation. No causal weapon-duration conclusion follows. See raw duration distributions above and population sensitivity table.

## Source and classifier stability

[Classification yield/unknown](figures/classification_coverage.png), [message volume](figures/message_volume.png), [classification_stability.csv](classification_stability.csv). Source-span eligibility is not continuous channel availability. Monthly message medians and unknown rates vary, including increased recent unknown rates; reporting vocabulary is documented in [vocabulary_yearly.csv](vocabulary_yearly.csv), counting unique alert support, not token repetition. Inference from lexical variation to physical activity is not supported.

| version | eligible | classified | shahed_uav | jet_uav | ballistic_high_speed | cruise_missile | mig31 | strategic_aviation | other |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v1_4 | 1803 | 1050 | 596 | 130 | 273 | 89 | 173 | 60 | 67 |
| v1_5 | 1803 | 1141 | 603 | 128 | 360 | 94 | 195 | 62 | 72 |
| v1_6 | 1803 | 1295 | 630 | 131 | 458 | 99 | 293 | 77 | 70 |

Accepted uncertainty by category is tabulated in [category_evidence_uncertainty.csv](category_evidence_uncertainty.csv); any uncertain evidence does not imply all supporting messages are uncertain. Context-reference rows without a lexical expression are explicitly flagged in the vocabulary table and must not be counted as new lexical vocabulary.

[Version plot](figures/version_category_counts.png). Exactly101 previously-classified alerts changed combinations v1.5→v1.6 (8.85% of1141 previously classified); this excludes155 gains and1 loss. Full counted transitions: [category_transitions_101.csv](category_transitions_101.csv), IDs in [changed_previously_classified_alerts.csv](changed_previously_classified_alerts.csv). Category shifts are classifier instability, not new historical events. Known1096/2581 label/source discrepancies and unlabeled independent holdout persist.

## Sensitivity and uncertainty

[sensitivity_populations.csv](sensitivity_populations.csv) compares A, B, classified-only, unknown separately and B excluding weak months. Weak threshold fixed before analysis: classification yield below60%, at least10 eligible alerts, purely a reporting-quality screen. Weak months: 2023-09, 2025-05, 2026-01, 2026-02, 2026-03, 2026-10. [sensitivity_category_trends.csv](sensitivity_category_trends.csv) reports descriptive linear share slopes on full Telegram calendar months for both versions with/without weak months. Slopes are descriptive associations, not fitted forecasts or calibrated trend significance. Unknowns remain in eligible denominator. Version comparisons and classified-only filtering alter counts/duration distributions; conclusions about absolute physical category incidence cannot survive these observation choices. The analysis never imputes unknown labels. Zero detected categories in unknown rows does not establish zero physical threats.

Concrete sensitivity findings:

| population | n | median | mean | p90 | unknown |
| --- | --- | --- | --- | --- | --- |
| all_valid_official | 2593 | 37.367 | 68.635 | 158.000 | 1298 |
| eligible | 1803 | 33.567 | 68.749 | 168.687 | 508 |
| classified_v16 | 1295 | 38.383 | 81.115 | 205.553 | 0 |
| unknown_eligible_v16 | 508 | 26.133 | 37.226 | 71.342 | 508 |
| eligible_excluding_weak_months | 1568 | 33.883 | 70.164 | 170.118 | 401 |

The classified-only mean duration is 81.11 minutes versus 68.75 for all eligible and 37.23 for eligible unknowns. Dropping unknowns selects longer intervals and raises the mean by 18.0%. The ballistic share slope reverses from positive under v1.5 to negative under v1.6, and the v1.5 positive slope nearly disappears after excluding weak months; these are descriptive signs, not significant physical trends. Exact slopes per month are in sensitivity_category_trends.csv. Generic-UAV/jet positive and MiG negative descriptive slope directions persist across these checks, but both classifier and publication changes remain alternative explanations. Raw official lag1 persistence becomes small after monthly centering; nominal summer association disappears under Holm correction. These disappearing findings prevent a stable forecasting claim.

DST alert 1837: original 2025-10-26T02:27:00 → 2025-10-26T03:05:12. Source end remains null. Candidate folds ['2025-10-26T00:05:12+00:00', '2025-10-26T01:05:12+00:00']; duration bounds [38.2, 98.2] minutes; added union bounds [38.2, 98.2] minutes. Primary A excludes its start/duration; all-record frequency sensitivity adds its known single start. B excludes it. Daily unresolved flag identifies lower-bound union time. This tiny count difference cannot justify selecting an endpoint.

## Reproducibility and validation

Run `.venv/bin/python -m kyiv_alerts.temporal_analysis --root .`; install plotting requirements from `requirements-temporal.lock.txt` after existing analysis/dev dependencies. Inputs and all earlier source/config/classifier/report hashes are recorded in temporal_summary.json and checked unchanged. Generated Parquet tables retain local-zone aware timestamps and source identifiers; rates are null when no eligible observations, categories unavailable before Telegram. Tests cover DST day lengths, overlap unions, half-open midnight, counts, unknowns, transitions and deterministic resampling. Complete-suite actual outcome is recorded in validation_results.json after execution. No forecasting or Task006 implementation.

Recommendation: **FURTHER_VALIDATION_NEEDED**; see [forecasting_readiness.md](forecasting_readiness.md).
