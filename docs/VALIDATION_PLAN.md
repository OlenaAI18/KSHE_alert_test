# Planned validation

The table below remains the research validation plan. Task 001 checked architecture/configuration only. Task 002 executed ingestion tests and real-data audits for both supplied sources; the compact Telegram attachment resolved the earlier transfer blocker. Task 003 temporal integration and coverage validation are now executed; Task 004 automated classification checks are executed; human semantic and later research validation remain pending.

| Area | Planned checks | Acceptance / response |
| --- | --- | --- |
| Input integrity | Immutable byte copies, SHA-256, archive member safety, inventory and observed record counts | Reconcile source counts; investigate discrepancies; never overwrite originals. |
| Timestamp parsing | Preserve original strings; parse actual formats; timezone/DST ambiguous or nonexistent times; midnight and date boundaries | No arbitrary offsets or silent timezone guesses; report unresolved timestamps. |
| Alert intervals | Unique scoped IDs, start/end ordering, open intervals, duplicates, overlap, duration consistency | Quarantine/document invalid records; approve overlap/open-interval handling. |
| Message linking | Foreign keys, duplicate pairs, before/within/after interval fixtures, endpoint ties, overlapping intervals, unlinked messages | Reproducible reviewed linking policy and retained evidence. |
| Classification quality | Reviewed labeled sample including synonyms, ambiguity, negation, historical references, reposts, geography and multiple markers | Initial rules are authorized by Task 004; independent human labels and agreed quality thresholds are required before semantic validation. Report false positives/negatives and unknowns. |
| Missing data | Exact source coverage and internal gaps; distinguish unavailable, unknown, insufficient reporting and no mention | Pre-Telegram alerts retained; no missing-to-absence conversion. |
| Historical regime stability | Period/window comparisons, justified break detection, sensitivity, dependence-aware uncertainty | Report unstable/absent patterns; avoid unsupported pooled generalization. |
| Forecast backtesting | Chronological/walk-forward splits, training-only fitting, feature availability audit, baseline comparisons, held-out errors/uncertainty | Proceed only with approved aggregate targets and robust out-of-sample evidence; no random splits or operational claims. |

Future automated tests use pytest with small synthetic fixtures rather than committed raw exports. Include integration checks on supplied data locally, recording commands, versions, actual counts, and pass/fail/skip outcomes. Do not call a zero-test run a pass. Define statistical thresholds, audit sample design, metrics, and target/horizon with research review before analysis. Negative findings and a forecasting no-go are acceptable documented outcomes.


## Task 002 executed evidence

`python -m pytest -q`: 36 tests passed, no skipped tests. Fixtures are explicitly synthetic and generated in pytest temporary directories. Covered valid JSON, literal/native nulls, invalid/reversed/zero intervals, duplicates, overlaps (including nested intervals), midnight and DST elapsed durations, ambiguous/nonexistent/explicit-offset times, source geography, malformed records, HTML extraction/entities/multiline text, empty/service/continuation messages, forwarding/reply/edit metadata, duplicate conflicts, malformed HTML/missing IDs, negative export-heading IDs, ZIP path safety, zero-count months/posting gaps, explicit empty Parquet schema, repeatability, raw protection, missing input and corrupt ZIP CLI failures, natural HTML page ordering, and explicit fixed-offset summer timestamp auditing without silent correction.

Real Kyiv Digital: 2,594 retained records, all starts parsed; one DST-ambiguous end (uid 1837), 2,593 valid end times. No duplicate IDs/records/intervals or reversed/zero durations. Eight short-duration flags, two >7-day gap flags, no overlaps among resolved positive intervals. Reports include all 57 local monthly counts, null fields and source references. One unresolved end is not silently assigned a DST fold or treated as zero duration.

Both raw hash equality and logical Parquet equality are checked. Reports record input hashes and tested software versions; wall-clock performance measurements vary across runs and are outside deterministic normalized records. Diagnostic thresholds (<1 minute, >24 hours, >7-day alert gaps, >24-hour posting gaps) are audit flags only, not approved inferential rules or exclusion criteria.

Real Telegram: PROCESSED, 56 message HTML files, 55,739 ordinary messages plus 1,252 service records; no duplicates, HTML parse errors, unsafe paths or skipped records. All ordinary timestamps parse using their explicit UTC+02:00 offsets. All 1,252 service records lack exact timestamps; 1,205 export date headings lack genuine source message IDs, retained via HTML/file/index provenance. There are 2,339 ordinary messages without text and five >24-hour posting gaps. The 39 monthly counts sum to 55,739 timestamped messages. The overall timestamp rate includes intentionally untimed service records; the ordinary-message rate is 100%.

