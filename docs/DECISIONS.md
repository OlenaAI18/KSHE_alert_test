# Architecture and research decision log

Accepted decisions reflect the supplied task, not findings from data inspection. Changes require explicit proposals with consequences; retain superseded entries for traceability. Research/methodology decisions are coordinated outside the implementation workflow.

| ADR | Status | Decision | Rationale / consequence |
| --- | --- | --- | --- |
| 001 | Accepted | Kyiv is the geographic focus. | Avoid unapproved geographic expansion. |
| 002 | Accepted | Kyiv Digital is the primary alert interval source. | Official intervals define alert boundaries/duration. |
| 003 | Accepted | Telegram supplies supplementary threat mentions. | Context is not authoritative weapon confirmation. |
| 004 | Accepted | Timestamps are user-confirmed as aligned. | Preserve originals; no arbitrary offset. Actual formats/DST still need validation. |
| 005 | Accepted | Classification is dictionary-based and multi-label. | Rules and supporting message evidence must remain reviewable/versioned. |
| 006 | Accepted | Alerts may contain multiple markers. | Preserve combinations instead of forcing a single category. |
| 007 | Accepted | Forecasting is conditional on statistical evidence. | No aggregate MVP without robust chronological out-of-sample validation. |
| 008 | Accepted | Codex handles repository code implementation. | Work proceeds through scoped tasks and reported checks. |
| 009 | Accepted | Research/methodology decisions are coordinated outside code implementation. | Do not independently redefine objective, targets, interpretation, taxonomy, or methodology. |
| 010 | Accepted | Use a lightweight local Python src-layout architecture. | No services or infrastructure needed for initialization. |
| 011 | Proposed | Normalize internal timestamps to UTC and derive local calendar features in Europe/Kyiv. | Confirm source representations and DST handling before implementing. |
| 012 | Proposed | Initial category IDs listed in the YAML placeholder. | Taxonomy, synonyms, patterns, and interpretation need review before classification. |

Open decisions: interval endpoint/overlap policy; source/message ID scope; coverage states; statistical aggregate target/horizon; regime definitions; classification audit criteria; baseline metrics and forecast evidence thresholds; inferential/multiplicity strategy. No forecast target or detection rules are approved in Task 001.


## ADR 013 — Telegram clock interpretation (Task 002.1)

**Status: Accepted**, under the user's explicit conditional instruction to implement the interpretation clearly supported by real examples.

**Context:** All 55,739 ordinary HTML titles declare UTC+02:00, including summer. Two competing interpretations were evaluated on 28 manually reviewed Kyiv-specific boundary announcements across 2023–2026, using the same fixed official boundary for both hypotheses. Fourteen standard-time examples agree under both hypotheses. In fourteen daylight-time examples, H1 (suffix as absolute offset) matches 0/14 within five minutes, while H2 (displayed clock as Kyiv-local) matches 14/14. Daylight median absolute error is 61.758 minutes for H1 and 2.075 minutes for H2; overall H2 median absolute error is 1.442 minutes. This is purposive source verification, not a population accuracy estimate.

**Decision:** For this inspected Telegram Desktop format `DD.MM.YYYY HH:MM:SS UTC+02:00`, treat the displayed clock as Europe/Kyiv wall time and use tzdata's seasonal rules to normalize to UTC. Preserve the exact title and its suffix. Generic ISO offsets and other title formats retain their existing semantics; future exports require independent verification. No arbitrary global shift is applied: standard-time readings do not change, and daylight-time readings differ by one hour from H1.

**Consequences:** Rebuilt Telegram Parquet has 55,731 resolved ordinary timestamps and eight DST-ambiguous values (IDs 35434–35441) retained as null with original titles. Service records remain retained and untimed. Kyiv Digital alert 1837 still has two admissible end instants (00:05:12Z or 01:05:12Z), durations 38.2 or 98.2 minutes; available messages/neighboring intervals do not justify selecting a fold. Preserve these unresolved cases for explicit handling in later tasks.

**Evidence:** `config/time_alignment_sample.json` versions reviewed IDs, fixed alert references, source hashes and excluded cases. `python scripts/verify_time_alignment.py` regenerates ignored `reports/data_quality/time_alignment.md` and `.json` directly from hash-checked raw inputs. The report includes all signed differences, sensitivity thresholds, excerpts and the separate DST inspection. Regression checks cover standard/daylight time and both DST boundaries. This decision refines the timestamp implementation of ADR 004 without altering the research objective or introducing Task 003 linking rules.


## ADR 014 — Half-open temporal linkage and coverage states (Task 003)

**Status: Accepted**, following the user's explicit Task 003 rules. Preserve ADR 013 H2 normalization.

**Decision:** Link source messages by `start <= time < end` using sorted interval/message sweeps, never nested full-dataset scans. Keep each unique source-ID pair once. Retain all matches in genuine overlapping resolved intervals with review quality; do not choose an arbitrary interval. Missing timestamps/IDs are reported, not invented; valid empty-text records can match. No threat/relevance classification is performed.

