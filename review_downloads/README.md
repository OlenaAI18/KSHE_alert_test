# Excel review files

Open an `.xlsx` file on GitHub and click **Download raw file** (the download arrow).
Save it and open it in Excel Desktop.

- `task0045_controlled_alert_review.xlsx`: controlled diagnostic sample, full message timelines and decision traces. DIAGNOSTIC SAMPLE — HUMAN REVIEW REQUIRED.
- `task0044_attribution_review.xlsx`: provisional inside-interval and pre-alert-window evidence.
- `task0043_alert_review.xlsx`: v1.3 alert-level classification and coverage audit.
- `task0042_pattern_review.xlsx`: exploratory pattern discovery.
- `task0041_geography_review.xlsx`: geographic dictionary review.
- `task004_reviewed_rules_review.xlsx`: reviewed-rule comparison.
- `validation_sample.xlsx`: initial classification review sample.

Experimental evidence is provisional and is not independently validated classification accuracy or confirmation of weapon deployment. Human review fields remain blank.

## Task 004.6 — experimental v1.4

Open [classification_review.xlsx](task0046/classification_review.xlsx) and click
**Download raw file**. The [comparison report](task0046/classification_comparison.md)
and CSV/JSON files in [task0046](task0046/) accompany the workbook.

437 → 1,050 experimental alert classifications; 613 new, zero lost. Coverage
increase is not verified accuracy. The research lead chose to keep the 2581 label
discrepancy for review; 2590 remains an unconfirmed working hypothesis.
All new associations remain EXPERIMENTAL — HUMAN VALIDATION REQUIRED.

## Task 004.7 — residual uncertainty review

Open [residual_review_50.xlsx](task0047/residual_review_50.xlsx) and click
**Download raw file**. Read the complete **Full Timeline** for each alert, then
fill the blank fields in **Human Review**. The workbook contains 40 residual
alerts and 10 newly classified safety cases; A–F are diagnostic hypotheses.

The [summary](task0047/residual_segment_summary.md) documents exact grouping and
selection rules. [All CSV/JSON files](task0047/) include full in-alert chronology,
separate pre-alert evidence, supplementary post-alert boundary context, all 655
residual features and the separate audit of 98 no-text cases. The latter consists
of 96 alerts without linked records and two with only empty-text records.

v1.3/v1.4, dictionaries, source timestamps and temporal links are unchanged.
**DIAGNOSTIC — HUMAN REVIEW REQUIRED.** No v1.5 is implemented.

## Task 004.8 — experimental v1.5 audit

Open [false_positive_audit_20.xlsx](task0048/false_positive_audit_20.xlsx) and click
**Download raw file**. The workbook contains 20 audit cases, full in-alert
timelines, separate pre-alert evidence and blank human review fields.

**EXPERIMENTAL — HUMAN VALIDATION REQUIRED.** Coverage gains are not validated
classification accuracy.

## Task 004.9 — experimental v1.6 handoff

Download [task0049_v16_bundle.zip](task0049/task0049_v16_bundle.zip) using
**Download raw file**. The archive contains derived Parquet datasets, CSV/JSON
reports, v1.6 implementation, tests and documentation; raw exports are excluded.
Reproduction requires the existing workspace with frozen earlier inputs/profiles.

Read the [comparison report](task0049/classification_comparison.md) and
[time-series handoff](task0049/time_series_handoff.md).

1,295 / 1,803 eligible alerts (71.82%); 155 gains and one loss versus v1.5.
582 tests and 20 compact source checks passed. Coverage is not measured accuracy.
**EXPERIMENTAL — HUMAN VALIDATION REQUIRED.** Marker development has stopped;
analytical adoption remains subject to research-lead acceptance.

## Task005 — temporal diagnostics

Read the [Ukrainian execution summary](../reports/temporal_analysis/execution_summary.md),
[full analysis](../reports/temporal_analysis/temporal_analysis_report.md) and
[forecasting readiness](../reports/temporal_analysis/forecasting_readiness.md).
Figures and CSV evidence are directly viewable in
[reports/temporal_analysis](../reports/temporal_analysis/).

Download [task005_temporal_bundle.zip](task005/task005_temporal_bundle.zip) with
**Download raw file**. It contains four analytical Parquet tables, all Task005
reports/figures, implementation/tests and updated documentation. Original raw
exports are excluded. Reproduction requires the existing frozen source/earlier
classification workspace; the ZIP is an overlay, not a complete private dataset.

591 tests passed. Recommendation: **FURTHER_VALIDATION_NEEDED**. No forecasting
model. Task005 explicitly adopts v1.6 for exploratory analysis without approving
classifier accuracy. Unknowns and original timestamps remain preserved.

## Task005.1 — external validation

Read [the full report](../reports/external_validation/external_validation_report.md)
and [Task006 handoff](../reports/external_validation/task006_handoff.md).
Download [task0051_external_validation_bundle.zip](task0051/task0051_external_validation_bundle.zip)
using **Download raw file**. It contains reports, figures, new implementation,
tests and documentation. Raw exports are excluded. This is an overlay requiring
the existing frozen workspace and external caches; source URLs, pinned commits
and hashes are recorded in the reports. 599 tests pass; Task006 is not started.

## Task006 — retrospective forecastability validation

Read [the full report](../reports/forecastability_validation/forecastability_report.md)
and [Ukrainian MVP decision](../reports/forecastability_validation/mvp_decision.md).
Download [task006_forecastability_bundle.zip](task006/task006_forecastability_bundle.zip)
using **Download raw file**. Contains derived weekly/prediction Parquet tables,
all reports/figures, new implementation/tests and documentation; no raw exports.
Reproduction requires the existing package/workspace and frozen Task005 fact table.
613 tests pass. Decision **B — NO_STABLE_GAIN_OVER_BASELINES**; all official colors
retained. No dashboard/chatbot/live forecast/deployment started.

## Task006.1 — threat-specific reported-marker assessment

Read [the report](../reports/threat_forecastability/threat_forecastability_report.md)
and [category decisions](../reports/threat_forecastability/category_decision_matrix.csv).
Download [task0061_threat_forecastability_bundle.zip](task0061/task0061_threat_forecastability_bundle.zip)
using **Download raw file**. Includes derived weekly/forecast Parquet tables,
reports/figures and new code/config/tests; no original message text or raw exports.
Code is also directly available in src/kyiv_alerts/threat_forecastability.
Requires the existing frozen v1.5/v1.6 source artifacts and normalized Telegram
inputs for reproduction. 626 tests pass. Broad UAV: inconclusive; ballistic: no
stable gain; five other categories fail fixed data/stability gates. Marker counts
are not true threat incidence. No dashboard or live forecast/deployment.
