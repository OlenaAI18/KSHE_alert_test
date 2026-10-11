# Planned methodology

The research plan originated in Task 001. Ingestion/time normalization and descriptive temporal integration are now implemented through Task 003; Task 004 implements provisional classification; inferential analysis and forecasting remain prospective. No statistical hypothesis conclusions are claimed.

## Units and transformations
Retain one observation per official alert, one per Telegram message, and a separate many-to-many temporal mapping. Preserve raw bytes and original timestamp strings; future normalized records retain source identifiers and transformation versions. Record input checksums, validation outcomes, and rejected/quarantined records rather than silently discarding them. Document normalization of string `"null"` separately from native null.

## Time and integration
Sources are user-confirmed as aligned. Do not apply arbitrary offsets. Inspect actual timezone representations before selecting parsing rules; handle Europe/Kyiv DST and calendar boundaries correctly. Internal UTC normalization uses the source-specific H2 rule accepted in ADR 013. Task 003 explicitly approves half-open intervals `[start, end)`: a start-boundary message belongs to that alert, an end-boundary message does not. Overlapping resolved intervals retain all mathematically valid links with review quality rather than choosing one. Unresolved intervals receive no fabricated endpoints or links; candidate DST folds only bound uncertainty. Analytical local-calendar features beyond descriptive coverage grouping remain deferred. Temporal links preserve message-level evidence and do not imply Kyiv-directed threats.

## Context markers and missingness
Use the Task 004-approved version-controlled v1.0 multi-label scheme described below. The Task 001 placeholder taxonomy has been superseded. Retain supporting message identifiers and dictionary version. Address synonyms, ambiguity, negation, historical references, reposts, geography, and multiple categories before implementation. Empty placeholder rules must not produce classifications. Unknown information, no detected mention, unavailable coverage, and confirmed absence are distinct concepts; none are interchangeable.

## Analysis and evaluation
Retain pre-Telegram alerts for interval-only baselines. Consider descriptive frequency/duration, daily/weekly aggregation, rolling summaries, autocorrelation, justified decomposition, structural breaks, and regime comparisons. Choose aggregation, hypotheses, and uncertainty methods before inferential analysis; document multiple-testing and sensitivity decisions. Never use random time-series train/test splits.

For any conditional forecast experiment, approve aggregate target and horizon first. Use chronological splits, walk-forward evaluation, simple baselines, training-only fitted transformations, and explicit feature availability timestamps. Information observed during/after an alert is not automatically available before it. Select models using training/validation periods and reserve untouched test evidence. Report errors, uncertainty, instability, and unsuccessful experiments. No safety or individual-attack predictions are permitted.

## Limitations
Threat/reporting regimes are non-stationary; Telegram coverage is incomplete and non-authoritative. Associations are not causation. Forecasting and an aggregate MVP proceed only if robust out-of-sample evidence supports them; no stable patterns is a valid result.


## Task 003 coverage interpretation

Temporal association is computed without keyword filters or relevance scores. A message inside a Kyiv alert can discuss another region, commentary or unrelated content; linkage alone is not a threat marker. Counts track all accepted messages and non-empty text separately. Original alert/message records remain intact, including unmatched records and pre-export alerts.

Coverage is reported only relative to the observed Telegram date span. No-history, partial-history and unresolved states remain distinct from a resolved within-span interval with no messages. Monthly rate denominators exclude unresolved or not fully observed intervals. The entire possible range of the DST-ambiguous official interval is withheld conservatively, including messages definitely before both possible ends, so that no link has a fabricated or null official end. This scope decision is explicit and reversible after separate evidence resolves the fold; it is not an automatic data correction.

## Task 004 implemented provisional classification

The user-approved v1.0 taxonomy supersedes the Task 001 placeholder identifiers: shahed_uav, jet_uav, ballistic_high_speed, cruise_missile, mig31, strategic_aviation, other, unknown. Zircon belongs to the proposed analytical high-speed grouping; Kh-59/69 belong to the research missile grouping. These are research groupings, not claims of identical technical weapon classifications. Concrete lexical subtypes remain in evidence.

Only Task 003-linked messages are classified. All messages, including no text/no keyword, are accounted for; candidates retain exact source spans, rule IDs and provenance. Normalization maps single characters for lowercase, dash and apostrophe variants without altering originals or changing character-offset length. No stemming, embeddings, APIs or language model inference is used.