**Uncertainty:** No links are published for an unresolved official interval. Enumerated DST end candidates bound a possible envelope only; the original end stays null. Conservatively exclude all resolved message timestamps in that envelope, even a definitely contained prefix. Ambiguous message candidate folds flag potentially affected alerts but do not create links or select folds. Unknown source endpoints may leave an unbounded envelope rather than a guessed end. Exact repeated message rows are deduplicated with evidence; conflicting source IDs fail the run.

**Coverage:** Retain one row per official alert. Use covered, no_messages_found, no_telegram_historical_coverage, unresolved_temporal_ambiguity, plus explicit partial_historical_coverage for boundary truncation without links. Availability/count values are null for unknown or unavailable observations; separate deterministic lower bounds reconcile to links. The observed first/last Telegram times define a date span, not continuous reporting. Monthly rates use fully range-contained resolved eligible alerts only; unavailable rates are null rather than zero.

**Observed consequences:** 32,772 unique temporal links, 1,707 covered alerts, 96 resolved within-span alerts with no messages, 790 historically unavailable alerts, one unresolved alert (1837). There are 1,804 fully span-contained alerts, of which 1,803 are rate-eligible; observed coverage is 94.6755%. Fifteen resolved messages in the possible interval and eight DST-ambiguous messages are withheld; 1,252 untimed service records are excluded. No actual overlapping-interval review links or partial-range rows occurred. Input hashes and source records are preserved. Evidence is in ignored temporal-linking reports, not committed production data.

## ADR 015 — Dictionary-based threat context v1.0 (Task 004)

**Status: Accepted implementation scope; semantic outputs provisional**, following explicit Task 004 authorization. ADR 012's placeholder taxonomy is superseded; the research objective, H2 time interpretation and half-open linking remain unchanged.

**Taxonomy:** shahed_uav, jet_uav, ballistic_high_speed, cruise_missile, mig31, strategic_aviation, other, unknown. The last is an analytical missing/undetected state, not a lexical weapon category. Preserve explicit subtypes, including Zircon's analytical grouping, Kh-59/69, generic UAV/missile and unspecified-model MiG candidate evidence.

**Implementation choices for review:** small versioned YAML regular expressions with Unicode boundaries and reversible normalization; clause-level negation/history/uncertainty/cause/current context; transparent text geography; conservative inclusion only for current or cause evidence with explicit city/nationwide geography. Unspecified/oblast/other/mixed geography remains review-only. No cause inferred from volume or timing. Generic family and overlapping spans stay traceable but do not double-count a named type. These deterministic heuristics are initial auditable rules, not semantically validated findings or an exhaustive language model.

**Missingness:** retain all official alerts; available text without markers differs from no linked text, no historical coverage, partial history and unresolved timing. Null means unavailable observation; false means not detected in available text. Context counts are not deployment counts.

**Validation:** reproducible 180-example round-robin stratified sample with seed 20261010, blank human labels and no invented precision/recall. Include no-marker examples. Full outputs are **PROVISIONAL — HUMAN VALIDATION REQUIRED**. Independent review and rule refinement under a new dictionary version are required before analytical use. No commit or later task is authorized by this decision.

## ADR 016 — Geographic Dictionary Expansion within Task 004.1

**Status: Accepted implementation scope; all semantic matches provisional**, under the user's explicit addition to Task 004.

**Decision:** Implement `config/kyiv_geography.yaml` as finite kyiv-geography-v1.0 with independent versioning. Keep threat taxonomy v1.0 and classify with transformation v1.1-geo when explicitly enabled. Preserve found source names and generalized geography; recognize selected declensions, alternatives, abbreviations and colloquial localities. Keep suburb/oblast cities separate from Kyiv City and generic/shared names dependent on a trusted Kyiv anchor. New matches are predictions, never automatically human-approved truths.

**Change control:** Freeze original Task 004 outputs/reports; publish new tables/reports in classification_v1_1 subdirectories. No ingestion, H2 normalization, temporal linking or threat/context rule changes. Compare all prior rejected candidates, including the actual 3,327 unspecified markers from 2,897 messages. Report gains and losses, exact marker/geography transitions, monthly classification yields and blank-label human review examples. A reduction in yield is not concealed or described as loss of actual threats. This is not a separate large gazetteer project and does not authorize time-series analysis or forecasting.

## ADR 017 — Research-lead approved context refinements (Task 004 continuation)

**Status: Accepted rule interpretation; general semantic validation still pending.** On **2026-10-11**, the user explicitly approved the following rules in response to real examples:

- `Троя бпла` and `ДВРЗ бпла`: Kyiv, current threat. Generalize to short named-city-locality threat bulletins; generic UAV stays generic.
- Movement from suburbs toward Kyiv: Kyiv-relevant alert context, retaining both source locations and literal mixed geography.
- `Тривога в Києві через бпла біля Чабанів`: explicit Kyiv alert cause even with an oblast location.
- `Буча бпла`: not Kyiv City. Do not extend standalone oblast reports into direct city evidence.
- `Центр бпла`: Kyiv in this inspected channel. The unconfirmed Soloma/Forest/bank abbreviations retain previous anchoring requirements.
- `Пуск Кинджалу`: Kinzhal threat context relevant to Kyiv. Preserve unspecified source geography; do not invent a destination or cause.
- Include probable/potential operational warnings; keep the uncertainty flag and original context. Do not promote an uncertain cause into confirmed textual attribution.
- `шах`: Shahed shorthand. Bare `реактивний`: user-inferred Shahed context. Preserve explicit jet UAV/model categorization and avoid overlapping double-counting; do not assert a technically verified model from the bare adjective.

