# Data dictionary

Task 002 implements the ingestion schemas described below. The earlier conceptual tables remain useful logical design references; Task 003 now implements links and descriptive coverage; Task 004 implements provisional contextual features; later analytical features remain unimplemented. Original values are retained alongside normalized representations.

## alerts — one official interval per record
| Field | Proposed type | Meaning / constraint |
| --- | --- | --- |
| alert_id | string | Stable source-scoped identifier; validate source uid uniqueness. |
| start_time | timezone-aware datetime | Normalized start with original string retained in provenance. |
| end_time | nullable timezone-aware datetime | End; missing values indicate an unresolved/open interval, not zero duration. |
| duration_minutes | nullable float | Derived elapsed duration; undefined for unresolved/invalid intervals. |
| source | string | Kyiv Digital source identifier. |
| source_cause | nullable string | Preserved reported cause; not independently verified weapon classification. |

## messages — one exported message per record
| Field | Proposed type | Meaning / constraint |
| --- | --- | --- |
| message_id | string | Source/channel-scoped identifier; uniqueness requires validation. |
| message_time | timezone-aware datetime | Parsed timestamp preserving original representation. |
| text | nullable string | Extracted message content; service/empty messages remain distinguishable. |
| source_file | string | Relative export member path for traceability. |
| message_type | nullable string | Provisional content/service classification, to be defined after inventory. |

## alert_message_links — separate temporal relationships
| Field | Proposed type | Meaning / constraint |
| --- | --- | --- |
| alert_id | string | Foreign key to alerts. |
| message_id | string | Foreign key to messages. |
| match_method | string | Versioned linking convention, including boundary handling. |
| match_quality | string or enum | Transparent rule-based quality designation; vocabulary pending approval. |

Validate foreign keys and duplicate pairs. Overlapping intervals may allow multiple links; resolve policy before implementation. A temporal link does not establish that a message concerns a Kyiv-directed threat. Never flatten the complete Telegram history into alert records.

## Future derived fields and provenance
Potential fields include local date/hour/weekday, daily/weekly count and duration aggregates, rolling summaries, multi-label markers, supporting message IDs, coverage status, dictionary version, source hash, transformation version, and feature availability time. These are proposals, not approved forecasting features. Count/duration bin semantics, DST behavior, overlap handling, aggregation target, and horizon require decisions.

Missingness needs explicit states for unavailable coverage, insufficient reporting, unknown interpretation, and no detected mention. Confirmed absence requires independent justified evidence. All feature definitions must identify units, source records, observation time, availability time, and transformation rules. Raw/source timestamp strings must remain recoverable through provenance.


## Task 002 implemented Parquet schemas

All string fields are nullable UTF-8; normalized timestamps are nullable `timestamp[us, UTC]`. Ordering preserves JSON source order for alerts and deterministic natural filename/page and DOM order for messages. No volatile execution timestamps occur in normalized rows.

### alerts.parquet
| Column(s) | Type / semantics |
| --- | --- |
| alert_id, source_uid | Source uid as string; missing remains null, never a fabricated identifier. |
| source_region_code | CATUTTC; expected Kyiv code UA80000000000093317 is a diagnostic, not a filter. |
| source_region_name | addressPostName, without geography inference. |
| alert_type, source_cause | type/cause; native null and literal null normalize to missing. |
| start_time_original, end_time_original | Original timestamp values; malformed non-string values serialize as JSON for traceability. |
| start_time, end_time | UTC values; missing/invalid/DST unresolved values remain null. |
| duration_minutes | Nullable float64 elapsed UTC minutes, only when end is later than start. |
| validation_status | valid or semicolon-separated issues; flagged records retained. |
| start_timestamp_status, end_timestamp_status | valid, valid_explicit_offset, valid_kyiv_wall_clock (Telegram H2), missing, invalid, ambiguous, or nonexistent. |
| source_file, source_record_index | Filename and zero-based JSON array position, including invalid items. |
| raw_record_json | Entire original record/item as sorted-key JSON; preserves additional fields and original null sentinels. |