The real CLI now exits 0 and reports COMPLETE for ingestion/auditing. Both Parquet tables were read back and compared across two repeated full runs, with logical equality, deterministic natural page ordering and unchanged raw hashes verified. Cross-source date-range intersection is 2023-08-17T11:46:25Z–2026-10-04T21:38:04Z. Telegram parsing is the principal measured runtime cost (~3.50 seconds of ~4.68 seconds total in the latest run); these are observations, not fixed performance promises.

Quality review remains necessary: one alert end is DST-ambiguous and explicit Telegram UTC+02:00 differs from Europe/Kyiv's seasonal offset for 35,454 messages. No shift was added or source wall time silently reinterpreted; review cross-source timezone semantics before temporal matching. Dataset intake completion does not establish event-level alignment. Linking/classification/statistical tests remain unrun, and Task 003 has not started.


## Task 002.1 executed verification

The Task 002 results above describe the initial H1 baseline. Task 002.1 evaluated 28 fixed reviewed real examples under both hypotheses; H2 matches 28/28 within five minutes, H1 14/28 (no daylight-time matches). Accepted source-specific H2 normalization is recorded in ADR 013. Generic offset parsing remains unchanged, and original Telegram titles are preserved.

Current automated suite: **51 passed**, no skipped tests. New checks cover H2 standard/daylight time, before/after spring and autumn boundaries, nonexistent/ambiguous clocks, both hypotheses against the same fixed boundary, signed differences, unresolved-comparison rejection, and the two admissible ends for official alert 1837. Real Telegram regeneration retains all 56,991 records, including eight ordinary repeated-hour clocks with null UTC values; 55,731 ordinary timestamps resolve. No fold is guessed for these messages or the ambiguous official interval. The audit report and Parquet were regenerated using this rule; fixed-example verification is separately reproducible from hash-checked raw inputs. No Task 003 mapping dataset or linking policy is implemented.


## Task 003 executed validation

Current suite: **74 passed**, no skips. New synthetic checks cover strict-inside/start/end/outside membership, multiple messages, no-message versus no-history distinctions, adjacent intervals, cross-midnight intervals, ambiguous messages, unresolved official endpoints, empty text, untimed and timestamped service events, exact/conflicting duplicates, source provenance, deterministic ordering, genuine overlaps, partial historical boundaries, monthly denominators/zeros, stale-H1 rejection, CLI input immutability and blocked-input behavior. A deterministic small brute-force oracle independently checks the indexed sweep on overlapping synthetic intervals.

Both real normalized datasets were processed: 2,594 alerts, 56,991 message records (55,739 ordinary; 55,731 with resolved timestamps). Every generated link was checked against source IDs/times/file/index, half-open membership and pair uniqueness. Both Parquet outputs were read back and compared across repeated runs. Normalized input SHA-256 hashes remain unchanged; raw sources were not accessed or modified by integration. All monthly alert totals and covered counts reconcile; resolved-message partitions reconcile as 32,772 linked + 22,944 outside + 15 withheld = 55,731. Adding 1,252 untimed service and eight ambiguous message records recovers all 56,991 records.

All 2,594 alerts remain in coverage: 1,707 covered, 96 no_messages_found, 790 no-history, one unresolved. Complete count/availability fields for the unresolved interval remain null, with deterministic lower bounds zero; no end was fabricated. Known possible-range evidence identifies alert 1837 and source IDs 35419–35441 as the 23 withheld/ambiguous ordinary messages. The monthly report has 57 calendar-month rows, of which 39 have eligible alerts; earlier unavailable months have null rates. No classification, NLP, forecasting or statistical hypothesis tests were run; Task 004 has not started.

## Task 004 executed technical validation — human review pending

`python -m pytest -q`: **155 passed**, no skips. Synthetic tests cover all seven lexical categories and the unknown state; Ukrainian/transliterated spelling and subtypes; Unicode dash/case normalization and exact reversible spans; boundary collisions (Shakhedoban, zirconium, incorrect aircraft/missile models); multiple messages/categories and fixed combination ordering; negation/cancellation, historical summaries, speculative wording and textual alert cause versus carrier explanations; aircraft activity without launches; generic UAV specificity and no accidental generic-family double counting; city/oblast/nationwide/other/mixed geography and sentence versus message fallback; missing/empty text, historical unavailability and unresolved intervals; complete alert retention; marker source/version integrity; duplicate/conflicting inputs, empty output schemas, input/output path collision and blocked-input reporting; repeatable CLI tables/CSV and immutable source inputs.

