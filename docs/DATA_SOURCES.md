# Data sources and observed intake

## A: Kyiv Digital — processed real input
File: `airAlert_2026-10-10.json`; JSON array, **2,594 records**, **797,208 bytes**.

SHA-256: `0c9ef4fc776ef695d818127ff5d11f9a9e994acf703c063e97b89f332c07e44b`.

Observed Europe/Kyiv times: first start **2022-02-28 05:51:22 +02:00**, last start **2026-10-04 23:32:50 +03:00**, latest resolved end **2026-10-05 00:38:04 +03:00**. The export filename does not establish coverage through October 10.

Observed fields: `uid`, `CATUTTC`, `addressAdminUnitL1`, `addressAdminUnitL2`, `addressPostName`, `type`, `level`, `cause`, `dateTimeStart`, `dateTimeEnd`. All original objects are retained in `raw_record_json` and traced with zero-based `source_record_index` plus filename/hash inventory. `uid` is normalized to string; native null and literal `"null"` become missing in normalized fields while raw values remain recoverable.

All 2,594 starts parse; 2,593 ends parse unambiguously. Alert `uid=1837` (source index 1836) ends at `2025-10-26T03:05:12`, a Kyiv-local repeated DST time. No fold is guessed: end UTC and duration remain null, with `end_ambiguous` status. Its original end is preserved. No invalid-format timestamps, nonexistent times, reversed/zero intervals, duplicate IDs/raw records/intervals, or unexpected geographic codes were found. No overlaps were found **among the 2,593 intervals with resolved positive duration**; the ambiguous interval cannot be fully audited for overlaps.

`cause` and `level` are null in 2,400 records each. Eight durations are below the diagnostic 1-minute threshold; none exceed 24 hours. Two resolved-interval gaps exceed the diagnostic 7-day threshold. These are review flags, not proof of source errors or grounds for deletion. Monthly counts cover 57 calendar months in Europe/Kyiv and sum to 2,594. No records were skipped. Hash checks confirmed the raw copy and supplied attachment are identical and unchanged.

## B: Telegram — processed real supplied archive
File: `ChatExport_2026-10-10 (1).zip`; **5,873,514 bytes**, **61 archive members**, including **56 message HTML files** (75,436,583 uncompressed HTML bytes). No media were read or extracted. This supplied compact archive has its own hash; it is not claimed to be byte-identical to the earlier oversized attachment.

SHA-256: `8225e1a3e886671cfb24257d2e3b7effe549a4245c5c042af3cfaf93e1a7ee61`.

Observed channel title: Український Єнот. Extracted **56,991 records**: **55,739 ordinary messages** and **1,252 service records**. Service records include 1,205 date headings with negative export IDs and 47 positively identified service events. Negative heading IDs are preserved as HTML evidence, not invented genuine Telegram IDs. All service records lack exact timestamp titles and remain null in UTC; their readable body text is retained. The initial Task 002 H1 interpretation resolved all 55,739 ordinary timestamps using the explicit suffix. Task 002.1 empirically validated H2 (Kyiv wall clock): 55,731 ordinary timestamps now resolve, while eight repeated-hour values remain DST-ambiguous and null. No invalid-format or nonexistent ordinary timestamps, duplicated genuine IDs, skipped records, unsafe HTML paths, or HTML recovery/parse errors were observed.

First ordinary timestamp: **2023-08-17 13:46:25 UTC+02:00**; last: **2026-10-10 18:49:45 UTC+02:00**. Under validated H2, the displayed clocks are Europe/Kyiv **2023-08-17 13:46:25 +03:00** and **2026-10-10 18:49:45 +03:00**, respectively; the original export titles remain unchanged. The earlier H1 normalization (one hour later in summer) is superseded by ADR 013. A heading indicates channel creation on August 11 but lacks an exact time and is not substituted for message coverage.

There are **2,339 ordinary messages without text**; these remain records, and no OCR/media decoding is attempted. Forwarded sender metadata was captured for 1,027 records and reply IDs for 18,628. No recognized edit-title metadata was present; `edited_at` remains null rather than inferred. After H2 normalization, monthly timestamped-message counts cover 39 local calendar months and sum to 55,731. The eight ambiguous records remain in Parquet and are separately reported, not deleted or assigned a fold. There are five posting gaps over 24 hours (maximum approximately 44.49 hours); these are not evidence of absent threats. After natural page ordering (`messages.html`, `messages2.html`, ..., `messages10.html`), valid message timestamps are nondecreasing. ZIP bytes and hashes were verified unchanged.

Initial Task 002 measured ingestion runs (before Task 002.1 normalization): Kyiv Digital approximately 0.11 seconds, Telegram approximately 4.68 seconds; Telegram HTML parsing approximately 3.50 seconds is the main measured cost. Runtime includes hashing, parsing, audit, Parquet writing/readback verification, and final source hash checking. No multiprocessing is justified by these measurements. Repeated runs produce logically identical rows and ordering; timing measurements themselves vary.

