# Kyiv Air Alert Time Series Analysis

A Python research project investigating temporal patterns in historical Kyiv air raid alerts, their stability across changing threat/reporting regimes, and possible aggregate predictive value. Finding no stable predictive patterns is a valid result.

Deadline: **October 12, 2026, 23:59 Europe/Kyiv**.

## Current status
Task 001 created the research architecture. Task 002 is **COMPLETE** for source ingestion, normalization and descriptive auditing of both supplied inputs: 2,594 Kyiv Digital records and 55,739 ordinary Telegram messages plus 1,252 service records from 56 HTML files. Both Parquet datasets and JSON/Markdown reports were generated; 362 tests passed and repeated real-data runs produced logically identical tables. Completion does not remove quality caveats: one alert end and eight Telegram clocks are DST-ambiguous, and service records lack exact timestamps. Task 002.1 validated H2: fixed-+02:00 Telegram title clocks are interpreted in Europe/Kyiv, preserving the original suffix. Task 003 temporal linking and descriptive coverage are COMPLETE: 32,772 links and all 2,594 official alerts retained in coverage. Task 004 classification is technically complete with v1.0 rules and a human review export; outputs are PROVISIONAL — HUMAN VALIDATION REQUIRED. Time-series analysis and forecasting remain unimplemented.

## Research boundaries
Kyiv Digital is the primary interval source; Telegram supplies contextual threat mentions, not authoritative weapon confirmation. Alerts, messages, and future links stay separate. Source timestamps are user-confirmed as aligned; no arbitrary offset is applied. Pre-Telegram alerts remain available and contextual information outside coverage is unavailable, not absent threats.

Forecasting is conditional on robust chronological out-of-sample evidence and baseline comparisons. Any experimental MVP concerns aggregate indicators only; it must not identify safe hours, predict individual attacks, replace official alert systems, or guide protective behavior.

## Installation and checks
Use Python 3.11+ in the existing checkout. Commands are portable except environment activation:

```sh
python -m venv .venv
```

Activate with `source .venv/bin/activate` on Linux/macOS or `.venv\Scripts\Activate.ps1` in Windows PowerShell, then:

```sh
python -m pip install -r requirements-dev.lock.txt -e .
python -m pytest -q
```

The lock file records tested dependency versions; it contains no machine paths or source exports. Runtime dependencies are lxml, pyarrow, tzdata and PyYAML. pytest is a development dependency. Timestamp localization uses the declared tzdata package on all platforms rather than differing OS timezone databases. Setuptools is the build backend.

## Reproduce ingestion
Place unchanged source copies in ignored `data/raw/`. A Telegram HTML-only ZIP can be used when media makes transfer impractical; its hash and archive inventory then describe that reduced ZIP, not the original full export.

```sh
python -m kyiv_alerts.ingestion --alerts "data/raw/airAlert_2026-10-10.json" --telegram "data/raw/ChatExport_2026-10-10 (1).zip" --output "data/interim" --report "reports/data_quality"
```

Outputs are `alerts.parquet`, `telegram_messages.parquet`, and JSON/Markdown audit reports. Each source is processed independently. The CLI exits nonzero for unavailable/critical source failures, writes available-source results, and records partial status. A missing source does not produce an empty fake dataset. Existing files from previous runs may remain; use the current report's `output_generated` and input hashes to identify this run's outputs. The command records elapsed times and verifies source hashes remain unchanged.

Naive timestamps are Kyiv-local. Unambiguous values become UTC; ambiguous/nonexistent DST times remain null with original values and diagnostic status preserved. Generic explicit offsets are honored; the inspected fixed-+02:00 Telegram title format uses the Kyiv wall-clock interpretation validated in Task 002.1. No interval correction is performed. An audit flag is not a deletion rule. See [DATA_SOURCES.md](docs/DATA_SOURCES.md) for observed metrics and limitations.

## Layout and data protection
`docs/` contains the charter, questions, methodology, schemas, architecture, roadmap, decisions, risks, and validation plan. `src/kyiv_alerts/ingestion/` contains source parsers, time handling, storage and CLI; `validation/quality.py` contains descriptive quality checks. Temporal integration is in `src/kyiv_alerts/integration/`; classification has a dictionary engine, aggregation and CLI; analysis and forecasting remain placeholders. `config/threat_dictionary.yaml` contains the Task 004-approved v1.0 taxonomy and provisional auditable detection rules.