Duplicate IDs, duplicate intervals and overlaps are audit-level findings; they do not automatically remove rows or replace source identifiers. Pair this provenance with the input hash inventory.

### telegram_messages.parquet
| Column(s) | Type / semantics |
| --- | --- |
| message_id | Extracted nonnegative source message ID string; null when unavailable or an export heading. |
| message_time_original, message_time | Original date title and nullable normalized UTC timestamp. |
| text | Readable text with entities decoded and explicit line breaks preserved; no keyword filtering. |
| message_type | message or service based on HTML class, not threat classification. |
| source_file, source_message_index | Archive HTML member and zero-based message-element position in that member. |
| source_html_id | Original HTML id, including negative export headings or unrecognized IDs. |
| has_text, is_service_message | Non-null booleans. |
| forwarded_from, reply_to_message_id | Nullable recognized metadata; absence is unknown. |
| edited_at | Nullable raw edit-title string, not an inferred UTC timestamp. |
| parse_status, timestamp_status | Semicolon-separated row issues and explicit timestamp parse status. |

The real Telegram schema was validated on the supplied 56-file HTML archive: 55,739 ordinary messages and 1,252 service records were retained. Under the Task 002.1 H2 rule, 55,731 ordinary clocks resolve to UTC and eight are DST-ambiguous; original fixed-+02:00 titles are retained; exact timestamps remain null for all service records. Of those service records, 1,205 export headings have no genuine message ID, while 47 service events have source IDs. No duplicate genuine IDs were observed. Repeated genuine IDs are retained once; duplicate occurrences, source positions, content conflicts, and duplicate normalized evidence are preserved in the JSON audit. Missing IDs remain separate traceable records. Negative service-heading identifiers are not genuine Telegram IDs. No alert/message mapping, markers, or statistical features are produced in Task 002.


## Task 003 implemented temporal datasets

### alert_message_links.parquet
One row per unique `(alert_id, message_id)` pair satisfying `alert_start_time <= message_time < alert_end_time`. Required UTF-8 fields are `alert_id`, `message_id`, `match_method`, `match_quality`, `source_file`; `source_message_index` is int64. `message_time`, `alert_start_time`, `alert_end_time` are timestamp[us, UTC]. `match_method` is always `within_official_interval`. Quality is `deterministic` for one resolved interval, or `review_overlapping_intervals` when more than one resolved interval contains the message. No threat category, geographic relevance score or message text is flattened into these links. Source message text/availability remains in messages, recoverable by ID and file/index.

### alert_coverage.parquet
One row per unique official alert, including alerts before Telegram's date range and the unresolved interval. `alert_id`, `start_time`, `end_time`, and `duration_minutes` retain source values/types. `telegram_message_count` and `telegram_text_message_count` are nullable int64. `has_telegram_coverage` is nullable boolean. `coverage_status` and `historical_range_relation` are UTF-8. Additional `deterministic_message_count` and `deterministic_text_message_count` provide non-null lower bounds that reconcile to generated links.

| coverage_status | Meaning and null policy |
| --- | --- |
| covered | At least one accepted temporal link; count/text count reflect generated links, not relevant threats. |
| no_messages_found | Fully historically contained, resolved interval with zero matching messages; counts 0 and coverage false. |
| no_telegram_historical_coverage | Interval is outside recorded Telegram range (or no observed range exists); count/text count and coverage are null, never false absence. |
| unresolved_temporal_ambiguity | Interval/end or a potentially intersecting message is unresolved; complete counts are null, coverage is true only if other accepted links exist, otherwise null. |
| partial_historical_coverage | Boundary-straddling interval without links in its observed portion; coverage remains unknown. No such rows occurred in the actual Task 003 run. Partial intervals with links are covered but retain `historical_range_relation=partial`. |

`historical_range_relation` is within/outside/partial/unknown. For unresolved endpoints, candidate envelopes may establish range containment, never a replacement normalized endpoint. Rate eligibility requires full containment and resolved count status; partial, unknown and unresolved cases are excluded. All valid timestamped records can match, even empty text or timestamped service records; untimed service events and ambiguous messages are excluded and reported. Missing genuine message IDs are never invented.