## Implemented HTML parser and limitations
The parser opens HTML ZIP members individually in deterministic natural filename/page order and never reads/extracts media. It discovers message-bearing HTML dynamically, uses lxml recovery, decodes entities, retains line breaks/readable text, and handles service and joined/continuation message structures. Recoverable HTML diagnostics are reported; unreadable members and unsafe paths are reported as critical failures. Exact record loss in unreadable/malformed source members cannot always be determined.

Main date-title metadata is used when present. Missing timestamps remain unknown; no sender/date inheritance is guessed. Forwarded sender and reply anchors are captured in recognized structures; edit titles are preserved as raw `edited_at` metadata rather than guessed normalized times. Missing/unrecognized metadata remains null. Original outer formatting whitespace is stripped from readable text; content is not keyword-filtered. No NLP/OCR/classification is performed.

Nonnegative `messageN` identifiers are preserved as source message IDs within this single-export scope. Negative service-heading export IDs are retained in `source_html_id`, not misrepresented as genuine Telegram IDs. Missing IDs are not replaced with row numbers; `source_file` plus zero-based `source_message_index` provides traceability. Repeated genuine IDs retain the first deterministic occurrence; all later occurrences and any content conflicts remain in the JSON audit with full duplicate-record evidence. Cross-channel uniqueness is not established; this parser is for a single-channel export. Real export validation confirmed the observed ordinary, joined, service-heading and service-event structures; other export formats remain untested.

## Timestamp and interpretation contract
Naive source timestamps are Kyiv-local, as requested; no arbitrary offset is added. Round-trip checks for both DST folds identify ambiguity/nonexistence. Unambiguous times normalize to UTC, with original strings retained. Generic explicit ISO offsets and other export offsets retain their semantics. For this verified fixed-+02:00 Telegram title format, the displayed clock is localized in Europe/Kyiv (H2), not treated as an absolute +02:00 instant; see ADR 013 and the time-alignment report. The packaged tzdata version is recorded for reproducibility; local month boundaries use Europe/Kyiv. Duration is elapsed UTC time, not naive wall-clock subtraction.

Telegram provides contextual reports, not authoritative weapon confirmation. Preserve earlier official alerts. Absence of Telegram records outside coverage or within publication gaps does not establish absence of threats. Posting frequency is not attack frequency. The observed timestamped coverage intersection is **2023-08-17T10:46:25Z–2026-10-04T21:38:04Z**, or **2023-08-17 13:46:25 +03:00–2026-10-05 00:38:04 +03:00** in Europe/Kyiv. This is date-range intersection only, not record-level temporal linking.

## Verified timestamp interpretation — Task 002.1

H2 is supported by 28 reviewed Kyiv-specific beginning/end announcements: 14 standard-time and 14 daylight-time examples spanning 2023–2026, including near-DST dates. Against fixed manually reviewed official boundaries, H2 matches **28/28 within five minutes**, median absolute difference **1.442 minutes**. H1 matches 14/28 overall, entirely in standard time; daylight H1 matches 0/14, median absolute difference 61.758 minutes, compared with H2's 14/14 and 2.075 minutes. Per-message signed differences, geography/text exclusions, publication-lag sensitivity and source provenance are in `reports/data_quality/time_alignment.md` and `.json`.

The source-specific normalization rule is implemented in `parse_telegram_time`: localize displayed clocks from the inspected fixed-+02:00 format to Europe/Kyiv, then convert unique instants to UTC. Raw titles are unchanged. Generic timestamp parsing still honors actual offsets in other formats. The rule is seasonal localization, not a global subtraction. The H1 summer instants generated during Task 002 have been replaced in the derived Parquet; raw source files are unchanged.

All 55,739 original ordinary titles still contain +02:00. For 35,454 resolved readings the suffix differs from Kyiv's seasonal offset; eight more have unresolved DST comparisons. IDs **35434–35441**, at 03:05–03:42 on 2025-10-26, fall in a repeated hour and now have null UTC timestamps with `ambiguous` status. Their source records and text remain retained. No nonexistent local clocks were observed.

Official alert **1837** ends at 2025-10-26T03:05:12: either 00:05:12Z (+03:00 fold) or 01:05:12Z (+02:00 fold), with durations 38.2 or 98.2 minutes. Both are chronologically possible. Nearby Telegram messages concern reconnaissance/district reports, not an unambiguous Kyiv all-clear; they do not resolve the fold. The official end/duration remain null. No source time is automatically corrected.