Raw/interim/processed data and generated reports are ignored except `.gitkeep` files. Do not commit production exports, personal data, or sensitive notebook outputs. `.env.example` documents future path configuration; automatic dotenv loading is not implemented. Tests use minimal synthetic fixtures constructed in temporary directories, never production exports.

Start with [AGENTS.md](AGENTS.md), [the charter](docs/PROJECT_CHARTER.md), and [the roadmap](docs/ROADMAP.md). The next step is independent human review of Task 004 predictions, rule refinement and semantic validation before analytical use.


## Reproduce Task 002.1 verification
Run `python scripts/verify_time_alignment.py` from this checkout with the project installed. The script reads immutable raw sources, checks their SHA-256 hashes against `config/time_alignment_sample.json`, and writes the 28 reviewed comparisons to `reports/data_quality/time_alignment.md` and `.json`. H2 matches 28/28 within five minutes; H1 fails all 14 daylight examples. These are fixed verification examples, not a production temporal linking pipeline. See ADR 013 in `docs/DECISIONS.md`. Task 003 now uses this approved interpretation without reinterpreting original titles.


## Reproduce Task 003 temporal linking

```sh
python -m kyiv_alerts.integration --alerts data/interim/alerts.parquet --messages data/interim/telegram_messages.parquet --output data/processed --report reports/temporal_linking
```

The CLI refuses stale H1 normalized values, preserves input hashes and applies half-open `[start, end)` intervals. Outputs are ignored `alert_message_links.parquet`, `alert_coverage.parquet` and `coverage_report.json/.md`. Monthly rates distinguish genuine no-message intervals from unavailable historical coverage and unresolved timing. There are 1,707 covered alerts among 1,803 eligible resolved alerts (94.68%); 96 have no messages, 790 predate the export, and alert 1837 remains unresolved. Median messages per covered alert is six; 98.88% of linked messages have text. These are temporal reporting metrics, not threat frequencies or geographic relevance scores.

The unresolved alert receives no fabricated end or links; 15 resolved messages in its possible envelope plus eight ambiguous clocks remain excluded with source references. All 1,252 untimed service records are counted separately. The source datasets retain every unmatched/pre-coverage record. Review ADR 014 and the temporal-linking report before Task 004.

## Reproduce Task 004 classification

```sh
python -m kyiv_alerts.classification --alerts data/interim/alerts.parquet --messages data/interim/telegram_messages.parquet --links data/processed/alert_message_links.parquet --coverage data/processed/alert_coverage.parquet --dictionary config/threat_dictionary.yaml --output data/processed --report reports/classification
```

Outputs: `message_threat_markers.parquet`, `alert_threat_features.parquet`, `classification_report.json/.md`, and `validation_sample.csv`. Existing inputs are hash-checked and never rewritten. Reports distinguish accepted evidence from excluded/ambiguous candidates. All 2,594 alerts remain; generic UAVs do not imply Shahed, city and oblast stay distinct, and unknown observations remain nullable. The default human sample has 180 unique examples and blank review fields; it is for error discovery, not an unbiased precision estimate. Precision/recall are unavailable without genuine independent labels. All frequencies describe reported context, not confirmed attacks.

## Reproduce Task 004.1 geography extension

```sh
python -m kyiv_alerts.classification --geography config/kyiv_geography.yaml --output data/processed/classification_v1_1 --report reports/classification_v1_1
python -m kyiv_alerts.classification.geography_review
```

The 82-entry finite dictionary adds districts, selected neighborhoods/landmarks, inflections, abbreviations, colloquial spellings and nearby settlements. It keeps city and oblast separate, stores exact found and canonical names, and leaves unanchored ambiguous names for review. Threat taxonomy/context remain v1.0; transformation is v1.1-geo and geography dictionary is kyiv-geography-v1.0. The original Task 004 tables and reports remain unchanged.

Comparison covers all prior rejected candidates and all 3,327 previously unspecified markers. Reports contain before/after monthly yields, newly included AND newly excluded cases, the full geography-change CSV and a new 180-example review sample. A change in coverage does not establish accuracy. All outputs remain **PROVISIONAL — HUMAN VALIDATION REQUIRED**.

## Reproduce user-approved contextual rules

```sh
python -m kyiv_alerts.classification --dictionary config/threat_dictionary_v1_1.yaml --geography config/kyiv_geography_v1_1.yaml --output data/processed/classification_v1_2 --report reports/classification_v1_2
python -m kyiv_alerts.classification.reviewed_rules_report
```