Recorded availability runs from first to last resolved Telegram timestamp; this is not proof of continuous reporting. Monthly grouping uses the official start's Europe/Kyiv calendar month. Coverage rate is covered / fully range-contained resolved eligible alerts. The eligible-alert median includes genuine zeros; the covered-alert median excludes zero-message intervals. Months without eligible alerts have null rates/medians. Candidate-fold evidence and all excluded source references are in `reports/temporal_linking/coverage_report.json`.

## Task 004 implemented classification schemas — v1.0

Classification describes **reported threat-context markers**, not confirmed weapon launches, interceptions or attacks. Outputs are provisional pending human validation. No ingestion or Task 003 table is rewritten.

### message_threat_markers.parquet

One row per dictionary occurrence per existing alert/message pair, including excluded candidates. A message can have multiple rows and, if officially overlapping intervals exist, multiple alert references. No marker rows are manufactured for empty text or absent keywords. All linked records are nevertheless processed and counted in the report.

| Column | Type / semantics |
| --- | --- |
| message_id, alert_id | UTF-8 foreign keys to source message, official alert and Task 003 pair. |
| category, subtype | v1.0 category and explicit lexical subtype; generic UAV is `other:generic_uav`, not an inferred Shahed model. |
| matched_text | Exact original substring, including original case and punctuation. |
| match_start, match_end | int64 Python Unicode-character offsets `[start,end)` into original message text, not byte positions. |
| rule_id, dictionary_version | Stable dictionary rule ID and `v1.0`; dictionary SHA-256 is recorded in the run report. |
| evidence_context | Original clause containing the match; sentence, newline and semicolon boundaries. |
| evidence_status | current_threat / explicit_alert_cause / historical_or_summary / negated_or_cancelled / uncertain. Textual attribution does not establish actual cause. |
| geography | explicit_kyiv / kyiv_region / other_region / nationwide / unspecified / uncertain; describes text, not independently geolocated threats. |
| accepted_for_aggregation | boolean; requires accepted context, explicit-city/nationwide geography and no dictionary/specificity exclusion. |
| exclusion_reason | Nullable UTF-8 semicolon-separated non-exclusive reasons. Suppressed overlaps and specific-family generic words remain reviewable. |
| source_file, source_message_index | Original HTML member and int64 DOM position, checked against the linked message. |

### alert_threat_features.parquet

Exactly one row for every official alert, including pre-export and unresolved records. `alert_id`, `start_time`, `end_time`, `duration_minutes` retain official source values. Timestamps are `timestamp[us, UTC]`, duration float64. `coverage_status`, `historical_range_relation`, and nullable int64 Telegram message/text counts retain Task 003 semantics.

| Column(s) | Type / semantics |
| --- | --- |
| shahed_uav, jet_uav, ballistic_high_speed, cruise_missile, mig31, strategic_aviation, other | Nullable booleans. True = accepted marker detected; false = not detected in available linked text, **not absence of danger**; null = no appropriate text observation, unavailable history, partial-unobserved interval or unresolved time. |
| unknown | Non-null boolean analytical state: no accepted category or observation unavailable. It does not mean a detected unknown weapon. |
| threat_combination | Nullable UTF-8. Fixed dictionary category order; e.g. shahed_uav+ballistic_high_speed. Available text without accepted categories uses `unknown`; unavailable evidence uses null. |
| explicit_cause_categories | Nullable list of UTF-8 accepted textual cause categories in fixed order; available evidence without explicit cause uses []; unavailable evidence uses null. |
| marker_evidence_count | Nullable int64 accepted candidate-occurrence count, not unique weapons or attacks. Unknown observation = null, observed no marker = 0. |
| candidate_marker_count | Non-null int64 count of all auditable candidates generated from accepted temporal links; a lower bound for incomplete coverage, not a claim of complete observation. |
| classification_status | classified / multiple_categories / no_identifiable_marker / no_telegram_historical_coverage / no_linked_text / unresolved_temporal_ambiguity / partial_historical_coverage. Existing coverage_status still distinguishes no messages from messages with empty text. |
| dictionary_version | UTF-8 v1.0. |