This verification is a purposive consistency check, not proof of perfect event matching across the full corpus. Exact repeated-hour ambiguity remains unresolved; Task 003 must address it explicitly. No production alert-message links were generated. Reproduce the comparison with `python scripts/verify_time_alignment.py` after installing the project; source hashes and frozen sample references are verified on each run.

## Evidence locations
`data/interim/alerts.parquet`, `data/interim/telegram_messages.parquet`, `reports/data_quality/source_inventory.json`, `reports/data_quality/data_quality_report.json`, and `.md` are local ignored outputs. Reports include source hashes, software versions, monthly counts, missing fields, traceable anomaly references, thresholds and runtimes. Task 002 ingestion and auditing are COMPLETE; raw inputs and generated results remain ignored by Git. Task 002.1 adds a narrowly scoped reviewed-example alignment audit. No classification, production temporal linking, or time-series analysis has been performed.

### Reviewed contextual interpretation (2026-10-11)

The research lead approved locality bulletins (Troya, DVRZ, center), movement
from suburbs toward Kyiv, explicit Kyiv alert causes, bare Kinzhal launch
warnings, inclusion of probable operational warnings, and Shakh/reactive
shorthand. Bucha alone remains outside Kyiv. These are versioned interpretation
rules, not changes to source records or independent verification of weapon type.
Use `config/threat_dictionary_v1_1.yaml` together with
`config/kyiv_geography_v1_1.yaml`; results are in
`data/processed/classification_v1_2/`. Original timestamps/text and literal
geography are preserved; relevance, rule provenance and uncertainty are separate
fields. Coverage comparison and 180 review examples are in
`reports/classification_v1_2/`. Classified eligible alerts: 274 → 437,
15.20% → 24.24%. The source/temporal linking datasets are unchanged.

### Task 004.2 derived discovery artifacts

The diagnostic pipeline reads only current reviewed v1.2 classification and Task
003 links, and verifies input hashes against previous reports. Word/character
normalization is an analysis copy; original text/time/file/index remain review
provenance. Official intervals stop at 2026-10-05 00:38:04 Europe/Kyiv (last start
2026-10-04 23:32:50), while the Telegram source extends to 2026-10-10 18:49:45.
October alert-level observations therefore cover only a partial month. Later
Telegram messages outside available official intervals do not enter this task.
No source/dictionary/classification output is modified. Reports are under
`reports/pattern_discovery/`; XLSX/ZIP exports are generated by
`scripts/export_pattern_discovery_review.py`.

### Task 004.3 consolidated v1.3 analytical features

The new dictionary/classification v1.3 uses unchanged H2-normalized sources and
Task 003 links. Historical v1.2 data/dictionaries and Task 004.2 reports remain
frozen. Operational generic UAV evidence changes analytical group, not source
model identity; reactive shorthand retains inferred uncertainty. One-row-per-alert
features and chronological supporting IDs are under
`data/processed/classification_v1_3/`; reports are under
`reports/classification_v1_3/`. Official and Telegram source bounds are preserved.

Task 004.4 reads the frozen H2-normalized source Parquet, Task 003 links/coverage,
v1.3 feature/marker Parquet and frozen dictionary/geography files. SHA-256 values
are verified before/after and saved in the attribution experiment JSON. No raw
source, timestamp, official interval or v1.3 classification is modified.

Task 004.5 reads existing normalized data, temporal links, v1.3 outputs and
Task0044 experimental outputs; no raw parsing or classification occurs. Every
existing file under data/config/prior reports is fingerprinted before and after.
Controlled-review outputs have isolated paths; Excel retains all source texts
(with explicit format-limit CSV fallback), original timestamps and source IDs.

Task 004.6 creates isolated classification_v1_4 outputs. All previously existing
raw/derived data, configs and reports (including controlled review) are verified
unchanged by SHA-256. The v1.3 lexical profile is frozen; a composed v1.4 profile
adds only the research-lead-confirmed banderol jet-UAV alias recorded in the new
attribution policy. H2, literal timestamp strings, Task 003 links and unresolved
DST folds remain unchanged. New context-reference records cite original anchors.

Task 004.7 adds read-only residual diagnostics under
`reports/classification_v1_4/residual_review/`. Frozen baseline remains 2594
official / 1803 eligible / 1050 v1.4 classified / 655 text-unclassified / 98
no-linked-text / 790 outside / 1 DST-unresolved. All 655 receive recorded-signal
features; all 98 remain a separate coverage audit (96 no linked records, two
with only empty-text records). None receives a new classification.

The 40+10 review sample preserves 749 complete linked messages, 54 available
messages in the ten-minute pre-alert window, and 35 in a separate ten-minute
post-alert diagnostic context CSV. H2, original text/title strings, UTC instants,
official intervals, source IDs and indexes are unchanged. Post-alert lexical
readouts only reuse the frozen profile; they are marked diagnostic and unaccepted.
Source/classifier/prior-output hashes are checked before and after. Human review
fields are blank. Reproduce with `python -m kyiv_alerts.residual_review --root .`;
see ADR 023 and `residual_segment_summary.md` for exact grouping/sampling rules.