Context is clause-level and conservative. Priority is cancellation/negation, historical/summary, uncertainty/explanation, explicit alert cause, current operational threat, otherwise uncertain. Cause rules require alert/cause wording in the same clause as the marker. Descriptive carrier explanations are uncertain. Takeoff/activity is sufficient contextual evidence without a launch; absence of launch alone does not cancel aircraft activity. Unspecified-model MiG takeoff is review-only. Question marks, hypothetical qualifiers and uncertain reports trigger review. These rules cannot reliably resolve every mixed-context sentence.

Geography uses a small visible name/rule list. A clause's explicit geography takes precedence; absent geography falls back to unambiguous message-wide geography. Mixed city/oblast/other/nationwide references are uncertain. Kyiv Oblast is not Kyiv City. Aggregation accepts only current_threat or explicit_alert_cause with explicit_kyiv or nationwide. Oblast, other-region, unspecified and uncertain matches remain in the marker dataset but do not silently become direct city threats. This deliberately limits recall; unlisted districts and elliptical follow-ups often remain unknown. A city name can still refer to origin/transit/commentary: human review remains necessary.

Generic UAVs do not prove Shahed, and generic missiles do not prove cruise or ballistic type. The `other` category retains these lexical subtypes. Higher-priority specific matches suppress overlapping generic candidates; same-clause specific-family matches also suppress separate generic family words, preserving all suppressed evidence. Non-overlapping broad Shahed and jet mentions may coexist, but alert-category counts are overlapping mention sets, never weapon counts. Combination order is fixed by YAML; there are no hardcoded combination classes.

Missingness follows Task 003. No history, no appropriate text or unresolved timing produce null observed-category fields, while available text with no accepted marker produces false detection fields and an unknown classification state. No observation is converted into evidence of absence.

Monthly diagnostics use Europe/Kyiv alert-start months. Denominator 1 is fully historically contained, resolved eligible alerts; denominator 2 is eligible alerts with non-empty linked text. Unavailable monthly rates are null. Reporting density (publication counts and linked messages per eligible alert) describes varying observation opportunities, not threat incidence or statistical regimes. No time-series inference or forecasting was started.

## Task 004.1 Geographic Dictionary Expansion

The user authorized a narrowly scoped finite geographic dictionary, not a complete list of Kyiv Oblast settlements or a redesign of context detection. Optional `--geography config/kyiv_geography.yaml` enables classification v1.1-geo. With the option absent, legacy v1.0 geographic behavior remains reproducible. Threat lexical rules, context status rules, timestamps and integration are unchanged; original v1.0 tables/reports remain frozen at their original locations.

The new dictionary recognizes explicit inflections, common alternative spellings, district abbreviations and selected colloquial names. It preserves source spelling, canonical locality and locality type. Generic center/bank/forest labels, ambiguous Borshchahivka shorthand, and district names shared by other cities need explicit Kyiv or an unambiguous city-locality anchor. A nationwide warning, channel name or temporal association alone cannot supply that anchor. No destination or weapon geolocation is inferred. Longer specific locality names suppress overlapping shorter aliases. Specific matched localities replace fully covered legacy broad-region matches (e.g. Kharkivskyi Masyv is a Kyiv locality, while Kharkiv is another region; Boryspil is oblast, not generic other_region).

Every previously rejected candidate, including all 3,327 previously unspecified-geography markers, is reevaluated with unchanged threat/context rules. Comparing before and after requires identical threat-candidate identities, original text spans, categories/subtypes, context, source provenance and official alert/coverage fields. Both gained and lost classifications are reported; additional geographic recognition can make previous city-only evidence mixed and thus uncertain. Changes in classification coverage measure detection yield, **not improved precision or recall**.

A new 180-example review sample covers geographic transitions, inclusion/exclusion gains/losses, unchanged inclusion with newly named localities, context and historical years. It complements the original sample. Human decisions remain unfilled. Remaining unspecified examples are exposed for discovery of missing names; no unreviewed name is automatically added. Terse locality/threat fragments often still have uncertain context; changing that rule would require a separately reviewed refinement, not be hidden in a geography-only comparison.

## Task 004 user-approved context refinement — v1.2-reviewed-rules

