# Task 004.7 — Residual uncertainty segmentation

**DIAGNOSTIC — HUMAN REVIEW REQUIRED**

Frozen baseline: {"official": 2594, "eligible": 1803, "classified": 1050, "text_unclassified": 655, "no_linked_text": 98, "outside_coverage": 790, "dst_unresolved": 1}.

A–F are diagnostic hypotheses, not validated root causes. Membership overlaps; primary groups partition all 655 text residuals.

| Segment | Overlapping | Primary |
|---|---:|---:|
| A | 215 | 215 |
| B | 284 | 116 |
| C | 194 | 128 |
| D | 81 | 44 |
| E | 80 | 27 |
| F | 180 | 125 |

## Exact diagnostic rules
Primary priority: A,C,D,B,E,F.
- A: At least one rejected in-alert v1.4 lexical_anchor (context references excluded). A rejection is not a confirmed error.
- B: At least one nonempty <=12-token in-alert bulletin, no lexical anchor in that message, no frozen NONOP/RESET/NEGATED match, with a recognized explicit-Kyiv locality or a frozen MOVEMENT_REFERENCE hit. No category is inferred.
- C: At least one diagnostic gap-probe span not overlapped by any recorded in-alert lexical anchor, outside frozen NONOP/RESET/NEGATED messages. Probes name possible wording gaps, not validated threat types.
- D: At least one rejected operational v1.4 pre-alert anchor in [start-10min,start), or an operational frozen-profile lexical readout in [end,end+10min). Boundary proximity does not establish the same event; no post-alert evidence is attributed.
- E: At least half of nonempty linked texts have frozen NONOP/RESET/NEGATED signals or every in-alert lexical anchor in that message is explicitly other-region-confined or negated/history/non-operational. This is a coarse recorded-signal proxy, not a semantic content judgment.
- F: No A/B/C/D signal, or <=2 text messages and no A/C/D signal. Sparse locality-only evidence can overlap B; other residual cases default to F. Insufficiency is a review hypothesis.

Diagnostic lexical probes (not classifier rules): {"gap.reactive_variant": "(?<!\\w)реактив\\w*(?!\\w)", "gap.banderol_variant": "(?<!\\w)бандерол\\w*(?!\\w)", "gap.uav_spelling": "(?<!\\w)(?:бплт\\w*|блп\\w*|бп\\s+ла|бпл)(?!\\w)", "gap.euphemism": "(?<!\\w)(?:мандрівник\\w*|жужик\\w*|мопед\\w*|балалайк\\w*|герань\\w*|герані)(?!\\w)", "gap.unspecified_object": "(?<!\\w)(?:ціл(?:ь|і|ей|лю)|розвідник\\w*|невідом\\w*\\s+об[ʼ’\\x27]?єкт\\w*)(?!\\w)"}

## Source coverage audit
98 no-linked-text cases stay outside A–F. Subtypes: {"no_linked_records": 96, "only_empty_text_records": 2}. The audit retains nearest before/after message IDs and posting gaps; no threat absence is inferred.

## Controlled selection
Seed 20261011. Exclude all 25 Task0045 sample alerts from both new samples and the five discussed cases. Within each primary group: lexicographically sorted IDs, seeded per-year shuffle, cycle available years in ascending order; within each next year greedily prefer unseen recorded rejection/probe/geography/boundary/volume signals, seeded order resolves ties. Requested A8/B8/C8/D6/E5/F5. If short: report shortfall, fill from unused eligible cases with the same year-balanced method, retain actual primary and fallback flag.
Quota audit: [{"segment": "A", "requested": 8, "available": 214, "selected": 8, "shortfall": 0}, {"segment": "B", "requested": 8, "available": 115, "selected": 8, "shortfall": 0}, {"segment": "C", "requested": 8, "available": 127, "selected": 8, "shortfall": 0}, {"segment": "D", "requested": 6, "available": 43, "selected": 6, "shortfall": 0}, {"segment": "E", "requested": 5, "available": 27, "selected": 5, "shortfall": 0}, {"segment": "F", "requested": 5, "available": 125, "selected": 5, "shortfall": 0}]
Safety sample: newly classified only; seeded tie order, greedy unseen priority-risk flags, then fewer selected in year, then number of flags. Risks are not proof of false positives. All selectors are purposive; no accuracy estimation.

A: 833, 1312, 1500, 2589, 806, 1096, 1416, 2230
B: 830, 1356, 1613, 2592, 866, 1308, 1842, 2457
C: 861, 1107, 1649, 2537, 839, 997, 1433, 1954
D: 876, 1286, 1662, 2124, 953, 1810
E: 881, 1051, 1597, 2098, 813
F: 824, 1158, 1573, 2352, 820
Safety: 2483, 1991, 1612, 1204, 878, 1731, 931, 855, 2472, 1663

## Evidence completeness
50 unique alerts; 749 complete linked in-alert messages, including 657 with no lexical anchors; 54 pre-alert messages; 35 post-alert diagnostic-only messages. Candidate occurrences: 219. All human fields blank.
All chronology rows preserve original text/title/ID/file/index. Half-open links are Task003 links, not recomputed assignments. Pre-alert and post-alert windows each retrieve every available timed record for ten minutes. Post-alert lexical readouts reuse the frozen profile, are explicitly unaccepted, and are only diagnostic boundary checks. Cross-message records cite original anchors and their unmodified texts. Never infer continuity across unrelated messages.

## Limitations
Recorded-signal E is not a semantic majority judgment. Place-only B cannot establish weapon type. C probes may be benign, unrelated, or already understood semantically; absence of a hit is not a dictionary error. D proximity can concern a different episode or deliberate safe rejection. Primary priority affects counts and sampling. Missing media/OCR, one-channel coverage, untimed/DST-ambiguous records and unrecorded legacy context/geography regex IDs limit explanation. v1.4 uncertainty remains explicit. October official starts stop Oct4; Telegram extends Oct10. No classifier or approved interpretation is changed.

## Validation
Validation: {"complete_source_chronology": true, "correct_links_and_local_times": true, "all_human_fields_blank": true, "source_and_classifier_hashes_unchanged": true, "unique_samples": true, "no_text_separate": true}. Protected data/config/classifier/prior-report hashes verified unchanged. Tests and reproducibility checks are recorded separately in validation_results.json.
Excel cell representation adjustments: 0; full details in JSON, exact texts in CSV.

## Reproduction
`python -m kyiv_alerts.residual_review --root .`

Outputs: residual_segment_summary.md/.json; residual_alert_segments.csv; residual_review_50.xlsx; residual_review_alerts.csv; residual_full_timeline.csv; residual_pre_alert_evidence.csv; false_positive_review_sample.csv. Supplements: no_linked_text_source_audit.csv, residual_post_alert_context.csv, residual_human_review.csv.

Stop for dialogue-based human validation. v1.5, time-series analysis and forecasting are not implemented.