The research lead's 2026-10-11 rules cover short Kyiv-locality warnings, center shorthand, movement toward Kyiv, city-alert causes involving suburbs, Kinzhal launch context, probable warnings, shakh and reactive shorthand. Exact source geography stays separate from rule-based Kyiv relevance; uncertainty and original context remain traceable. Bucha alone remains outside Kyiv City, generic UAV remains generic, and explicit jet UAV subtypes stay distinct. Previous profiles are frozen. A fresh review sample and before/after comparison are generated; rule approval does not establish independent semantic accuracy.

## Task 004.2 — read-only pattern discovery

Install the pinned local analysis dependencies, then generate diagnostics:

```bash
.venv/bin/python -m pip install -r requirements-analysis.lock.txt
.venv/bin/python -m kyiv_alerts.pattern_discovery
```

This requires the current reviewed v1.2 inputs and refuses stale/missing tables.
Review `reports/pattern_discovery/pattern_discovery_report.md`, candidate patterns,
October alert/message tables and full source examples. Human labels remain blank;
discovery neither changes classification nor validates proposed rule improvements.

## Task 004.3 — versioned alert consolidation and coverage audit

```bash
.venv/bin/python -m kyiv_alerts.classification --dictionary config/threat_dictionary_v1_3.yaml --geography config/kyiv_geography_v1_1.yaml --previous data/processed/classification_v1_2 --previous-report reports/classification_v1_2/classification_report.json --output data/processed/classification_v1_3 --report reports/classification_v1_3
```

v1.3 broadens the compatible `shahed_uav` ID to an analytical UAV group, retaining
generic versus explicit source subtypes, and moves reactive shorthand to jet_uav
with inferred uncertainty. One alert row retains distinct categories and first/all
supporting message IDs. Seven states separate classifications from unavailable
observations. Review alert_coverage_audit.md and the 28-alert unclassified sample.
Outputs remain PROVISIONAL — HUMAN VALIDATION REQUIRED; no time-series analysis
is automatically authorized or started.

Task 004.4 (provisional attribution): run `.venv/bin/python -m kyiv_alerts.attribution`.
Reports/data: `reports/attribution_experiment_v1/` and
`data/processed/attribution_experiment_v1/`. Export review files with
`.venv/bin/python scripts/export_attribution_review.py`. All new attributions and
lookbacks require human review; the production v1.3 baseline is unchanged.

Task 004.5 controlled case review: install `requirements-review.lock.txt`, then
run `.venv/bin/python -m kyiv_alerts.controlled_review`. Open
`reports/controlled_review/controlled_alert_review.xlsx`; use the alert-ID links
to read each complete timeline before filling blank human review fields.
`.venv/bin/python scripts/export_controlled_review.py` makes downloadable copies.
This is a purposive diagnostic sample; no classifier corrections are implemented.

Task 004.6: `.venv/bin/python -m kyiv_alerts.classification_v14` generates isolated
experimental v1.4 Parquet and comparison reports. Four rule-disabled ablations
measure overlapping contributions. User-confirmed banderol means jet UAV; no
model inference. The reviewed 2581 label discrepancy remains explicitly unresolved
by research-lead choice. No population accuracy claim follows from increased yield.
Run `.venv/bin/python scripts/export_v14_review.py` for an Excel review workbook
and delivery copies. All outputs: EXPERIMENTAL — HUMAN VALIDATION REQUIRED.

Task 004.7: `.venv/bin/python -m kyiv_alerts.residual_review --root .` creates
read-only diagnostics for all 655 text residuals, a separate audit of 98 no-text
cases and a 40+10 review workbook. Outputs are under
`reports/classification_v1_4/residual_review/`; open `residual_review_50.xlsx` and
read each full timeline before filling Human Review. Supplementary CSV preserves
complete pre-alert/post-alert boundary context. Exact grouping/sampling rules are
in `residual_segment_summary.md`. No classifier or baseline is modified.
Status: DIAGNOSTIC — HUMAN REVIEW REQUIRED. Stop for manual review; no v1.5.

Task0048 explicitly authorizes isolated experimental v1.5. Run
`.venv/bin/python -m kyiv_alerts.classification_v15 --root .` for the full comparison,
five correction ablations, reviewed-case regression table and 20-case Excel audit.
Outputs are in `data/processed/classification_v1_5/` and
`reports/classification_v1_5/`. v1.3/v1.4 and source timestamps/intervals remain
immutable. 1096's confirmed two-category target and the prior 2581 discrepancy
remain explicitly unresolved by automatic attribution; no alert-ID overrides.
Status: EXPERIMENTAL — HUMAN VALIDATION REQUIRED. Stop after Task0048; no automatic
commit or forecasting.