ADR 017 supersedes the strict mixed-geography and default-uncertain exclusion **only for the explicitly approved rules**. A short named Kyiv-locality plus threat bulletin can be current_threat; generic UAV remains other:generic_uav. Center denotes Kyiv in this inspected channel. A target phrase toward a named Kyiv locality or an explicit Kyiv alert cause makes the marker relevant even when an oblast origin/current location is also named. Standalone Bucha and other oblast reports remain excluded from direct Kyiv aggregation.

Literal `geography` is kept distinct from `relevant_to_kyiv` and `relevance_rule_id`. Thus `від Вишгорода на Київ` may retain uncertain/mixed text geography while being relevant by user.toward_kyiv; a bare Kinzhal launch warning retains unspecified geography while being relevant by user.kinzhal_launch_warning. Route interpretation stays clause-local; no weapon destination, actual launch, or causal truth is independently established.

Probable/potential operational warnings may enter aggregation with evidence_status=uncertain and uncertainty_flag=true. Original status and normalized qualifier words remain available. Short-bulletin promotions preserve context_status_original and context_rule_id. Uncertain textual cause remains outside explicit_cause_categories. Short bulletins have a visible character/token bound to avoid turning any locality-plus-keyword commentary into a current warning. Questions, historical/cancelled statements, carrier explanations, unsupported conditional/future contexts and unspecified-model MiG claims remain excluded.

Shakh shorthand and the bare reactive adjective are dictionary candidates with explicit subtypes; reactive_shorthand_user_inferred records the research lead's contextual interpretation, not a verified Shahed model. Explicit jet UAV/238 matches retain jet_uav. The approved example containing bare `крилаті` adds a reviewable cruise shorthand. Specific overlapping terms suppress generic ones and remain auditable. An inferred weapon family alone does not supply missing geography; the special no-place relevance rule is limited to Kinzhal launch warnings.

Run with the paired new dictionaries and separate classification_v1_2 destinations. Previous profiles remain reproducible and frozen. Compare existing candidates and newly introduced lexical candidates separately, retaining source/interval invariants and reporting losses as well as gains. Rule-design examples must not be reused to claim independent precision/recall.

## Task 004.2 exploratory pattern discovery

This user-authorized diagnostic task reads reviewed classification v1.2 without
modifying sources, dictionaries or acceptance rules. Four exclusive populations
are A specific (including specific + other), B other-only, C text-unclassified,
and D unavailable/unresolved. Retain missing observations separately.

Rank word 1–3-gram and character 3–5-gram support by distinct B/C alerts rather
than message volume; A is the specifically classified comparison population.
NFKC/case/apostrophe normalization and Unicode tokenization are analysis-only.
Remove URLs, decorated footer lines and account-number noise from that analytical
representation, preserving original complete messages and short operational forms.
Frequency matrices are sparse and binary per message/alert. Period comparisons
retain coverage denominators and partial official-source windows. Smoothed
prevalence ratios are screening descriptors, not significance or regime tests.

Unsupervised grouping uses sparse word/character TF-IDF, sorted unique texts,
alert-balanced weights, fixed-seed single-thread MiniBatchKMeans and cosine to
assigned centroids in bounded chunks. No dense N×N matrix, external API or hosted
model is used. A transparent diagnostic family catalog, informed by October
source examples, complements frequencies/groups; it is not a production dictionary.
Elliptical updates require context review; no cross-message referent is inferred.
Human decisions remain blank. Candidate overlap bounds describe review workload,
not validated or predicted coverage improvement. Stop before any rule change.

## Task 004.3 alert-level consolidation — v1.3

ADR 019 authorizes broadening shahed_uav to an analytical UAV group including
qualified generic UAV terminology. Specific model/family source subtypes and
new evidence-type distinctions remain separate. Bare reactive adjective/noun
shorthand maps to jet_uav with explicit inferred uncertainty; direct jet-UAV
phrases/model references are distinguished. Category flags are group detections,
not confirmations of a model or weapon deployment. No additional place aliases,
parcel euphemisms, elliptical mentions or cross-message references are inferred.

The existing classifier applies unchanged context/geography qualification, then
consolidates accepted occurrences into one row per official alert. Each category
is boolean at most once regardless of repeated messages/mentions. Deterministic
combinations include all accepted categories; specific-state counts exclude
other. Chronological support IDs retain every supporting message globally and
per category. Same-message multi-category evidence is represented once in global
message support, separately in the category support blocks.