**Implementation:** preserve original configurations and all v1.0/v1.1-geo outputs. Add threat rule dictionary v1.1 (`config/threat_dictionary_v1_1.yaml`), geography dictionary kyiv-geography-v1.1 (`config/kyiv_geography_v1_1.yaml`, center override only) and transformation v1.2-reviewed-rules. Category IDs/order remain the approved taxonomy v1.0. Bound short bulletins to auditable token/length rules; infer route relevance only from a named city target within the same clause. Keep cancellations, historical summaries, questions, carrier explanations and unsupported hypotheses excluded. No cross-message object inference, arbitrary timestamp correction, or change to Task 003 linkage.

**Validation:** user-provided examples authorize rule design; they are not an independently held-out labeled sample or population quality estimate. Test exact rules and counterexamples, compare gains/losses against frozen versions, preserve trace fields and provide a fresh blank-label human review sample. No time-series analysis/forecasting or commit is authorized.

## ADR 018 — Read-only exploratory pattern discovery (Task 004.2)

**Status: Accepted diagnostic scope; candidate interpretations require review.**
The user explicitly requested investigation of current v1.2 other-only and
text-unclassified alert contexts, prioritizing October 2026. Keep all official
alerts, immutable source/classification inputs, complete evidence and missingness.
Use local sparse frequency/TF-IDF discovery; do not update threat/geography
rules, automatically classify, forecast, build a dashboard or create a commit.

The implementation uses a versioned diagnostic family codebook separately from
production YAML, unique-alert support ranking, six fixed historical periods and
blank human-review exports. A fixed seed/order plus single-thread clustering
supports reproducibility. Broad lexical or geography candidates can be unrelated,
out of area or cancelled; candidate overlap is a review ceiling, not promised
gain. The official October alert-start window ends October 4 (last interval ends
October 5 Kyiv time), while Telegram extends to October 10. Do not confuse these
source bounds or compare the partial alert month by raw full-month totals.
No semantic interpretation proposed by this diagnostic is approved for production.

## ADR 019 — Broad UAV grouping and alert-level consolidation (Task 004.3)

**Status: User-approved interpretation; semantic outputs remain provisional.**
On 2026-10-11 the research lead explicitly authorized generic operational UAV
terms to enter the existing `shahed_uav` analytical group, while preserving
`generic_uav` evidence and never identifying a Shahed model from a generic noun.
The category ID is retained for compatibility, with expanded semantics version
`v1.3-broad-uav`. Explicit Shahed/Geran, attack-UAV and source model subtypes
remain unchanged. This supersedes the generic-UAV grouping in ADRs 015–017
only for the new version; previous configurations/data stay frozen.

Reactive adjective/noun shorthand now enters `jet_uav`; channel-inferred
shorthand always retains `inferred_shorthand=true` and `uncertainty_flag=true`.
Explicit reactive-UAV / Shahed-238 lexical references are distinguished from
inferred shorthand and never become independent model/deployment confirmation.
This supersedes ADR 017's bare-reactive Shahed grouping in v1.3 only.
Only the approved reactive noun forms are added; no parcel/geography/elliptical
pattern from Task 004.2 is automatically promoted. Context, literal geography,
H2 timestamps, links, cause semantics and non-UAV vocabularies stay unchanged.

Use `config/threat_dictionary_v1_3.yaml` with frozen geography v1.1 and separate
classification_v1_3 directories. Historical rule IDs are retained for existing
spans despite category migrations; original subtypes remain recoverable. New
`uav_evidence_type` records generic/explicit/inferred distinctions. Generic
same-family arbitration must not suppress a generic marker merely because its
own new analytical category is in the UAV family.

Each official alert has one row and ordered distinct category flags. Preserve
chronological first/all accepted supporting IDs globally and by category. New
seven-state classification separates single/multiple specific analytical groups
from only_other and missing/unresolved states. `other` alongside one specific
group does not create multiple_types. Separate counts including other remain
available. Unavailable category/count/support observations remain null; observed
no-marker text has zero counts and empty support lists. Incomplete historical
coverage maps to outside_telegram_coverage while preserving the original partial
coverage field; no such partial row exists in the current real dataset.

Technical completion is not semantic readiness for threat-category time-series
conclusions. Require independent human labels and coverage-aware methodology;
interval-only descriptive work needs separate authorization and explicit DST /
partial-source handling. Do not begin time-series analysis or create a commit.

## ADR 020 — Progressive attribution experiment (Task 004.4)

The research lead authorized bounded cross-message exploration and five pre-alert
lookbacks, exclusively as PROVISIONAL — HUMAN VALIDATION REQUIRED. Frozen v1.3
accepted categories, metadata and source evidence remain unchanged. No dictionary
or production classification update is authorized by this experiment.