An unresolved interval has null detection fields even if other deterministic lower-bound links could exist in synthetic inputs. A partially observed interval with known text can show positive detections while retaining historical_range_relation=partial; it is excluded from primary monthly denominators. Overlap links are retained from Task 003; counts are per alert, not mutually exclusive weapon totals.

### Human review CSV

`reports/classification/validation_sample.csv` is UTF-8 with BOM for spreadsheet compatibility. Each row is a unique alert/message pair. Original text/timestamp, message time/ID, alert ID, all detected markers (JSON), rule IDs, predicted context/geography, source file/index, dictionary version and overlapping strata are supplied. Reviewer categories/context/geography/Kyiv relevance/notes remain blank. Predictions are never human labels. The fixed seed is 20261010; default size is 180. Include no-marker/empty-text examples to support false-negative discovery.

## Task 004.1 geographic extension — classification v1.1-geo

Threat taxonomy/rules remain v1.0. `config/kyiv_geography.yaml` separately versions a finite dictionary as `kyiv-geography-v1.0`. Its 82 entries cover ten administrative districts, selected neighborhoods/landmarks, colloquial aliases, nearby settlements and a few oblast cities/areas; it is not a complete gazetteer. Kyiv and Kyiv Oblast are separate entries. Unqualified common/shared names carry `requires_kyiv_anchor=true`.

Both marker and feature tables add `classification_version` (v1.1-geo with geography enabled; v1.0 otherwise) and nullable `geography_dictionary_version`. The run report hashes both dictionaries. Taxonomy `dictionary_version` remains v1.0 and must not be mistaken for the full transformation version.

Markers additionally include:

| Field | Type / semantics |
| --- | --- |
| geography_mentions | List of structs containing locality_id, canonical_name, locality_type, category, matched_text, rule_id, resolution_status (strings); match_start/match_end (int64 source-character offsets); requires_kyiv_anchor (boolean). Original found name is preserved exactly. Empty list means no additional locality-dictionary match, not absence of a place. |
| geography_source | clause / message_fallback, explicitly identifying inherited rather than clause-local geography. |

The outer `geography` remains the existing generalized vocabulary. City-locality candidates use explicit_kyiv; suburbs/oblast entries use kyiv_region. A generic/shared name without a trusted city anchor uses uncertain and resolution_status=needs_kyiv_anchor. Otherwise a lexical match is **provisional_lexical_match**, never a human-approved label. Mixed geographic categories remain uncertain. `locality_type` distinguishes suburb from more distant oblast_city/region_area; all use kyiv_region for aggregation exclusion. Longest overlapping locality spans take precedence so qualified oblast Borshchahivka names cannot be flattened into the city alias.

Frozen Task 004 output/report files remain in their original paths. New tables are in `data/processed/classification_v1_1/`, and new reports in `reports/classification_v1_1/`. The comparison outputs `geography_changes.csv` (all changed/newly informative candidate rows) and `geography_review_sample.csv` (180 unique alert/message examples). Review fields remain blank. Flattened matched/canonical names, generalized before/after geography and context are included alongside full change evidence JSON and original text. Direct marker spans remain reversible even when locality evidence is inherited from another sentence.

## User-approved contextual rules — v1.2-reviewed-rules

Paired configs are `threat_dictionary_v1_1.yaml` (dictionary v1.1; unchanged category IDs/order) and `kyiv_geography_v1_1.yaml` (kyiv-geography-v1.1, user-confirmed center alias). Original configs remain unchanged. Markers add:

| Column | Semantics |
| --- | --- |
| context_status_original | Initial clause context before user-approved promotion; preserves default uncertainty. |
| context_rule_id | Nullable identifier for short-bulletin/target/probable-warning interpretation. |
| relevant_to_kyiv | Boolean evidence-level contextual relevance by a recorded rule; not independent weapon geolocation and not proof of a threat's absence when false. |
| relevance_rule_id | text_geography or a user-approved target/city-cause/Kinzhal-warning rule. |
| uncertainty_flag | Boolean; probable warnings retain true even when accepted. A user-approved unqualified short bulletin may become current with false while still retaining its original status and overall provisional validation status. |
| evidence_qualifiers | List of normalized probability terms detected in the clause; original text remains preserved. |

`geography` continues to describe the text separately from relevance: mixed and unspecified geography can be accepted only by specific authorized rules. No source location/name/time is fabricated. `evidence_status=uncertain` can be accepted for approved probable operational warnings; it does not populate explicit_cause_categories. New marker subtypes include shakh_shorthand, reactive_shorthand_user_inferred and cruise_shorthand. Explicit jet subtypes remain distinct. Generic UAV observations do not automatically become Shahed.

New outputs and reports use `data/processed/classification_v1_2/` and `reports/classification_v1_2/`. `reviewed_rule_changes.csv` records existing changes plus new lexical occurrences; `reviewed_rule_sample.csv` has unique changed alert/message pairs, original text, trace rules and blank reviewer fields. Independent reference labels/quality metrics remain unavailable.

## Task 004.2 diagnostic reports (read-only classification baseline)

`reports/pattern_discovery/` stores UTF-8-BOM CSV review tables plus Markdown/JSON
reports. Nested arrays/maps are JSON cell values; original multiline source text
is quoted as ordinary CSV. Review decisions/notes/status remain blank.

- `candidate_patterns.csv`: diagnostic family ID/type, phrases, distinct B/C
  alert/message supports, separate C/B supports, first/last evidence time,
  period/month supports, existing dictionary evidence, exclusions, complete
  representative source messages and proposed review action. Supports overlap.
- `october_2026_alert_review.csv`: one row for **every** October official alert,
  including no-text rows; original interval/classification/status, linked-text
  and candidate counts, reasons, family IDs, full representative messages.
- `october_2026_messages.csv`: every linked October message in alert/time order,
  original time/text/file/index, dictionary hits/exclusions, diagnostic IDs;
  empty linked messages retained if present. No neighboring-message inference.
- `period_comparison.csv`: six requested periods; eligibility/text denominators,
  A/B/C/D counts, reporting density, distinctive n-grams, newly prominent families,
  short/place-only format indicators and explicit partial-period/source bounds.
- `representative_examples.csv`: 3–5 original source examples per supported
  family when available, alert/message IDs, time, current classification,
  candidate evidence/exclusions, source provenance and context-review flags.
- `word_ngram_frequency.csv`, `character_ngram_frequency.csv`: alert/message
  supports, A comparison, prevalence ratios, temporal distribution and examples.
- `similarity_groups.csv`, `similarity_assignments.csv`: exploratory TF-IDF
  groups and alert/message-to-group mappings with assigned-centroid cosine.
  Cluster IDs are not semantic labels.
- `pattern_assignments.csv`: diagnostic family-to-existing-link pairs only.
  No accepted-marker or alert-classification field is generated or changed.

The report records SHA-256 for every input and retained source/classification
artifact, current versions, software, deterministic seed and elapsed time.
Precision/recall are null without independent human reference labels.

## Task 004.3 versioned schemas — classification_v1_3

The original official interval/coverage columns and evidence source spans remain
unchanged. Dictionary and classification version are v1.3; geography remains
kyiv-geography-v1.1. Category semantics version is v1.3-broad-uav.

`shahed_uav` now denotes the broader qualified UAV analytical group, including
generic_uav evidence. It does **not** identify a Shahed model for generic wording.
`jet_uav` includes explicit jet-UAV/model references and channel-inferred reactive
shorthand. Historical versions retain their previous category meanings.