Seven states are mutually exclusive: single_type, multiple_types, only_other,
no_marker_with_text, no_linked_text, outside_telegram_coverage, unresolved.
Null unavailable observations remain distinct from observed zero markers. Keep
legacy_classification_status and original temporal coverage metadata. Audit
all-official, eligible and eligible-with-text denominators separately; report
any-category and non-other analytical-category yield. Month/year grouping uses
Kyiv alert-start calendar, retaining incomplete October/source boundaries.

Coverage comparison distinguishes genuinely newly classified alerts from
regrouping existing generic-UAV evidence. Increased non-other category counts
alone do not establish increased coverage or accuracy. Threat-category time-series
analysis requires independent semantic validation and explicit missingness /
reporting-drift methodology; software readiness alone is insufficient. No
Time Series Analysis is performed by consolidation/audit.

## Task 004.4 — Progressive attribution experiment

Run `.venv/bin/python -m kyiv_alerts.attribution` from the repository root.
Results are isolated in `attribution_experiment_v1` data/report folders. All
1,268 v1.3 text-unclassified intervals are inspected using their complete Task 003
chronological message sequences. Accepted baseline alerts are frozen. New evidence
levels are explicit_alert_cause, direct_operational_threat,
contextually_supported_threat, ambiguous_candidate and not_relevant. Supported
levels count provisional alert/category candidates; no human validation is implied.
ADR 020 specifies bounded context, strict lookbacks and contamination controls.

Window coverage is distinct alert support, not marker frequency. Repeated lexical
occurrences never add categories. Longer windows are nested alternatives and
cannot be summed. All-official, eligible and text-covered denominators differ.
Missing historical coverage and DST observations remain unknown. Clean candidates
mean no detected contamination and explicit approved Kyiv relevance, not verified
accuracy or causality. Known channel footers are removed only when measuring
short-bulletin length; original evidence text remains intact. Review workload and
ambiguous/contaminated support accompany every window result.

## Task 004.5 — Controlled diagnostic sample

Run `.venv/bin/python -m kyiv_alerts.controlled_review`; install optional local
Excel dependencies with `.venv/bin/python -m pip install -r requirements-review.lock.txt`
(or project extra `[review]`). CLI accepts `--root` and `--seed` (default 20261011).
Only the `reports/controlled_review` output directory is written.

The sample is purposive: 8 October 2026 unclassified, 5 August–September 2026,
4 high-volume 2024–2025 (≥20 text messages), 3 low-volume 2023–2025 (≤3), and
5 existing classified controls. Stratification and recorded-signal coverage
are documented in ADR 021. Include every existing linked message, not only
keywords; preserve every existing candidate occurrence and its recorded decisions.
The six-sheet workbook separates official interval timelines from supplementary
pre-alert experimental evidence. Blank human fields support A–H investigation,
not automated root-cause assignment or population metric estimation. No previous
classifier or attribution experiment is rerun or corrected.

## Task 004.6 — Context-aware experimental attribution v1.4

Run `.venv/bin/python -m kyiv_alerts.classification_v14` from the root. This separate
module reuses the existing lexical engine and unchanged source intervals. Policy:
`config/attribution_v1_4.yaml`; reviewed cases are audit-only in
`config/task0046_reviewed_cases.yaml`. The user-confirmed banderol alias is the
only lexical extension. Literal geography and source context/exclusions remain
traceable independently of experimental acceptance. Generic UAV never becomes a
verified Shahed model. Existing jet/generic overlap suppression remains active.

All previous accepted evidence is retained. New operational anchors can be
experimentally associated with official Kyiv intervals even without a literal
Kyiv word; explicit unrelated regional confinement and non-operational/negative
contexts remain excluded. Episodes and ten-minute lookbacks follow ADR 022.
Unresolved references remain candidates, not accepted categories. An accepted
pre-alert anchor may cite later inside-interval corroboration: these retrospective
features are not available at alert start and must never be used as forecasting
inputs without an explicitly approved availability model.