Experimental context uses a current explicit lexical anchor followed by an
approved Kyiv locality within five minutes and the next three messages. Competing
categories, resets and explicit other-region anchors stop propagation. Short
operational bulletins may be reconsidered, with original exclusions retained.
These are analyst-selected experimental bounds requiring human review, not an
approved interpretation rule. Generic UAV is never a specific model inference.

Pre-alert retrieval uses [start-lookback, start) for 5/10/15/30/60 minutes. Stage C
includes eligible no-linked-text alerts as a separate stratum, in addition to
remaining text-unclassified alerts. Earlier alert membership, intervening starts
or ends, and unresolved DST envelopes are flagged and excluded from clean gains.
Ambiguous links remain candidates. Never treat a pre-alert explicit-cause text as
a confirmed cause of the next official interval. Retain all five experiments;
10 minutes is a review priority, not a validated optimal production window.

## ADR 021 — Controlled diagnostic review (Task 004.5)

The research lead explicitly requested a diagnostic sample, not classifier
corrections or acceptance of Task 004.4 candidates. Preserve H2, Task 003 links,
all v1.3 classifications, dictionaries and attribution experiment artifacts.
Build review-only outputs under `reports/controlled_review/`.

Select 20 text-observed unclassified alerts in requested disjoint date/volume
strata and five positive controls. Seed 20261011, sorted-ID seeded shuffle with
novel recorded-signal coverage; positive controls prioritize existing non-uncertain
accepted category diversity, explicit cause evidence and lower message volume.
High volume means ≥20 linked text messages; low means ≤3. Report any unavailable
stratum rather than replacing it. This is purposive error-discovery sampling,
not a representative estimate of population precision, recall or error rates.

A–H remain human-review hypotheses. Automatic indicators identify recorded
rejections/missing hits/provisional associations only. Neither a rejection nor
missing classification establishes an error. All original messages including
empty/no-hit records remain visible. All candidate occurrences and accepted
markers are retained, with available source/rule/context/geography provenance.
Absent legacy context/geography pattern IDs, exact overlap suppressor identities
and Task0044 occurrence spans are explicitly `not_recorded`; no fictional
internal decisions are reconstructed. Human labels start blank.

Use openpyxl for native Excel review, original timestamp columns alongside Kyiv
local display dates, drop-down decisions and internal navigation. If Excel cannot
represent full text, log cell-specific limitations and retain exact text in CSV.
No dictionary, context rule, geography rule, classification or approved method
changes are authorized by this task. Stop for research-lead case review.

## ADR 022 — Context-aware attribution v1.4 (Task 004.6)

**Status: User-authorized experimental correction; human validation required.**
The research lead explicitly approved reconsidering operational lexical anchors
inside official Kyiv intervals independently of literal Kyiv geography / legacy
uncertain context, bounded cross-message episodes, and a provisional ten-minute
pre-alert lookback. Preserve the v1.3 data/config/results and Task 003/H2 intervals.
New associations are experimental, not verified weapon deployments or Kyiv direction.

Use the frozen v1.3 lexical/context/geography engine with separately versioned
attribution policy `config/attribution_v1_4.yaml`. During this task the research
lead additionally clarified **бандероль = реактивний БПЛА**. This one explicit
lexical alias is included in the v1.4 composed profile as jet_uav, without a model
inference or taxonomy expansion; no other discovery euphemisms are promoted.
All v1.3 accepted occurrences/categories are preserved. Existing explicit jet /
generic-family priority suppression prevents counting one reactive UAV phrase as
two different threat categories.

Operational eligibility is checked before geographic attribution. Negative/history,
non-operational/joking/donation/explanatory contexts and suppressed lexical rules
cannot create new accepted evidence. Recorded other-region geography may name a
route's origin; inspect the target separately while retaining literal geography.
An explicitly different city's center is not a Kyiv-center anchor. Any newly
accepted association retains uncertainty and the original source/exclusion reasons.

An episode has a ten-minute maximum anchor age and five-minute maximum gap between
consecutive messages. Clear resets and new competing explicit anchors end the
previous episode. Multiple concurrent categories leave elliptical references
ambiguous. Geography-only messages cannot create categories without explicit
anchors. Pre-alert [start-10 min, start) links retain previous membership,
intervening official boundaries and unresolved envelopes; contaminated evidence
cannot transfer. Weak pre-alert anchors need coherent inside-interval followups.
Pre-alert context is never promoted to an explicit cause of the next alert.

Reviewed IDs live only in an audit fixture, never in attribution logic. Cases
2563/2565/2578 reproduce shahed_uav. The research lead instructed **retain the
2581 discrepancy for review** after clarifying banderol: explicit sources support
jet_uav, while the initially supplied approved table additionally lists shahed_uav.
Do not fabricate a second type or override by ID. Case 2590 is only a working
hypothesis, not independently confirmed. Development cases are not held-out
population accuracy evidence.

Measure correction supports as overlapping unique-alert sets and separately run
four full-data ablations disabling each correction. Neither support nor ablation
counts are additive. No coverage improvement establishes accuracy. Stop after
experimental outputs and review; no time-series analysis or forecasting.

## ADR 023 — Residual diagnostic review (Task 004.7)