The real CLI processes all **32,772** links / unique messages, including **32,406** with text. It retains all **2,594** alerts and produces **5,981** candidate markers, of which **343** pass conservative context/geography/specificity rules and **5,638** remain excluded/review-only. **285** alerts have accepted categories: **267** single-label and **18** multi-label. **1,420** text-observed alerts have no identifiable accepted marker, **98** have no linked text (96 without messages and two with only empty text), **790** have no historical coverage and **one** remains DST-unresolved. All category booleans for alert 1837 and its end remain null.

Per-category alert counts overlap: shahed_uav 16, jet_uav 2, ballistic_high_speed 23, cruise_missile 9, mig31 163, strategic_aviation 2, other 94. Jet/strategic evidence is particularly sparse (two accepted alerts each); every category still needs human validation. The complete 57-month classification/density table is in the generated report. Classified coverage is 285/1,803 eligible alerts (15.81%); it is **not recall**. October 2026 has zero accepted categories under these rules despite linked text; low detection and colloquial/place-name exclusions require review before analytical use. Telegram density changes substantially: mean linked messages per eligible alert is 12.93 in 2024 versus 23.20 in 2025, so marker opportunities are not constant.

Repeated real runs have logically identical marker/feature Parquet tables and byte-identical review CSV. All four existing Parquet input hashes and the dictionary hash remain unchanged during processing. Original raw hashes match Task 002 values. Foreign keys, half-open boundaries, source positions, reversible text spans, counts, combinations, full-alert cardinality, null DST state and readback reconcile. Measured runtime is approximately five seconds on this environment, not a performance guarantee.

The review CSV contains **180** unique alert/message examples, seed **20261010**, covering 2023–2026, every category/context/geography, single/multi-label/no-marker states and low/middle/high volume. No requested lexical/context/geographic stratum is absent. Reviewer fields are blank; precision and recall are null and reviewed reference count is zero. This round-robin sample deliberately overrepresents rare and difficult cases and is suitable for error discovery, not unweighted population precision estimation. Require independent annotation, false-positive and false-negative review, adjudication of mixed contexts/geography, versioned rule refinement and an independently held-out reference set with agreed metrics before semantic acceptance. **PROVISIONAL — HUMAN VALIDATION REQUIRED**.

## Task 004.1 executed geography verification

`python -m pytest -q`: **224 passed**, no skips. The finite 82-entry dictionary is implemented separately from threat taxonomy v1.0. The current classification transformation is v1.1-geo. Automated checks cover selected Ukrainian/Russian spelling, inflections, colloquial aliases, all ten city district patterns, abbreviations, exact source-name spans, nested-name arbitration, suburb exclusion, mixed geography, common/shared names with/without Kyiv anchors, clause/message fallback, regex boundaries, untouched context rules, provenance, structured Parquet readback, legacy v1.0 reproduction, input hashes, repeated runs, and comparison gains/losses.

All **5,638** previously excluded markers were reevaluated, including **3,327** unspecified-geography candidates from **2,897** messages. For those 3,327: **345** now identify city geography, **647** oblast geography, **138** ambiguous geography, and **2,197** remain unspecified. Thus **1,130** changed geography interpretation. Of the 345 newly city-recognized candidates, **338** retain uncertain context; only **seven** pass existing context/specificity rules (five current-threat and two explicit-cause records).

Across all candidates, **eight** newly pass aggregation and **33** previously accepted records become excluded, yielding **318** accepted of **5,981** unchanged lexical candidate records. Classified alerts change **285 → 274**, with **six gained** and **17 lost**. Eligible denominator remains **1,803**; yield changes **15.80699% → 15.19689%** (−0.61009 percentage points). Text-conditioned yield changes **16.71554% → 16.07038%** among **1,705** alerts with text. Monthly comparisons retain all 57 months and unavailable/null rates. All **2,594** official alerts remain, including the one unresolved DST interval with null end/category observations. Uncovered counts are unchanged.

These losses reveal a limitation of the preserved conservative mixed-geography rule. For example, messages explicitly describing movement from Vyshhorod toward Kyiv, or a Kyiv alert cause near an oblast settlement, can now become uncertain once both places are recognized. This is **not** evidence that those threats were irrelevant or that the new classifier is more accurate. Adjudicate such cases, along with terse city-locality warnings that retain uncertain context, before proposing a separately versioned relevance/context refinement. No silent destination inference or rule changes were introduced to force a higher yield.