One output row per official alert; distinct categories and global/category source
message support are deduplicated. Original coverage fields do not change, and
outside-history/DST rows remain null/unknown. Eligible no-text alerts can gain
experimental context only if qualifying earlier evidence exists; no such gain
occurs in this run. Overlapping correction supports are distinguished from four
independent rule-disabled ablations. Report month/year yields with all-official,
eligible and eligible-with-text denominators; October is a partial-source month.

Weak pre-alert evidence is not resolved by an unknown directional phrase alone:
its inside-interval followup must contain a locality recognized by the frozen
geography dictionary. Unknown/locality-free movement remains ambiguous before
acceptance of that earlier anchor. Within an already anchored episode, short
movement verbs or recognized locality updates can support context; a bare
preposition such as an unrelated “на вечерю” cannot establish an operational link.

## Task 004.8 — Targeted experimental attribution v1.5

Run `.venv/bin/python -m kyiv_alerts.classification_v15 --root .`. New outputs:
`data/processed/classification_v1_5/` and `reports/classification_v1_5/`.
ADR024 and `config/attribution_v1_5.yaml` specify the authorized narrow corrections;
review targets are audit-only in `config/task0048_reviewed_cases.yaml`.

Keep separate fields for lexical threat identification (not physical confirmation),
operational status, literal/full-message geography, supported geographic relevance,
linking confidence, final acceptance and exact scoped exclusion spans. All
new accepted evidence carries uncertainty. An ordinary short-update gap is <=5min
and explicit anchor age <=10min. An explicit in-alert Kyiv cause pronoun can
corroborate a pre-alert anchor across a longer gap only within that same ten-minute
anchor-age limit. Every pre-alert acceptance cites an inside source record. This
retrospective link is not evidence available at alert start.

Valid prior evidence is retained. Losses from newly enforced negation scope or
unsupported pre-warning transfers are reported rather than hidden. Compare all
three versions on the same 2594 IDs and temporal coverage metadata. Report
overlapping supports and separate full-data ablations, month/year denominators,
pre-only lexical attributions (with mandatory inside corroboration) and uncertain
new classifications. Classification yield remains distinct from semantic accuracy.

The remaining 43 Task0047 review cases stay untouched for diagnostic human review;
rules are not tuned to their examples. Separate twenty-case stratified audit
includes every linked in-alert message and available ten-minute pre-alert context,
with blank human fields. Confirmed-label discrepancies for 1096 and previously
retained 2581 remain visible, not ID-based overrides. Do not forecast or commit
automatically; stop for review after Task0048.

## Task 004.9 — Final marker iteration, experimental v1.6

Run `.venv/bin/python -m kyiv_alerts.classification_v16 --root .`. Freeze v1.3,
v1.4, v1.5, original sources and Task003 temporal links; write separate
`data/processed/classification_v1_6/` and `reports/classification_v1_6/`.
Read ADR025 and `config/attribution_v1_6.yaml` for the complete finite policy.

All 564 v1.5 text residuals receive auditable, nonexclusive A–F signals. These
are candidate explanations, not independently labeled errors. New expressions
cover missing ballistic inflections/targets/trajectories, БРСД and Tu-95 without
variant suffix; approved taxonomy stays fixed. The lead explicitly authorizes
finite operational MiG shorthand as a channel convention under mig31, with
subtype `mig_channel_model_unspecified` and persistent inferred uncertainty.
This never establishes a MiG-31K model. Bare verbs, jokes and negations do not
qualify. Generic UAV remains the broad analytical group, never Shahed model proof.

Exclude only exact known channel-signature / Severshchyna-Poltava promotion /
“🔥 Збір помсти” footer lines from a length-preserving context view. Original
text and source spans remain intact; excluded spans are recorded separately.
A current warning is evaluated independently of later carrier descriptions or
instructional/footer clauses. Current explicit type-only bulletins, Kyiv-local
UAV position/route statements and probable cruise-missile bulletins remain
experimental and uncertain. A suburb name by itself supplies no weapon label.

Retain ten-minute pre-alert lookback, ten-minute anchor age and ordinary
five-minute gap. Require inside correspondence and reject previous-alert/DST
contamination. “Курської” is an origin name, not the word “курс”; confined foreign
anchors need an actual route expression before a bounded Kyiv followup. Current
absence ends reference propagation without erasing earlier accepted observations.
Explicit absence, hypothetical past launches, satirical lists, retrospective
summaries, explanatory posts and explicitly non-threatening aircraft missions
are rejected with original source spans. Report every withdrawn category.