Message evidence adds `uav_evidence_type` (nullable UTF-8: generic_uav,
shahed_explicit, attack_uav_explicit, jet_uav_explicit,
reactive_shorthand_inferred) and `inferred_shorthand` (boolean). Inferred reactive
shorthand always has uncertainty_flag=true; explicit references can still have
textual probability qualifiers with inferred_shorthand=false. Existing lexical
subtypes, matched_text, rule_id and literal geography are retained. Rule ID
prefixes may reflect the original category for traceable migrated occurrences.

Alert feature additions:

| Field | Semantics |
| --- | --- |
| classification_status | single_type / multiple_types / only_other / no_marker_with_text / no_linked_text / outside_telegram_coverage / unresolved. Specific group count excludes other. |
| legacy_classification_status | Previous aggregation status vocabulary retained for this run's original coverage/combination interpretation. |
| unique_threat_category_count | Nullable int64 count of distinct accepted categories including other; zero for observed no-marker text, null for unavailable observations. |
| specific_threat_category_count | Nullable int64 distinct categories excluding other; broad UAV is an analytical group, not verified model identification. |
| first_accepted_evidence_message_id | Nullable UTF-8 earliest accepted source message by timestamp/file/index/ID. |
| supporting_message_ids | Nullable chronological unique ID list; [] for observed text with no accepted marker, null for unavailable observations. |
| supporting_message_count | Nullable int64 length of the unique global support list, separate from marker_evidence_count. |
| category_message_support | Nullable ordered list of structs: category, first_message_id, message_ids, supporting_message_count, supporting_marker_count, uncertain_marker_count. |
| category_semantics_version | v1.3-broad-uav. |

Cause/context alert subsets overlap; marker occurrences and message counts are
not event counts. `explicit_cause_categories` retains textual cause attribution.
A specific category plus other has state single_type and unique count two;
two specific categories have multiple_types regardless of the other flag.

Reports under reports/classification_v1_3 include Markdown/JSON coverage audit,
all-alert version comparison, exact marker transitions, month/year CSVs and a
28-alert stratified no-marker review with blank human fields. Nested CSV evidence
is JSON; complete source text/time/file/index remain traceable. Reports retain
input hashes, independently reviewed sample count zero and null precision/recall.

## Task 004.4 — attribution_experiment_v1

`inside_interval_candidates.parquet`: one lexical occurrence per alert/source/rule,
including rejected and ambiguous evidence. `pre_alert_candidates.parquet`: one
lexical occurrence per target alert/source/rule, with an array of applicable
lookback windows; never duplicated once per window.

Both retain alert_id, category, anchor_message_id, chronological source_message_ids,
full evidence_text, source_timestamps_original, normalized source_message_times,
source_files/indices, evidence_level, time_relation, minutes_before_alert (null
inside intervals), literal anchor geography, relevant_to_kyiv (anchor relevance),
review status, original exclusions, dictionary version, subtype and UAV evidence
semantics. Contextual Kyiv relevance is established by the cited following source;
anchor geography is not rewritten. Human decision/notes remain null.

Pre-alert fields add previous_alert_ids, intervening_boundary_alert_ids,
unresolved_envelope_alert_ids, contamination_flag, candidate_windows,
baseline_stratum and complete_history_windows. lookback_history_complete describes
the maximum 60-minute window relative to observed export bounds, not continuous
reporting. Ambiguous timestamps are never assigned a fold.

`progressive_alert_coverage.parquet`: one row per original official alert. Every
v1.3 field is copied unchanged; baseline_accepted, inside_provisional_categories,
inside_new_candidate, and pre_N_candidate_categories are separate experimental
annotations. Null means unevaluated/unavailable; an empty list means evaluated
without a supported candidate, not confirmed absence. New categories are never
written into the v1.3 boolean columns. Experimental status always remains
PROVISIONAL — HUMAN VALIDATION REQUIRED. CSV nested fields are JSON arrays/objects.

## Task 004.5 — Controlled diagnostic outputs

`reports/controlled_review/controlled_alert_review.xlsx` uses six sheets:
README, Alert Overview (one selected official alert per row), Full Message
Timeline (one original alert/message link), Classification Trace (one recorded
v1.3 candidate occurrence), Diagnostic Summary, and Pre-Alert Evidence
(supplementary Task0044 records, clearly outside the official interval).