**Status: DIAGNOSTIC — HUMAN REVIEW REQUIRED.** The research lead requests
diagnosis, not another classifier correction. Preserve all v1.3/v1.4 outputs,
source datasets, H2 timestamps, temporal links and dictionaries. Fail before
generating outputs if the baseline differs from 2594 official / 1803 eligible /
1050 classified / 655 text residual / 98 no-text / 790 outside / 1 unresolved.

Record overlapping A–F conditions and a deterministic primary partition with
priority A,C,D,B,E,F. Exact conditions, diagnostic-only lexical probes and source
evidence IDs are published in the residual summary and machine CSV. These are
initial grouping choices, not validated causes or approved classifier rules.
Place-only bulletins do not determine a weapon category; recorded non-operational
signals are only a coarse proxy. Finite gap probes are not an exhaustive inventory
of missing words or unknown localities.

Select primary-group quotas A8/B8/C8/D6/E5/F5, seed 20261011. Exclude all 25 prior
Task0045 sample alerts and the five discussed cases from both new samples.
Sorted-ID seeded per-year pools cycle available years 2023–2026; within each next
year prefer unseen recorded rejection/probe/geography/boundary/volume signals,
using seeded order for ties. Report quota shortfalls; use unused year-balanced
cases only as an explicitly flagged fallback. No fallback was required here.

The ten newly classified safety cases prioritize unseen ballistic / strategic /
jet / pre-alert / uncertain-geography / multi-category uncertainty flags, then
year diversity and number of flags. These are possible over-attribution cases,
not confirmed false positives and not a representative accuracy sample.

Export every linked in-alert record, including empty/no-hit records, and all
available timed messages in [start-10min,start) separately. Supplementary
[end,end+10min) chronology supports boundary diagnosis only. Frozen lexical
readouts of post-alert text are explicitly unaccepted, do not assign alerts and
never modify a classifier artifact. Original text/title/ID/file/index, candidate
rejections, recorded rules and cross-message anchor text remain traceable.

Audit all 98 no-text cases separately, including nearest previous/next source
records and surrounding publication gaps; no absence-of-threat inference.
Human fields start blank. Protect raw/data/config/classifier/prior-report hashes,
validate complete chronology and local offsets, rerun existing tests, and stop
for dialogue-based human review. Do not implement v1.5 or time-series analysis.

## ADR 024 — Targeted attribution v1.5 (Task 004.8)

**Status: user-authorized experimental correction; human validation required.**
Task0048 explicitly supersedes the previous stop before v1.5. Preserve v1.3/v1.4,
Task003 links, source text/timestamps, H2 and official intervals. Keep the threat
taxonomy and broad-UAV semantics. Do not create a commit automatically.

Compose the frozen v1.4 lexical profile with two narrow patterns: inflected
ballistic weaponry and enemy UAV. Existing ballistic-origin and reactive
shorthand expressions receive full-context qualification rather than a blanket
noun bypass. Occurrence-specific scope preserves exact source expressions and
positions for history, explanation, quotation, questions and negation. An
introductory question in a different clause does not reject a declarative warning.
Negation of MiG does not negate a different family; no confirmed strikes does
not mean no UAV. Direction reversal is movement; lost observation stops an
episode without deleting earlier valid evidence. Valid frozen positives remain
accepted; record invalidated scoped evidence and unsupported pre-only transfers.

Use a five-minute ordinary gap / ten-minute anchor age. Short route/state
updates can support an explicit earlier anchor; static foreign regional threats
cannot jump to Kyiv through an unrelated locality message. Multiple simultaneous
families leave pronominal references unresolved. Retain the ten-minute lookback,
but require in-alert correspondence for every accepted pre-alert anchor. The
explicit “Тривога в столиці через нього” reference may bridge an ordinary gap
over five minutes only if source anchor-to-reference age remains <=10 minutes.
This is a narrowly specified reference rule, not a global wider context window.
Previous alert membership, intervening boundaries and unresolved envelopes block
transfer. A pre-warning alone never attributes a category to the next interval.

Reviewed IDs remain only audit fixtures, never interpretation exceptions.
The six new confirmed labels are preserved; 1416 remains provisional. The user
reconfirmed 1096 = shahed_uav + ballistic_high_speed. The current source-backed
engine reproduces shahed_uav, while its preceding ballistic warning lacks a
type-linked in-alert correspondence under the requested policy. Retain the
confirmed target and report the discrepancy; do not invent an anchor or silently
broaden pre-alert transfer. The earlier 2581 discrepancy remains retained by the
user's prior decision; 2590 remains a working hypothesis.

Reserve the remaining 43 Task0047 cases as an untouched diagnostic holdout. Do
not inspect their source examples to tune rules or infer gold labels. Store
frozen rule hashes before full-data inference; generate only diagnostic category
outputs for these cases. Select a separate 20-case newly-classified audit excluding
holdout and all development/prior review cases, seed 20261011. Prefer five each
strategic, ballistic, pre/context and other-uncertain strata; report shortfalls
and fill from unused year-balanced weak-evidence cases. Only one new strategic
candidate was available after exclusions, so four cases use documented fallback.

Run five correction-disabled full-data comparisons with safety guards retained.
Unique alert support and ablation counts overlap; neither implies accuracy.
Publish gains, losses, category removals, year/month denominators, uncertainty,
pre-only lexical evidence with inside corroboration, regression discrepancies
and complete twenty-case source timelines. Stop after Task0048, no forecasting.