The original v1.0 outputs remain unchanged, and rerunning the legacy engine reproduces every original column of all **5,981** baseline candidates and **2,594** feature records. Expanded runs retain threat taxonomy/subtypes, context statuses, lexical spans, source identities, H2 timestamps, intervals and coverage fields. New exact locality spans are checked against source text and dictionary metadata. The comparison verifies these invariants and exposes all informative changes in geography_changes.csv. A second 180-example geographic review CSV has unique alert/message pairs and blank human fields; precision/recall remain unavailable. **PROVISIONAL — HUMAN VALIDATION REQUIRED**.


## Executed user-approved contextual rules (2026-10-11)

The complete suite passed: **271 passed in 6.06 seconds**. The real-data
classification used the v1.1 threat dictionary and v1.1 geography dictionary,
producing classification version v1.2-reviewed-rules in 13.542947 seconds.
All 2,594 official alerts remain represented. Of 1,803 temporally eligible
alerts, classified alerts increased from 274 (15.20%) to 437 (24.24%):
163 gained, none lost. Among 1,705 alerts with linked text the share rose
from 16.07% to 25.63%. There are 712 accepted marker records, including
16 whose uncertainty is preserved. All 5,981 previous lexical candidates
remain traceable; 527 new candidates were identified and 22 accepted.

Regression coverage includes the approved locality bulletins, Bucha exclusion,
suburban direction toward Kyiv, explicit Kyiv alert cause, Kinzhal launch,
probability qualifiers, Shakh/reactive shorthand, cancellation/history,
question and museum contexts, generic UAV distinction, explicit jet models,
version pairing, provenance preservation and a synthetic CLI comparison.
The 180-row review export has empty independent reviewer labels.
Coverage measures classification yield, not precision or recall.
See reports/classification_v1_2/reviewed_rules_report.md for reproducible changes.

Both preserved profiles were recomputed against their stored candidate records:
all 5,981 candidates in original v1.0 and all 5,981 in geographic v1.1 matched
on every retained interpretation field, keyed by rule and original match span.
The downloadable Excel archive and XML were verified, including all 180 rows.

## Task 004.2 executed discovery verification (2026-10-11)

Full suite: **306 passed in 6.74 seconds**, no skips. The 35 focused diagnostic
tests additionally passed after final report rendering changes (1.31 seconds).
Coverage includes analysis-only Unicode/noise handling and short forms, exclusive
A/B/C/D populations, Kyiv calendar boundaries, distinct alert/message support
under a repeated burst and overlapping-ID links, character n-gram ranges,
deterministic sparse grouping, full-context representatives, diagnostic-only
catalog behavior, absence of cross-message inference, blank human fields,
missing-input BLOCKED behavior, protected-directory refusal, current-version and
source-span validation, count/category mismatch rejection, and repeated synthetic
CLI outputs with immutable source inputs.

Current reviewed baseline reconciles: 2,594 official alerts; 1,803 eligible;
1,705 with linked text; 437 classified; 1,268 text-unclassified. Exclusive
populations: A 258, B 179, C 1,268, D 889. Per-category counts remain
49/4/52/18/163/3/225, including overlaps. October: 42 eligible alerts, 33 with
text, zero specific, one other-only, 32 text-unclassified, nine no-text;
486 text messages, 457 without lexical candidates, 35 candidate records.
The official alert-start window ends Oct 4 23:32:50 Europe/Kyiv; final interval
ends Oct 5 00:38:04. Telegram continues through Oct 10 18:49:45. Partial October
must not be compared by full-month raw totals.

Final real discovery runtime: **16.139518 seconds**; repeat **15.680040 seconds**.
Both runs produced byte-identical CSVs and identical JSON excluding elapsed time.
All protected Parquet/config/prior-report hashes remained identical. Every
representative and assignment pair was checked against Task 003 links and source
text; review fields are blank. Population totals and family period-support sums
reconcile. The six-sheet Excel/ZIP passed archive/XML/row-count validation.

There are 19 supported diagnostic families and 64 exploratory TF-IDF groups
from 20,741 unique normalized documents, using 60,000 sparse features. No dense
N×N similarity matrix or remote service is used. Candidate support is distinct
B/C alerts; families/exclusion counts overlap. Accepted B subtypes are generic
UAV (174 alerts) and unspecified missile (eight), overlapping in three alerts.
The four lexical-review families overlap 59 C alerts, only five with literal
city geography in the same message. This is an exploratory review ceiling;
validated additional classifications remain zero, precision/recall unavailable.
No classification, dictionary, source timestamp or temporal link was changed.