## Task 004.9: experimental v1.6 handoff

```bash
.venv/bin/python -m kyiv_alerts.classification_v16 --root .
.venv/bin/python -m pytest -q
```

v1.6 classifies **1295 / 1803 eligible alerts (71.82%)**, versus 1141 in v1.5.
155 alerts gain attribution and one loses an invalid absence-based attribution.
Original sources and all previous versions remain frozen. Separate outputs live
under `data/processed/classification_v1_6/` and `reports/classification_v1_6/`.
See `classification_comparison.md`, all-564 `residual_diagnostics.csv`,
`validation_results.json` and `time_series_handoff.md` there.

**EXPERIMENTAL — HUMAN VALIDATION REQUIRED.** The global coverage target is met;
accuracy remains unmeasured and 2026 coverage is 66.62%. Marker development stops
here. Handoff is conditional on research-lead acceptance; no forecasting or
automatic commit is performed.

## Task005 — temporal diagnostics

Experimental v1.6 primary; official frequency analysis remains independent of
Telegram interpretation. Install `requirements-temporal.lock.txt` after existing
analysis/dev requirements, then run:

```sh
python -m kyiv_alerts.temporal_analysis --root .
python -m pytest
```

Review `reports/temporal_analysis/temporal_analysis_report.md` and
`forecasting_readiness.md`; four derived Parquet tables are under
`data/processed/temporal_analysis/`. Original data/classifiers are preserved.
No forecasting model is implemented. Task005 supersedes the old roadmap's
numbering for this explicitly requested temporal-analysis scope.

## Task005.1 — external validation

Read [the external validation report](reports/external_validation/external_validation_report.md)
and [Task006 handoff](reports/external_validation/task006_handoff.md).
Official records are confirmed, but the September 2026 warning-level transition
limits comparison over time. External positive category support is not accuracy.
599 tests pass; original sources and v1.6 remain unchanged. Task006 is not started.
Download the [review bundle](review_downloads/task0051/task0051_external_validation_bundle.zip).

## Task006 — retrospective forecastability validation

Run `.venv/bin/python -m kyiv_alerts.forecastability --root .` using the existing
analysis/temporal locked dependencies and frozen Task005 fact table.
Read [forecastability report](reports/forecastability_validation/forecastability_report.md)
and [Ukrainian MVP decision](reports/forecastability_validation/mvp_decision.md).
All official warning colors are retained. The2026 final holdout does not show
stable candidate improvement over recent baselines: **B — NO_STABLE_GAIN_OVER_BASELINES**.
No dashboard, chatbot or operational deployment is implemented.

## Source code and reproduction

All implementation modules are directly available under `src/kyiv_alerts/`,
with command-line helpers in `scripts/`, regression tests in `tests/`, and
versioned dictionaries/policies in `config/`. Python packaging is defined in
`pyproject.toml`; tested dependency versions are in `requirements-*.lock.txt`.
Raw source exports and external snapshots remain excluded from Git. Full real-data
reproduction and the full test suite require the frozen original inputs and derived
artifacts. A fresh clone provides the code, but does not contain the complete data
workspace; missing artifact-dependent inputs can cause checks to fail.

## Task006.1 — threat-specific reported-marker assessment

Run `.venv/bin/python -m kyiv_alerts.threat_forecastability --root . --quality-only`
then `.venv/bin/python -m kyiv_alerts.threat_forecastability --root .`.
Read [the report](reports/threat_forecastability/threat_forecastability_report.md)
and [category decisions](reports/threat_forecastability/category_decision_matrix.csv).
Two categories pass the frozen exploratory gate: broad UAV (inconclusive) and
ballistic/high-speed (no stable gain). Five fail the data/stability gate. Counts
represent reported markers; hindsight taxonomy prevents blind prospective validation.
Classification versions and Task006 results are unchanged. No dashboard or deployment.

## Task007 — Ukrainian static research dashboard

Six research sections and interactive charts present frozen historical results,
with public aggregate JSON only. See [dashboard instructions](dashboard/README.md)
and [validation](reports/dashboard/validation_report.md). From `dashboard/` run
`npm install`, `npm test`, `npm run dev`, `npm run build`. A clone needs no private
inputs to display the dashboard. Manual GitHub Pages workflow is prepared; public
hosting is not activated and requires research-lead approval. No live forecasts/chat.