## ADR 025 — Residual marker improvement v1.6 (Task 004.9)

**Status: user-authorized experimental iteration; human acceptance pending.**
Preserve prior versions, sources, taxonomy and approved H2 temporal interpretation.
Task0049 authorizes all 564 text-residual diagnostics, evidence-supported lexical /
context fixes, full 2594-alert inference and compact exception review. It explicitly
forbids unsupported labels to reach 70%, automatic commits and forecasting.

On 2026-10-11 the lead approved “МіГ”, “+МіГ”, “Міг в повітрі” as the channel's
conditional convention for mig31. Keep subtype `mig_channel_model_unspecified`,
inferred uncertainty and no actual MiG-31K model claim. Limit promotion to finite
standalone/repeated/count, takeoff, in-air or explicit alert-cause formats. The
ordinary verb, uncertain-model commentary, jokes and negative/history contexts
remain excluded. Record approval in the isolated policy, not ID-specific logic.

Compose frozen lexical profiles with actual residual expressions: балістиці,
ballistic target/trajectory forms, БРСД, Tu-95 without variant, missing cruise
inflections. Mask only exact known channel footer lines for context; preserve
source characters, offsets and full original text. Separate current warnings from
carrier explanations and non-operational clauses. Current type-only bulletins,
explicit Kyiv-local UAV positions and probable cruise reports retain uncertainty.

Strengthen scope for explicit absence (including distant negation of a named
threat), satire, retrospective summaries, explanation and non-threatening aircraft
missions. No-launch-only does not cancel aircraft activity; no strikes does not
cancel UAV threat. Current absence stops bounded references, not prior positives.
Reject Kursk-origin strings being treated as “course”; foreign current threats
cannot transfer through a later unrelated locality. Keep five-minute ordinary gap,
ten-minute anchor age and ten-minute pre-alert window with inside corroboration.

Compact analyst source audit has 20 targeted source/category checks; fixture IDs
occur only in audit configuration/tests, never classifier interpretation code.
It is not independent population accuracy or lead-approved gold. The previous
43-case holdout remains unlabeled; all-residual exploration is not a blind v1.6
evaluation. Preserve confirmed 1096 and 2581 label/source discrepancies and
provisional 1416/2590, without manufacturing supporting messages.

Measured v1.6 yield is 1295/1803 (71.82%), 155 gained and one lost against v1.5.
Lost 2241 had only “По БпЛА чисто станом на зараз” accepted previously. All added
categories have provenance; category-level changes/removals are separately visible.
Unknown states remain 410 text, 98 no text, 790 outside history, one unresolved.
The target is reached but does not validate classification accuracy. Stop marker
iteration and prepare v1.6 technical handoff, conditional on lead acceptance.

## ADR 026 — Task005 retrospective temporal diagnostics

**Status: user-authorized exploratory analysis; no forecasting.** Task005 explicitly
selects experimental v1.6 as primary; this does not approve it as ground truth.
The user authorizes committing Task005 documents. Preserve all prior data/rules.
A=resolved official intervals; B=all eligible alerts, including unknowns. Keep the
unresolved official row in fact/all-record start sensitivity; never select a fold.
Use Europe/Kyiv day splitting and interval unions; zeros only inside official
observed span; endpoint days and partial periods labeled. Unknown is not absence.
Before numerical analysis: choose daily count dispersion/ACF, complete-year
contrasts and complete-2023–2025 equal-year seasonal contrasts; moving blocks14
days, sensitivities7/28,1200 replicates,seed20261011. Weekly blocks8 weeks.
Duration-category exploratory associations use log1p duration, calendar-month
centering among classified alerts, joint day resampling and Holm correction for
seven approximate bootstrap-SE Wald comparisons. Other descriptive effects have
pointwise intervals, no confirmatory p-values. Nonstationarity/short seasonal
replication preclude validated break/seasonal claims. Weak-month sensitivity uses
<60% interpretation yield with >=10 eligible alerts; this is not an accuracy rule.
No random temporal split, forecast, unknown imputation or physical weapon counts.

## ADR027 — Task005.1 external reconciliation and interpretation

**Status: user-authorized retrospective external validation; no classifier change.**
Use pinned public GitHub snapshots, separate volunteer/eTryvoga from third-party
archives of an official channel. Neither is independent gold truth. Record web
proxy403 failures as access limitations, never as evidence that data do not exist.
Official cause/threats semantics require accessible primary documentation; never
map a broad warning level to the seven experimental weapon-context groups.
Reconcile strict Kyiv City only, parsed explicit UTC offsets and local calendar
months. Deduplicate identical external intervals while preserving all original
CSV row numbers. Common-period primary comparisons exclude source endpoint days.
Primary one-to-one matching maximizes cardinality among positive-overlap intervals
whose starts differ <=5 minutes, then minimizes absolute start differences.
Report1/5/10-minute sensitivity and all overlaps for potential split/merged events.
Estimated volunteer ends remain identified and excluded from reliable end-delta
summaries. The existing unresolved DST endpoint stays null and outside resolved
matching. Count unmatched sources separately; no global time correction.
For1803 eligible v1.6 intervals retain mutually exclusive one/multiple/unknown
states, category single/co-occurring distributions by month/year, empirical
classification yield in duration/message-volume bins and joint strata. Daily
cluster moving blocks14 days,seed20261011,800 replicates quantify exploratory
bin-rate uncertainty; associations do not imply duration causes classifications
or physical threats cause durations. No predictive model, causal inference or
unverified external accuracy score. Prior authorization to commit research
reports persists; raw third-party exports remain local and uncommitted.