## Task 004.3 executed consolidation and coverage verification (2026-10-11)

Full suite: **362 passed in 9.45 seconds**, no skips. The 56 focused consolidation
checks additionally passed after the final policy-version metadata correction
(2.58 seconds). They cover approved generic/explicit UAV distinctions, reactive
noun/adjective versus explicit model inference, ambiguous non-threat exclusions,
no generic self-suppression, preserved overlap evidence, 85 repeated UAV messages
plus three ballistic messages aggregating to two categories, same-message global
support deduplication, chronological first/all evidence IDs, specific + other
state semantics, explicit cause preservation, all seven states, unavailable/null
observations, synthetic 2,594-ID retention, unchanged non-UAV profiles, version
gains/losses, deterministic blank-label sampling, corrupted-support rejection,
versioned schema readback, repeated CLI Parquet/CSV equality and blocked missing
previous-baseline inputs. Passing tests are not semantic validation.

Final real CLI runtime: **12.488978 seconds**; repeat **12.752707 seconds**.
Parquet tables were logically identical across runs, all CSVs byte-identical and
JSON identical excluding elapsed time. Protected original source/config/prior-
report hashes match the before-task snapshot. Recomputing the frozen reviewed
v1.2 profile with the current code exactly reproduces every field of its 6,508
marker records and 2,594 feature records. Every current alert ID matches the
original source set. The DST-unresolved record 1837 retains null end, duration,
category/support observations and unresolved state. No H2/link correction occurred.

v1.3 retains **2,594** official alerts, **1,803** eligible, **1,705** with text,
and **437** with accepted markers: **zero gained, zero lost** relative to v1.2.
Analytical categories excluding other change **258 → 432**; only_other changes
**179 → 5**, reflecting approved generic-UAV regrouping rather than a detection
coverage improvement or verified model identification. States reconcile:
393 single_type + 39 multiple_types + 5 only_other + 1,268 no_marker_with_text +
98 no_linked_text + 790 outside_telegram_coverage + one unresolved = 2,594.
There are 45 multi-label alerts if other is included, versus 39 with multiple
non-other analytical categories. Per-category flags: shahed_uav 233, jet_uav 12,
ballistic_high_speed 52, cruise_missile 18, mig31 163, strategic_aviation 3, other 18.
All non-UAV specific flags are unchanged relative to the previous reviewed run.

The new marker table has **6,548** candidates / **714** accepted occurrences.
Generic, explicit-family/attack-UAV and inferred-reactive evidence remain distinct;
all nine accepted inferred-shorthand markers retain uncertainty. Message support
is separate from marker occurrences and alert category presence. Month/year totals
and all-official/eligible/text denominators reconcile; unavailable rates are null.
Classification yields (any category): **16.85% / 24.24% / 25.63%** respectively.

The 28-alert unclassified review sample spans 2023–2026, density levels, recent
August–October and lexical-hit/no-candidate strata. Every representative original
text/ID was checked against Task 003 provenance; human fields remain blank.
All requested available strata are represented. Six-sheet Excel/ZIP archive,
XML and row counts were checked, including all 2,594 alert rows. Artifacts are
PROVISIONAL — HUMAN VALIDATION REQUIRED. Technical alert-table readiness does
not authorize or establish readiness for semantic threat-category time-series
conclusions; independent review and coverage-aware methodology remain required.
No Time Series Analysis or commit was performed.

## Task 004.4 executed experiment verification (2026-10-11)

Full suite: **383 passed in 10.31 seconds**, no skips. Nineteen bounded-context /
lookback unit cases plus two full real-output checks cover explicit-anchor-only
inference, original source IDs/text, context limits, resets, competing types,
negation/history/questions, deterministic lower-inclusive/start-exclusive windows,
previous membership, intervening boundaries, bounded unresolved envelopes,
multiple/repeated categories, unchanged inputs, every copied v1.3 field, unique
alert IDs, unavailable/null observations and waterfall reconciliation.

Real experiment: 2,594 official, 1,803 eligible, 1,705 with text, 437 frozen
accepted (432 specific / five other-only; 39 multiple-specific). All 1,268
text-unclassified intervals evaluated. New provisional inside candidates: **141**;
remaining text-unclassified **1,127**. Stage C evaluates these plus 98 no-text
alerts, **1,225** in total. Clean pre-alert candidate alerts under 5/10/15/30/60
minutes: **11/15/17/17/19**; ambiguous marker associations **115/169/207/306/464**;
contaminated marker associations **1/3/12/43/181**. These occurrence counts are not
precision/recall and are separate from unique message-alert review workloads.