`classification_error_trace.csv` retains candidate identity/spans, original text,
matched expression, lexical rule/category/subtype, literal geography and locality
rule IDs, recorded approved context/relevance override IDs, original/final context,
all exclusion strings, accepted/rejected outcome, uncertainty/qualifiers/UAV
semantics, source IDs/file/index/timestamps, dictionary versions, and matching
provisional Task0044 records. `lexical_match_status=matched` refers to actual
recorded occurrences; no-hit messages remain in `full_message_timeline.csv`.

`geography_rule` and `context_rule` are structured JSON: existing recorded locality
or approved override IDs plus `not_recorded` for missing legacy regex pattern IDs.
Null override IDs mean no recorded override. Exact overlap/family suppressor
identities were not persisted. Task0044 associations lack occurrence spans;
matching is only at alert/anchor/rule/category/subtype level, explicitly flagged.
All Task0044 evidence retains its provisional review status.

Supplementary `selected_alert_overview.csv` and `pre_alert_evidence.csv` support
complete audit/reuse. Nested arrays/objects are JSON inside UTF-8-BOM CSV; source
text, including multiline or empty content, is not truncated. Excel source strings
are literal text, never formulas. Excel dates are Kyiv-local naive values because
Excel does not support timezone-aware dates; original strings and normalized CSV
instants remain unchanged. Excel cell-limit/XML representation adjustments, if
any, are listed in JSON and full text remains in companion CSV.

`controlled_review_summary.md/.json` retain actual baseline and selection strata,
IDs, message/candidate totals, overlapping recorded exclusion/signal counts,
missing instrumentation, protected SHA-256 hashes, software versions, seed and
runtime. Human decisions/category/root cause/notes are initially blank. Proposed
diagnostic groups are review questions, not verified causes. Status is always
DIAGNOSTIC SAMPLE — HUMAN REVIEW REQUIRED; precision/recall remain null.

## Task 004.6 — classification_v1_4

Both Parquet datasets retain official/source IDs and metadata. Classification and
composed lexical dictionary version are v1.4; source_dictionary_version is v1.3,
geography remains kyiv-geography-v1.1, category semantics v1.3-broad-uav. The
composed profile consists of the frozen v1.3 rules plus the separately recorded
user-confirmed jet-UAV banderol alias. `lexical_rule_source` distinguishes the
frozen dictionary from this approved extension. No model subtype is inferred.

Marker fields extend v1.3 with source_classification_version/attribution_version,
experiment_status, source_message_time/source_timestamp_original/original_text,
anchor_message_id/anchor_rule_id/anchor_match_start/end, evidence_role
(lexical_anchor or context_reference), time_relation (inside_interval or
before_alert), minutes_before_alert, baseline_accepted/exclusion/context,
operational_status/rule_id, attribution_strength/rule_ids, correction_causes,
uncertainty_reasons, support_message_ids, previous/intervening/unresolved alert
IDs, context_geography and geographic_uncertainty. New experimental accepted
associations always retain uncertainty. Human decisions remain null.

Lexical anchors preserve exact matched spans. Context references have null
matched_text/match_start/end and `rule_id=attribution.context_reference`: their
category comes only from a cited explicit lexical anchor, not from locality alone.
Anchor spans identify that lexical source, while the message_id/source/time/text
identify the actual followup. Original anchor geography is not rewritten. Pre-alert
anchors remain before_alert even when cited by inside-interval followups. Recorded
support includes all cited source IDs, including corroboration of a pre-alert
anchor. Missingness and source coverage are not retroactively corrected.

Alert fields retain official intervals and Telegram coverage while recording
baseline_classification_status/categories, new deduplicated flags/status/support,
evidence_strengths, correction_causes, uncertainty_marker_count and
has_pre_alert_evidence. Explicit cause categories require inside-interval lexical
cause evidence, not an inherited contextual or pre-alert cause. Unknown/no-text /
outside-history/unresolved states remain distinct.

