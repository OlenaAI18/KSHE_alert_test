# Task 004.6 — Context-aware attribution v1.4

**EXPERIMENTAL — HUMAN VALIDATION REQUIRED**
Technical run: TECHNICALLY_COMPLETE_WITH_REVIEW_DISCREPANCY. Independent population accuracy is not established.

## Frozen baseline and full-dataset reconciliation
Official alerts 2594; eligible 1803; linked text 1705. Accepted v1.3 alerts 437 → experimental v1.4 1050. New unique alerts 613; lost 0. Baseline accepted categories and occurrences are retained. Classification yield is lexical/attribution coverage, not precision or recall.
Eligible yield: 24.24% → 58.24%; eligible-with-text: 25.63% → 61.58%.
Single category: 392 → 826; unknown including unavailable: 2157 → 1544.
States: {"single_type": 836, "multiple_types": 204, "only_other": 10, "no_marker_with_text": 655, "no_linked_text": 98, "outside_telegram_coverage": 790, "unresolved": 1}
Multi-label (including other): 45 → 224; multiple-specific: 39 → 204; other-only 5 → 10.

## Approved changes and explicit uncertainty
Within official Kyiv intervals, explicit current operational markers can contribute experimentally despite unspecified/nearby geography or legacy uncertain context. Literal geography and original exclusions remain separate. Negation/history, unrelated regional confinement, jokes, donations and explanatory articles do not create new accepted markers. No temporal association independently verifies direction or model.
Short explicit anchors define episodes with at most ten minutes anchor age and five minutes between consecutive messages. Resets and competing anchors stop propagation. Multiple types make elliptical references ambiguous. Geography alone never creates a category. Pre-alert retrieval is [start-10 minutes, start), excludes previous membership/intervening boundaries/unresolved envelopes; weak pre-alert anchors need coherent inside-interval followups before acceptance. Context and pre-alert evidence are not alert causes.
The frozen v1.3 lexical engine is reused, with one user-confirmed alias extension: бандероль → jet_uav. No specific model inference. Existing overlap/family suppression remains active. Profile v1.4 is explicit about its v1.3 base and authorized alias. All new accepted associations retain uncertainty and reasons.

## Categories
| Category | v1.3 | v1.4 | Delta |
|---|---:|---:|---:|
| shahed_uav | 233 | 596 | 363 |
| jet_uav | 12 | 130 | 118 |
| ballistic_high_speed | 52 | 273 | 221 |
| cruise_missile | 18 | 89 | 71 |
| mig31 | 163 | 173 | 10 |
| strategic_aviation | 3 | 60 | 57 |
| other | 18 | 67 | 49 |

## Correction contributions
Overlapping causes: [{"correction": "geography", "newly_classified_unique_alerts": 593, "all_supported_unique_alerts": 801, "accepted_marker_records": 4102, "overlapping_with_other_corrections": true, "unique_alerts_lost_when_disabled": 570}, {"correction": "context", "newly_classified_unique_alerts": 377, "all_supported_unique_alerts": 549, "accepted_marker_records": 3134, "overlapping_with_other_corrections": true, "unique_alerts_lost_when_disabled": 288}, {"correction": "cross_message", "newly_classified_unique_alerts": 307, "all_supported_unique_alerts": 505, "accepted_marker_records": 2914, "overlapping_with_other_corrections": true, "unique_alerts_lost_when_disabled": 38}, {"correction": "pre_alert", "newly_classified_unique_alerts": 77, "all_supported_unique_alerts": 96, "accepted_marker_records": 368, "overlapping_with_other_corrections": true, "unique_alerts_lost_when_disabled": 47}]
Do not add these nonexclusive counts. Support counts are not counterfactual causal gains. Each correction is also disabled in a separate full-data ablation; unique_alerts_lost_when_disabled measures coverage that depends on it under the remaining rules. Ablation counts can also overlap. Cross-message support can improve provenance without adding a category already identified by the explicit anchor. Pre-alert and cross-message gains often overlap; baseline-support preservation is excluded from new gains.

## Month and year classification yields
| Month | Eligible | v1.3 classified | v1.4 classified | v1.4 eligible yield |
|---|---:|---:|---:|---:|
| 2026-08 | 121 | 26 | 86 | 71.07% |
| 2026-09 | 190 | 28 | 129 | 67.89% |
| 2026-10 | 42 | 1 | 23 | 54.76% |
October official starts end Oct 4; final interval ends Oct 5. Telegram continues Oct 10. Partial October is not a full-month count comparison. All month/year rows with their distinct denominators are provided as CSV and JSON.

## Controlled regression cases

Alert 2563: approved ['shahed_uav']; observed ['shahed_uav']; REQUIRED_CATEGORIES_REPRODUCED.
- Source 55118 (inside_interval, shahed_uav): БпЛА на Бориспіль
- Source 55123 (inside_interval, shahed_uav): БпЛА на Рожни

Alert 2565: approved ['shahed_uav']; observed ['shahed_uav']; REQUIRED_CATEGORIES_REPRODUCED.
- Source 55151 (before_alert, shahed_uav): БпЛА біля Обухова

Alert 2581: approved ['shahed_uav', 'jet_uav']; observed ['jet_uav']; SOURCE_DISCREPANCY_REQUIRES_RESEARCH_LEAD_REVIEW.
- Source 55377 (before_alert, jet_uav): Реактивний БпЛА на Димер
- Source 55391 (inside_interval, jet_uav): Бандероль з Чернігівщини на Згурівку
- Source 55392 (inside_interval, jet_uav): Реактивний БпЛА з Черкащини на Кагарлик

Alert 2578: approved ['shahed_uav']; observed ['shahed_uav']; REQUIRED_CATEGORIES_REPRODUCED.
- Source 55351 (inside_interval, shahed_uav): БпЛА над водосховищем

Alert 2590: approved ['shahed_uav']; observed ['shahed_uav']; WORKING_HYPOTHESIS_ONLY.
- Source 55431 (inside_interval, shahed_uav): БпЛА на Зазимʼя

Cases supplied for rule development are not held-out population accuracy evidence. Alert 2590 remains an unconfirmed working hypothesis. No missing source label is fabricated to force a reviewed ID match.

## Evidence strength, uncertainty and limitations
Accepted strength counts: {"baseline_accepted": 714, "direct_operational_threat": 1984, "pre_alert_operational_context": 25, "contextually_supported_threat": 2835, "pre_alert_contextually_supported": 79}
Accepted uncertainty-reason counts (overlapping): {"experimental_alert_association_not_independent_confirmation": 4923, "literal_geography_not_verified_kyiv_direction": 3926, "pre_alert_association_unapproved_optimal_window": 43, "source_uncertainty": 37, "cross_message_identity_is_inferred": 2835, "alert_association_requires_review": 325, "pre_alert_category_and_episode_link_are_inferred": 325}
Markers: {"total": 12936, "accepted": 5637, "retained_baseline_accepted": 714, "pre_alert_accepted": 112, "context_reference_accepted": 2835}
A broad UAV label is not a verified Shahed model. One channel can describe simultaneous unrelated episodes, omit locality/threat words, or use aliases not approved here. Operational filtering is deterministic lexical evidence, not semantic truth. A recorded other-region geography may identify the origin of a route rather than confinement; route target is inspected separately without rewriting the literal geography. Unclear associations remain rejected candidates. Unknown/missing coverage and unresolved DST remain unknown. Human review required before production adoption or threat-category analysis.

Runtime 24.840804 seconds. Input hashes and all previously existing data/config/report hashes were checked unchanged. No time-series analysis or forecasting performed.