Reproducibility reruns compare Parquet logically, all CSV bytes exactly, and JSON
excluding elapsed time. Protected SHA-256 hashes match. Thirty review examples
span all five first-qualifying window bins (six each); human fields remain blank.
Workbook XML and ZIP integrity checks pass. Actual runtime approximately seven
seconds per run; final exact timings are in the generated report JSON. Source
review identified a Kyiv-bypass description, now retained as ambiguous rather
than clean support. No independently labeled semantic validation is claimed.
No production attribution, DST fold, dictionary, Time Series Analysis or commit
was introduced. All results: PROVISIONAL — HUMAN VALIDATION REQUIRED.

## Task 004.5 executed controlled review verification (2026-10-11)

Full suite: **404 passed in 13.77 seconds**, no skips. The 21 focused checks cover
25 unique official IDs, 20 unclassified / five existing positive controls,
requested date/volume strata, all requested diagnostic signal types, deterministic
selection and reordered inputs, unavailable strata without substitutions,
complete linked timelines including no-hit/empty messages, all candidate and
accepted occurrences, original text/time/provenance, chronological order and
relative minutes, valid foreign keys, blank human fields, provisional evidence,
explicitly missing instrumentation, detection of omitted messages/accepted markers
and invented human decisions, Excel readback/styles/filters/freeze/dropdowns /
internal navigation, original cell text/date formats, literal formula-like source
strings, Excel cell-limit fallback, XML-control representation, source/report
reconciliation and protected input hashes.

Controlled sample: all requested strata available; **25** alerts, **475** messages
(**468** nonempty), **416** messages without dictionary hits. **82** candidate
occurrences: **eight accepted**, **74 rejected**. Most common recorded exclusions
(overlapping) are context_uncertain 64, geography_unspecified 28,
geography_other_region 12, geography_kyiv_region 10 and geography_uncertain 10.
Four selected unclassified alerts have Task0044 inside provisional support; this
is not semantic acceptance. All human review fields remain blank.

Final reproducibility checks: first/repeat generation **2.365745 / 2.623840 s**;
all CSV bytes identical, summary JSON/Markdown identical excluding elapsed time,
all Excel cell values identical, all protected raw/derived data/config/prior-report
SHA-256 hashes unchanged. Native openpyxl workbook opens; companion ZIP integrity
passes. No source text exceeded Excel format limits or required XML escapes in
the actual sample (**zero cell adjustments**); full companion CSV retained anyway.
No classifications, dictionaries, H2 timestamps, DST states or prior reports
changed. No population precision/recall, classifier corrections, forecasting,
time-series analysis or commit. Status: DIAGNOSTIC SAMPLE — HUMAN REVIEW REQUIRED.

## Task 004.6 executed v1.4 verification (2026-10-11)

Full suite: **452 passed in 13.95 seconds**, no skips. The 48 new focused cases
cover operational anchors with legacy uncertain/nearby geography, exact source
provenance, historical/negated/explanatory/joking/donation/question/other-region
negatives, unrelated shorthand, literal geography preservation, explicit jet vs
generic-family suppression, user-confirmed banderol alias, multiple/repeated
categories, no geography-only type inference, bounded episodes, competing and
concurrent types, cancellation/negation resets, exact gap/maximum-age boundaries,
strict/inclusive ten-minute lookback boundaries, previous membership/intervening
boundaries, weak pre-alert locality corroboration, ambiguous unknown movement,
source/anchor time-relation separation, source-relative locality spans, pre-alert
context versus explicit cause, deterministic outputs, four ablation controls,
real full-dataset/accepted-baseline preservation, DST/no-history unknownness and
reviewed source discrepancies without hardcoded attribution IDs.

Final full-data classification plus four ablations: **24.701713 seconds**; repeat
**24.840804 seconds**. Parquet tables logically identical, all CSV bytes identical,
JSON/Markdown identical excluding elapsed time. All earlier raw/derived data,
configs and reports (including Task0045) retain their hashes. Sixty audit sample
records include anchor/reference/user-alias cases; all support texts checked
against original message IDs and all human fields blank. Nine-sheet openpyxl
Excel readback/rows/dropdowns/blank fields/no formulas/external connections and
bundle ZIP integrity passed.