v1.6 classifies 1295/1803 eligible alerts (71.82%): 155 gains, one loss, net +154
against v1.5. 410 text residuals and 98 no-text alerts remain; 790 outside-history
and one DST-unresolved interval remain separate. The global threshold is reached,
but 2026 coverage is 459/689 (66.62%). All 258 added alert/category pairs have
inspectable source evidence; 14 prior category pairs are removed. 101 existing
alerts change categories without gaining/losing overall classification.

Correction support sets overlap. The disjoint lexical → boilerplate → operational
→ existing-context priority counts 69 + 53 + 33 unique gains, totaling 155; this
is an accounting convention, not a causal ablation or an accuracy measurement.
A compact 20-case analyst source check covers risky new acceptances and exclusions;
it supplies no independent human gold labels. Prior review targets stay explicit,
including 1096/2581 discrepancies and provisional 1416/2590. Full residual
exploration in v1.6 is not a blind evaluation of the old diagnostic holdout.

Stop marker development here. v1.6 is the technical analytical candidate pending
research-lead acceptance; handoff explains missingness, overlapping categories,
calendar denominators, partial October and retrospective feature availability.
No time-series inference, forecasting or automatic commit is performed.

## Task005 — implemented retrospective temporal diagnostics

Task005 authorizes v1.6 as the primary experimental dataset, without making its
labels ground truth. ADR026 specifies populations, missingness, calendar unions,
serial-dependence resampling, exploratory comparison families and sensitivities.
Run `python -m kyiv_alerts.temporal_analysis --root .`. Daily official starts use
2593 resolved intervals; all2594 known starts remain in a separate sensitivity.
No future zeros extend past the last observed official end. Daily interval unions
are split at actual Europe/Kyiv midnights in UTC, including23/25-hour days.
508 eligible unknowns remain alongside1295 interpreted alerts. A zero category
flag is a nondetection, not verified absence. Source completeness is unverified.
Calendar-year and season effects are descriptive/exploratory; season and category
screening use explicit Holm families. Moving-block intervals are pointwise,
limited by nonstationarity and block-boundary bias; long-lag ACF intervals are
omitted where inappropriate. No model, future validation or operational advice
is implemented. Report and readiness decision: `reports/temporal_analysis/`.

## Task005.1 — external validation and physical interpretation

ADR027 defines pinned-source matching, mutually exclusive single/multiple/unknown
states and joint day-block opportunity diagnostics. Current municipal export
confirms2594 originals in all fields; it is the same origin, not independent truth.
Kyiv Digital history matches all original start clocks and has194 typed matched
alerts (209 positive causes); primary schemas support restricted exact/partial
context crosswalks, never technical launch/model verification. No absence is
inferred from2400 untyped starts. Positive-source support is not classification
accuracy; no authenticated alerts.in.ua historical sample is obtained.
A dated city statement documents differentiated warnings: Sep7 decision/Sep10
implementation, observed typing starts Sep7.139/190 September rows have yellow
level; excluding observed yellow is a scope sensitivity, not a repaired series,
and older null levels are not imputed red. Forecast validation requires a target
comparable across this procedural transition. Single/multi selection and duration/
publication opportunity confound category-duration physics. Stop after Task005.1.

## Task006 — authorized retrospective weekly forecastability validation

Task006 explicitly approves weekly recorded official starts, all warning colors,
Monday–Monday Europe/Kyiv, one-week horizon. It supersedes the Task005.1 target
prerequisite for this conditional archived-target experiment; yellow alerts remain
real alerts and are never excluded. Procedure changes are possible measurement
regime effects, not an explanation away of observed threat activity.
ADR028 freezes52-week initialization, development through2025, final2026 holdout,
B0–B4 and one L2 Poisson autoregression. Training-only scaling/selection and exact
calendar lags prevent future leakage. Primary no-record weeks remain unknown;
archived-zero sensitivity is explicit. Source publication latency and full internal
completeness remain unverified, limiting live generalization. Dependence-aware
paired error intervals and period sensitivities distinguish forecast skill from
correlation. Outputs and implementation are isolated under forecastability folders.
No individual threat/safe-period prediction or live deployment.