Task0048 reads the same immutable inputs and generates isolated v1.5 artifacts.
Scoped negation/exclusion traces retain source character offsets and exact matched
expressions. Cross-message and pre-alert records retain explicit anchor IDs,
original text/title strings, UTC instants and their own time relation separately.
Every accepted pre-alert anchor has in-alert supporting source IDs; original
intervals and links are never rewritten. Lost observation changes episode state,
not the source's earlier observed threat. Raw/data/config/frozen-classifier/prior
report hashes are verified before/after full inference and ablations.

The full run classifies 1141 alerts, leaving 564 text residuals; 98 no-text, 790
outside-coverage and one unresolved DST case remain separate. Compared with v1.4,
99 gain classification and eight lose unsupported pre-alert attribution, net +91.
The 43 reserved Task0047 holdout cases remain unlabeled; a separate 20-case audit
excludes all holdout/development/prior sample cases. All new evidence is experimental.

Task0049 consumes immutable normalized sources and frozen v1.3/v1.4/v1.5
outputs. All 2594 IDs, UTC instants, literal source timestamps, official intervals
and Task003 links remain unchanged. H2 and the unresolved DST interval stay frozen.
Separate v1.6 marker records preserve lexical/context anchor provenance and exact
source spans. Known footer lines are masked only in a length-preserving context
view; `context_view_excluded_spans` records the original source text and offsets.
The complete original message stays in `original_text`.

The source span is Telegram 2023-08-17T10:46:25Z through 2026-10-10T15:49:45Z;
official starts are 2022-02-28T03:51:22Z through 2026-10-04T20:32:50Z, with last
resolved end 2026-10-04T21:38:04Z (October 5 Kyiv local). October is partial.
1295 eligible alerts receive experimental categories; 410 retain text without
supported attribution, 98 have no text, 790 are outside Telegram coverage and
one is unresolved. All added category evidence is exported for inspection;
residual diagnostics contain all 564 v1.5 text residual IDs. The separate final
remaining-unknown CSV has 410 IDs, including the single withdrawn old attribution.
Prior holdout cases remain unlabeled; v1.6 exploration is not blind validation.

## Task005 temporal-analysis reuse

No new sources, timestamp correction or classifier rewrite. Reuse Task003 official
intervals/coverage and experimentalv1.4/v1.5/v1.6 for stability. Primaryv1.6 chosen
explicitly by Task005; acceptance as ground truth is still pending. Official span
ends2026-10-05 Kyiv time, earlier than Telegram export cutoff; no zeros are inferred
through October10. February2022/October2026 and source-boundary days are incomplete.
One unresolved DST end stays null, with separate candidate-duration/union bounds.
Observation-span availability is not independent completeness verification.

## Task005.1 verified external sources (access2026-10-11)

Use reports/external_validation/source_register.csv for exact pinned URLs,
publication/commit dates, evidence notes and independence. Pavlo Loiek snapshot
10b4d32f37843533f59f2197153993be338f7f51 derives from Vadimkin/eTryvoga;
current Vadimkin bf0c323c78e3e4508721458797dcd38c95df13f3 is the same volunteer
lineage plus a third-party official-channel archive, not a second official gold.
Keep Kyiv City separate from Kyivska oblast. Deduplicate1874 identical rows only
in derived official-archive reconciliation; preserve original CSV line IDs.
Volunteer estimated+30min ends and official-parser possible+1h fills limit durations.
Published Kyiv export equals every original record; source causes were already
present for194 records, while2400 are null. Official API history is separately
captured, with cause crosswalks and source-index provenance. API no-token public
history is accessible; webhooks require tokens and are not used. alerts.in.ua
requires a personal token for API calls; public docs describe open threats and
month_ago history without proving complete historical-threat retention.
Initial proxy restrictions were resolved; DSNS still returns a browser challenge
and direct relevant Air Force technical statements remain unverified. Raw external
snapshots/subsets are local only; reports include hashes and reviewed notes.

## Task006 — weekly archived official start target

Uses the frozen Task005 alert_analysis_fact.parquet, retaining all2594 known starts
and source IDs, including the DST interval whose end remains unresolved. Telegram
markers are never forecasting features. Every warning color counts once per UID.
Complete weeks only; endpoint weeks excluded conservatively. Week2023-10-09 has
no records and is unknown in the primary target, not certified zero. Every positive
week also has unverified internal completeness; actual publication/revision latency
is not certified. External export identity supports provenance, not independence or
full historic coverage. Conditional archived-zero sensitivity does not alter sources.