ADR027 execution update: network restrictions resolved for Kyiv/alerts sites.
The official export is entirely identical to originals, including194 typed causes.
All2594 history start clocks match; first typed history2026-09-07. Compare209
positive official cause instances across194 alerts, using exact/partial crosswalks,
with no full accuracy estimate or negative-source inference. Dated2026-09-08 city
statement confirms Sep7 decision/Sep10 differentiated-warning implementation.
139/190 September starts are yellow; the corresponding exclusion sensitivity
reverses the raw August→September count increase. Preserve Task005 outputs and
labels; reinterpret late growth as procedurally confounded, not pure physical
escalation. Source support is only warning context, not launches/weapon model.
DSNS/jet-specific direct technical evidence remains limited; no bypass. No
classifier corrections, official endpoint repair, forecasts or Task006 start.

## ADR 028 — Task006 retrospective aggregate forecastability protocol

User Task006 authorizes weekly official starts, all warning colors, one-week horizon,
without modifying the historical sources. No yellow exclusion or causal policy claim.
Frozen before inspecting forecast scores: complete Monday–Monday Europe/Kyiv weeks,
conservative exclusion of source endpoint dates; initial 52 calendar weeks;
development origins before 2026-01-05, final holdout origins from 2026-01-05.
One candidate: log-link L2 Poisson autoregression, standardized log1p lags1/2/4
and preceding4/8 calendar-week means; alpha grid1/10/100. All fitting is past-only.
B4 windows13/26/52 selected by development MAE; then candidate alpha and strongest
baseline selected on development only, frozen for final expanding evaluation.
All models score on common available origins. A no-record week is unknown in the
primary experiment (not an observed zero); exclude unavailable lag windows. An
explicit archived-zero sensitivity is separate and cannot certify completeness.
Positive weeks also have unverified internal completeness; infer only recorded activity.
Primary paired absolute-error difference uses circular4-week blocks,2000 repetitions,
seed20261011;8/13-week block sensitivities. Pointwise intervals are conditional on
this short nonstationary holdout, not guaranteed calibration. No opportunistic retries.
A requires >=10% final MAE gain over development-selected baseline, paired95%CI
strictly below zero, lower final MAE than every baseline, and positive skill in at
least3 of the4 year strata2023–2026 (year strata are partly development evidence).
Otherwise B if the archived target can be evaluated but no stable gain; C if data
or execution prevents evaluation. Forecast uncertainty is not operational warning.
Low/high activity groups use training-only expanding median; shift flags use
training-only recent4 versus preceding8 means, absolute difference>=5 counts/week.
September/post-Sep10 subsets are descriptive and too short for independent inference.
No category features, future detrending, full-sample scaling, live forecasts or dashboard.
Secondary forecasting is deferred: unresolved duration and completeness make minutes
less defensible, and monthly sample size is small. Retain monthly descriptive counts.
Existing document/push authorization persists; publish derived reports and review bundle
only, never raw source exports. Stop after Task006.

ADR028 execution: 52 initialization weeks,139 development origins,39 final origins;
selected B4=13 weeks, M1 alpha10 and baseline B1(previous4-week mean). Final M1
MAE7.3921 versus B1 5.6923 alerts/week; paired difference1.6998,95%4-week-block
interval[-0.0923,4.1317]. All baseline/candidate results retained. Final decision B,
NO_STABLE_GAIN_OVER_BASELINES. Excluding September-start weeks still leaves M1
MAE5.8815 versus B1 5.4143. September increases the gap but does not change decision.
All colors retained;3 full post-policy weeks descriptive only. No dashboard/chatbot/
deployment begun. This is evidence about archived administrative counts, not physical
attack timing or certified real-time predictability. 613 tests pass; prior files frozen.

## ADR029 — Task006.1 threat-specific reported-marker assessment