v1.3 **437 → v1.4 1,050**, **613 gained / zero lost** unique official alerts.
All **714** previously accepted occurrences/categories retained. All **2,594**
official records preserved; **1,803** eligible / **1,705** with linked text.
Eligible yield **24.24% → 58.24%**; text-covered **25.63% → 61.58%**. These are
experimental coverage yields, not verified accuracy or recall.

States reconcile: 836 single-specific + 204 multiple-specific + 10 only-other +
655 text-without-markers + 98 no-linked-text + 790 outside-history + one unresolved.
Single category including other: 392 → 826; multi-category including other:
45 → 224; unknown including unavailable: 2,157 → 1,544; other-only five → ten.
Category unique-alert counts: broad UAV 596, jet UAV 130, ballistic/high-speed
273, cruise missile 89, MiG-31 173, strategic aviation 60, other 67.

Overlapping new-alert correction support: geography 593, context 377,
cross-message 307, pre-alert 77. Independent rule-disabled ablations lose
**570 / 288 / 38 / 47** alerts respectively; these are also non-additive.
Aug/Sep/partial-Oct 2026: **86/121, 129/190, 23/42** experimental classifications.
Marker records: 12,936 candidates / 5,637 accepted, including 112 actual pre-alert
records and 2,835 context references. Each reference retains its own source time
relation and an independently recorded anchor time relation.

Reviewed 2563/2565/2578 reproduce shahed_uav. 2590 matches that experimental group
but remains an unconfirmed working hypothesis. 2581 has explicit jet_uav source
support (including the user-confirmed banderol alias), not a separate shahed_uav
anchor; the research lead explicitly chose to retain the discrepancy for review.
No source evidence/second type was fabricated. Baseline H2/DST untouched; no
Time Series Analysis or forecasting. EXPERIMENTAL — HUMAN VALIDATION REQUIRED.
## Task 004.7 executed validation — 2026-10-11

`python -m pytest -q`: **469 passed in 15.39 seconds**, no skipped tests; includes
17 residual diagnostic/selection/preservation tests. Checks cover fail-closed
baseline counts, probe spans without category promotion, non-operational guards,
overlapping/primary membership, half-open boundary windows, deterministic
year-balanced selection/exclusions/fallback, all 655 residuals, separate 98
no-text cases, exact 40+10 quota/status/uniqueness, complete source chronology and
candidate records, blank human fields, Excel filters/navigation/dropdowns and
unchanged source/classifier/prior-report hashes.

Repeated full review generation produced byte-identical CSV and Markdown, and
identical summary JSON excluding runtime. The seven-sheet workbook was reopened;
all full source texts were represented without Excel cell-limit adjustments.
The 749 in-alert, 54 pre-alert and 35 post-alert records retain original texts,
IDs, titles and normalized instants. Accuracy/failure labels remain unvalidated.
Technical verification does not complete the requested human dialogue review.

## Task0048 executed validation — 2026-10-11

Full suite: **514 passed in 19.84 seconds**, no skipped or failed tests. Includes
45 new v1.5 tests covering scoped questions/history/quotes/negations, no-strikes
versus no-UAV, absence of communications versus absence of a threat, unrelated
regions, movement reversal/lost observation, ambiguous simultaneous families,
bounded pre-alert correspondence, contamination, exact source spans, fail-closed
baseline diagnostics, full feature/marker/calendar reconciliation and blank audit
fields. The earlier residual preservation test now checks every historical
fingerprint while allowing separately authorized later output paths; no historical
hash assertion is removed.

Two complete full-data runs, each with five correction ablations, took 69.027479
and 69.300266 seconds. Repeated Parquet is logically equal; CSV/Markdown are
byte-identical; serialized JSON is identical excluding runtime. Original
raw/interim/processed baselines, H2, official intervals, dictionaries, legacy
source modules and all previous reports (including Task0047 residual review)
are fingerprinted and unchanged. There are 2594 official rows / 1803 eligible /
1141 classified / 564 text residual / 98 no-text / 790 outside / 1 unresolved.

The 20-case audit excludes development/prior sample and 43 holdout IDs, preserves
208 complete in-alert and 12 pre-alert messages, blank human fields and original
texts/titles; the workbook reopens and needs no Excel representation adjustments.
No standalone pre-warning is accepted without inside correspondence. All 99
new classifications remain uncertain; eight unsupported earlier transfers lose
classification. Calendar/category/source totals reconcile to the Parquet.