Comparison JSON/CSV include exact new/lost IDs, category changes, month/year rates,
overlapping rule support and rule-disabled ablations, uncertainty/evidence strength,
source-backed reviewed-case checks and protected hashes. Case 2581 remains a
research-lead-approved unresolved label discrepancy; 2590 remains a working
hypothesis. Status: EXPERIMENTAL — HUMAN VALIDATION REQUIRED.

v1.4 references retain their own time_relation and minutes_before_alert; an
inside-interval reference to an earlier anchor remains inside_interval.
anchor_time_relation and anchor_geography separately retain the anchor's relation /
literal geography. Reference locality mentions preserve exact source-relative
spans. The review sample includes anchor and reference examples plus a user-alias
case, with full supporting_evidence_text for all cited support_message_ids.

## Task0049 — isolated classification_v1_6

Preserve the v1.5 source/coverage schema, categories and nullable missingness.
Classification/dictionary/attribution version becomes v1.6; source version v1.5.
`v15_accepted` and `v15_exclusion_reason` record the preceding lexical occurrence.
`v16_correction_causes` records applied candidate transformations, not causal gain
estimates. `context_view_excluded_spans` is a list of original-text/source-offset
structs describing exact known boilerplate excluded only from context.

New subtype `mig_channel_model_unspecified` denotes the lead-approved conditional
channel convention, with inferred_shorthand=true and uncertainty_flag=true; no
specific model is established. Tu-95 variants and generic UAV models likewise
remain unspecified unless literally present in source. Accepted category counts
are unique alert/category sets; repeated references never count additional weapons.

`residual_diagnostics.csv` has all 564 original v1.5 text residuals, nonexclusive
A–F flags, source IDs/complete lexical-gap messages, old rejection counts, new
support, outcomes and remaining causes. Flags are diagnostic signals, not human
error labels. `remaining_unknown_with_text.csv` separately contains all 410 final
text residuals. `category_changes_evidence.csv` preserves complete sources and
supporting-message provenance for newly accepted/modified alert categories.
`exception_audit.csv` contains 20 compact analyst source checks and complete
candidate traces, explicitly not research-lead gold labels.

## Task005 — temporal_analysis datasets

`alert_analysis_fact.parquet`:2594 unique source IDs; original timestamp strings,
UTC and Europe/Kyiv timestamps, nullable duration/end, start date/year/month/
quarter/ISO week, valid_interval, source_coverage_status, eligible, classification
status, unknown, markers, marker_evidence_strength, versionv1.6, message counts,
and the unchanged seven nullable detected-category flags. No original is replaced.

`daily_alert_metrics.parquet`: one date inside the official observed span;
resolved official starts, all-record starts, interval-union minutes (lower bound
on unresolved_interval_day), actual calendar_day_minutes, source_boundary_day,
Telegram full-day span flag, eligible/interpreted/unknown counts, unknown text/
no-text/outside breakdown, unique overlapping category counts, coverage_rate=
interpreted/eligible (null with no eligible starts). Before Telegram, category
counts are null, never zero. A within-span zero means no detected alert/category,
not verified no threat. Unknown_total_count also includes source-unavailable states.

`monthly_alert_metrics.parquet`: observed calendar-day count, partial/source-boundary
flags, resolved/all starts, starts per observed calendar day (not exact exposure
rate on partial boundary days), union minutes, eligible/classified/unknown counts,
classification yield, message medians/means, duration median by start month,
Telegram-full-month flag. Full-month span does not guarantee continuous publication.
`threat_category_monthly.parquet`: month/category unique alert count, eligible and
classified denominators, both shares, unknown rate, partial/coverage flags,
category duration median. Categories overlap; count/share null without eligible
observations. Duration statistics group by start month; union minutes by calendar
occupancy day, so those monthly metrics intentionally answer different questions.
CSV reports retain counted101 combination transitions and vocabulary/year
unique alert support. Context references without matched text are tagged and
are not new lexical vocabulary. temporal_summary.json records source hashes,
seed/software, DST-fold sensitivity, population reconciliation and readiness.
