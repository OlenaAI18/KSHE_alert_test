# Time-series handoff — Task 004.9

**EXPERIMENTAL — HUMAN VALIDATION REQUIRED**

Selected technical candidate: experimental v1.6, conditional on research-lead acceptance. Frozen v1.5 remains the comparison baseline. This handoff does not start time-series modeling.
Coverage: 1295/1803 eligible (71.82%); 2594 official alerts. Marker improvement stops now, regardless of the target outcome.

Use data/processed/classification_v1_6/alert_threat_features.parquet (one original alert per row) and message_threat_markers.parquet (accepted AND rejected evidence). Filter accepted_for_aggregation for evidence. Deduplicate by alert/category, not occurrence; multiple categories overlap and do not count weapons or attacks.

Unknown handling: available text without accepted attribution is unknown, never confirmed absence. Separate no-linked-text, outside historical coverage and unresolved temporal ambiguity. Retain nullable category observations; do not impute false for unavailable periods. Report eligible and text-observed denominators alongside any category fraction.

Source boundaries (UTC): Telegram 2023-08-17T10:46:25+00:00 through 2026-10-10T15:49:45+00:00; official starts 2022-02-28T03:51:22+00:00 through 2026-10-04T20:32:50+00:00; last resolved end 2026-10-04T21:38:04+00:00 (October 5 Kyiv local). October is partial. Pre-export official records support interval-only descriptions, not threat-specific comparisons. One DST-ambiguous interval remains unresolved; H2 Kyiv-seasonal Telegram normalization remains frozen.

Calendar grouping: Europe/Kyiv official start year/month. monthly_coverage.csv and yearly_coverage.csv provide every period, denominators and all four versions. Do not treat reporting-density and wording changes as physical threat regime changes.

Permitted after acceptance: retrospective descriptive alert frequency/duration, category-conditioned descriptions restricted to observed intervals, version/missingness sensitivity analysis. Unsupported: attack/weapon counts, verified cause, confirmed deployment/model, category absence from silence, forecasting individual threats, safety advice or claims that these retrospective markers were available before alert start.

Pre-alert and cross-message evidence may be confirmed only during an alert. It cannot be used as an at-start predictor without an explicit feature-availability reconstruction and an approved analytical protocol. MiG shorthand is a channel convention with unspecified model; generic UAV is a broad analytical group, not verified Shahed.

Prior diagnostic holdout remains unlabeled; all-residual v1.6 exploration is not blind independent evaluation. Compact audit is analyst source inspection, not research-lead gold.

Known unresolved review cases: 1096 target includes ballistic but pre-warning lacks admissible inside corroboration; 2581 target includes Shahed but recorded explicit sources support jet UAV. 1416 is provisional, 2590 a working hypothesis. Previous review sample/holdout has no newly inferred gold labels. Compact exception review cannot establish independent population accuracy.

Quality status: software/provenance/negative regression gates are recorded in validation_results.json. Semantic population accuracy is unmeasured; research-lead acceptance is pending. No time-series analysis or forecasting has been executed.

| Year | Eligible | v1.6 classified | Coverage |
|---|---:|---:|---:|
| 2022 | 0 | 0 | unavailable |
| 2023 | 103 | 82 | 79.61% |
| 2024 | 501 | 376 | 75.05% |
| 2025 | 510 | 378 | 74.12% |
| 2026 | 689 | 459 | 66.62% |