User authorizes a separate assessment, not a transfer of Task006's overall B result.
Frozen before forecast scores: config/threat_forecastability_v1.yaml. Each target
counts unique eligible alerts with a detected v1.6 category, never attacks/launches.
Seven overlapping categories retain nullable source flags and unknown denominators.
Complete Kyiv calendar weeks inside both histories; no-record weeks/unresolved or
partly covered alert weeks remain unavailable. Each weekly finalized label release
is conservatively max(week end, alert ends, every accepted marker/support time).
Both versions use the later release for matched comparisons. Before each origin,
mask outcomes not yet released; exact calendar lags, not compressed observations.
Initial52 calendar weeks from first complete Telegram-covered week; development
before2026-01-05 and final2026. Data-quality gates:>=104 observed weeks,>=100 positive
alerts,>=40 development and20 final positives,>=20 development and10 final positive
weeks,>=20 scored origins per phase, v15/v16 alert-set Jaccard>=.70, annual coverage
range<=.25,<=40% observed weeks below60% classification. These are conservative
research sufficiency screens for reported counts, not validated clinical cutoffs.
Do not forecast failed categories. Baselines mean/lastweek/previous4/previous8;
zero-count reference retained to contextualize sparse observed marker targets.
One optional Poisson candidate, Task006 alpha10 fixed, only if development recent
baseline gains>=10% over mean and paired4-week95%CI strictly favors it. Baseline
selection on development only; no category hyperparameter search/final retuning.
Final14 planned contrasts (7 baseline-vs-mean,7 candidate-vs-selected) use paired
circular4-week blocks,4000 reps, Bonferroni familywise5%;8-week sensitivity. Unrun
contrasts retain slots. Signal requires>=10% gain, adjusted interval favoring method,
positive skill in development/final, and same gain direction in v1.5 and final
non-weak-month sensitivity. Fragile favorable results INCONCLUSIVE, no stable gain
otherwise; failed gates INSUFFICIENT_DATA_FOR_RELIABLE_FORECAST_TEST.
Weak-month filtering affects diagnostic scoring only, never availability/features
or selection: whole-month quality is not known at its first weekly origin.
Frozen dictionaries were developed retrospectively using full-history review:
a category holdout is untouched for numerical model selection, NOT blind to label
engineering. No archived as-of taxonomy/source publication latency is established.
Any favorable marker-target finding remains exploratory pending independent future
annotation protocol. No physical predictability/safe-period conclusion, taxonomy
changes or dashboard. Persistent user code/docs push authorization remains valid.

ADR029 execution:163 calendar weeks,161 observed; 48 development origins
2024-08-26–2025-12-29 and36 final origins2026-01-05–2026-09-14 for each passed
category. 27 potential origins excluded; late September origins lack finalized
prior-week labels, limiting evaluation of the final high-activity tail. Calendar
blocks preserve these unobserved positions. Broad UAV passes (630 labels): recent4
MAE3.0208 versus historical mean4.0746, but adjusted difference interval[-3.8843,.4308]
includes0. Candidate MAE3.5633; decision INCONCLUSIVE. Ballistic passes(458 labels):
development-selected mean MAE1.6881; recent4 final1.5764 (6.6% gain, not selected on
final). Development baselines did not support an extra model, so none is fitted;
decision NO_STABLE_GAIN_OVER_BASELINES. Jet, cruise, MiG, strategic and other fail
fixed data/version gates. MiG Jaccard.6655 would pass at a relaxed.65 screen; this
threshold sensitivity is recorded without rerunning forecasts or changing the gate.
v1.5 and non-weak-month checks do not establish a stable UAV candidate advantage.
No category has conclusive adjusted evidence of predictive signal. This is not a
physical unpredictability claim. 626 tests pass; all earlier inputs/results frozen.
Existing authorization covers publication of new source/config/tests as well as
reports and derived review bundle. Stop after006.1; no dashboard or deployment.

## ADR 030 — Task007 static research presentation

User Task007 explicitly authorizes a web presentation superseding the charter's initial no-web-application scope. No research objective, target, classification, timestamp or saved analytical output changes. Publish allowlisted aggregates only, with provenance hashes; unknown/null values retained. Official start counts use all2594 records; duration denominator is2593. Category counts overlap and do not certify weapons. Global cards are not recomputed by partial filters. No chat or operational predictions. Six Ukrainian sections, React/Vite/TypeScript/Plotly, repository base and hash navigation. Existing persistent user authorization covers committing/pushing code and documents. Hosting is separately subject to research-lead approval per Task007; workflow is manual-only and no repository settings changed.

## ADR 031 — Task007.1 scoped Myth Lab descriptive checks

User explicitly authorizes seven historical hypothesis cards and separate new
aggregates, without modifying previous results. `config/myth_lab_v1.json` freezes
calendars/definitions before computing contrasts. Kyiv warning counts are proxies,
not Ukraine-wide strikes or targeting motives. Six stable fixed Ukrainian holidays
are the selected subset, not the complete changing holiday calendar. Conservative
control exclusions include moving Orthodox Easter/Trinity (manually versioned)
and both old/new fixed holiday dates; wartime days-off status is not inferred.
Symbolic controls match same-month weekdays at ±7/14/21/28 days and omit selected
event windows. Event day and ±1day windows both shown, without outcome selection.
Negotiations: three source-confirmed Istanbul meetings, before/after3days primary
and7days sensitivity; no event selection based on alert outcomes or causal test.
Night22:00–06:00 Europe/Kyiv uses actual interval overlap in UTC elapsed minutes,
separate starts/intersections/clock-exposure share and annual/version sensitivity.
Calm: preceding3calendar days have at most1start; zero-start sensitivity. Daily
contrasts omit source endpoint days, unresolved-end day and the no-record week
already flagged in Task006. Matched differences are descriptive; no new calibrated
p-values or operational forecast claims. Small-sample calendar/motive claims remain
inconclusive. Task005 lag1 metrics are reused verbatim, not recomputed differently.
No hosting activation or workflow change. Persistent user authorization covers
Git source/docs push; public hosting still requires separate approval.