Software checks passing does not mean all human targets reproduce. Five of the
six newly confirmed targets match exactly; 1096 lacks source-backed in-alert
ballistic corroboration under the required temporal policy. Preserve its confirmed
two-category target and report the discrepancy. The user's previously retained
2581 source discrepancy also remains. 1416/2590 are provisional. No population
accuracy, automatic commit or forecasting claim is made.


## Task0049 executed validation — 2026-10-11

Final full suite: **582 passed in 24.13 seconds**, zero failed/errors/skipped.
Includes 68 new v1.6 checks for every new lexical family, approved finite MiG
shorthand/model uncertainty, exact footer spans, current position/type bulletins,
ballistic/cruise inflections, historical/negated/hypothetical/satirical content,
no-launch/no-strike scope, foreign Kursk-origin contamination, bounded routes,
pre-alert correspondence and previous-alert boundaries. Four full-data checks
verify source/category/calendar reconciliation, all 564 diagnostic IDs, inspectable
new category evidence, original fingerprints and compact exception sources.
Previously reviewed positive targets remain explainable; 1096 and 2581 are still
explicit confirmed-label/source discrepancies, not forced by alert ID.

The frozen v1.5 preservation test checks every historical fingerprint while
allowing separately authorized later v1.6 paths, matching the earlier residual
preservation approach. No historical checksum assertion is removed. All 184
original source/prior-classifier/config/report files remain unchanged, including
all previous Parquet/report artifacts, source timestamps and Task003 links.

Two final deterministic full-data runs took **23.480795 and 22.495853 seconds**.
Parquet is logically identical; every CSV and Markdown report is byte-identical;
comparison JSON is equal excluding runtime. Correction accounting uses sorted
alert IDs to keep Markdown dictionary ordering stable across processes. Actual
results are in `reproducibility_results.json` and `validation_results.json`.

The compact source-focused analyst audit passes 20/20 specified message/category
checks. New false acceptances discovered in development (explicitly non-threatening
aircraft, explanatory/summary/satirical posts, distant absence and Kursk/course
confusion) are rejected with regression coverage. This is not independent human
population accuracy. All 258 added alert/category pairs have inspectable supporting
sources and persistent uncertainty; 14 previous category pairs are withdrawn.
There are 1295 classified / 410 text residual / 98 no-text / 790 outside / one
unresolved, with 155 unique gains and one loss versus v1.5. No warning alone in
the pre-alert window is accepted without inside correspondence.

Reproduce full classifier then run `python scripts/validate_v16.py --root .` to
execute actual regressions and write machine-readable outcomes. The validator
marks a zero-test/failed run BLOCKED. A fresh classifier run resets test status
to pending until the validator runs. Stop marker development after Task0049;
analytical handoff remains EXPERIMENTAL — HUMAN VALIDATION REQUIRED.

## Task005 executed validation — 2026-10-11

Complete suite: **591 passed**, zero failures/errors/skips, 25.34 seconds.
Nine temporal tests cover overlapping/adjacent unions, half-open midnights,
23/25-hour DST days, missing end rejection, joint deterministic block sampling,
Holm correction, real population reconciliation, preserved timestamps/hashes,
partial months, nullable historical categories,101 counted transitions and
explicit statistical families/long-lag CI exclusions. Protected original/prior
files: 207; unchanged by the analytical runs.
The historical v1.6 preservation test now checks every saved historical checksum
while allowing new authorized Task005 paths, as prior-version tests already did.
No historical checksum assertion or classification rule was removed/changed.
Repeated final execution checks all33 generated artifacts for byte identity,
including Parquet, tables, figures and statistical CSV; machine-readable outcomes
are in reports/temporal_analysis/validation_results.json and
reproducibility_results.json. No independent source completeness or classifier
accuracy validation is claimed. Task005 finishes with FURTHER_VALIDATION_NEEDED.

## Task005.1 executed checks — 2026-10-11

Full suite: **599 passed** in 27.60s; zero failures/errors/skips. Eight new
checks exercise explicit-offset parsing, deduplication/CSV-row retention,
maximum-cardinality matching instead of greedy pairing, half-open boundaries,
unresolved-end exclusion,1015/280/508 group reconciliation, historical cardinality/
foreign keys and protected checksums, traceable register, constrained positive
corroboration,2594 unchanged originals/exact clock matches and partial crosswalks.
245 earlier source/config/classifier/Task005 output fingerprints are preserved.
Repeated analytical/report execution checks byte-identical outputs; captured
external source snapshots are frozen locally, not refetched during tests.
No scores are presented as independent weapon ground-truth accuracy. Native
API token requirements and DSNS browser challenge are respected.
