# Task 004.9 — Residual marker coverage v1.6

**EXPERIMENTAL — HUMAN VALIDATION REQUIRED**

| Version | Classified | Eligible coverage | Text residual |
|---|---:|---:|---:|
| v1_3 | 437 | 24.24% | 1268 |
| v1_4 | 1050 | 58.24% | 655 |
| v1_5 | 1141 | 63.28% | 564 |
| v1_6 | 1295 | 71.82% | 410 |

Against v1.5: 155 newly classified, 1 lost, net 154. 70% target reached: True. Minimum target count: 1263.

| Category | v1.3 | v1.4 | v1.5 | v1.6 |
|---|---:|---:|---:|---:|
| shahed_uav | 233 | 596 | 603 | 630 |
| jet_uav | 12 | 130 | 128 | 131 |
| ballistic_high_speed | 52 | 273 | 360 | 458 |
| cruise_missile | 18 | 89 | 94 | 99 |
| mig31 | 163 | 173 | 195 | 293 |
| strategic_aviation | 3 | 60 | 62 | 77 |
| other | 18 | 67 | 72 | 70 |

## Diagnostics and corrections
All 564 v1.5 text residuals are represented in residual_diagnostics.csv. A–F are nonexclusive diagnostic signals, not human-confirmed error counts.
{"A": 74, "B": 215, "C": 116, "D": 81, "E": 105, "F": 409}
A: new explicit operational lexical anchor; B: previously rejected in-alert lexical candidate; C: bounded chronological reference candidate; D: operational pre-anchor with possible correspondence (acceptance still requires inside support); E: dictionary gap/shorthand signal; F: no supported attribution after corrections.

Corrections: inflected ballistic targets/trajectories and балістиці; Tu-95 without model suffix; existing cruise inflections; БРСД abbreviation; user-approved finite MiG channel bulletins (model unspecified); exact known channel boilerplate excluded from context only; explicit current operational clauses, positions and type-only bulletins. Generic UAV never establishes Shahed model.
Known donation footer is not current operational evidence. Broad donation paragraphs, carrier explanations, satire, conditional future events, denied threats and foreign-region bulletins remain excluded. Negative scope can withdraw invalid old evidence; removals are explicit.
Chronological rules remain 5-minute ordinary gap and 10-minute anchor age; pre-alert lookback remains 10 minutes and requires in-alert correspondence. No widened window, locality-only labels, alert-ID exceptions or taxonomy expansion.

## Correction gains
Overlapping supports are not added. Disjoint gain attribution uses lexical → boilerplate → operational → existing_context priority, an accounting convention, not independent causal contribution.
{"overlapping_supports": {"operational": 99, "lexical": 69, "boilerplate": 58, "existing_context": 8}, "disjoint_first_support": {"boilerplate": 53, "lexical": 69, "operational": 33}, "disjoint_total": 155, "overlap_warning": "Do not sum overlapping supports; disjoint priority is an accounting convention, not causal ablation."}

## Evidence and quality
{"v15_preserved_valid": 1095, "direct_operational_threat": 364, "contextually_supported_threat": 569, "pre_alert_contextually_supported": 94}
All newly accepted categories have full source evidence in category_changes_evidence.csv. Compact exception audit covers high-risk new rules, contradictions and removals; it is not a population precision estimate. Previously reviewed positives and known discrepancies remain in regression_cases.csv.
Source data/previous versions/timestamps/links are hash-verified unchanged. Missing text, outside source span and unresolved DST remain distinct. All new associations retain uncertainty. Independent precision/recall remain null.

## Remaining uncertainty
{"operational_anchor_without_defensible_kyiv_or_pre_alert_correspondence": 89, "no_explicit_lexical_anchor_in_available_context": 207, "only_nonoperational_negated_historical_or_geographically_unlinked_evidence": 113, "withdrawn_previous_false_absence_attribution": 1}
2581 and 1096 remain confirmed-label/source-attribution discrepancies unless newly supported sources reproduce them; provisional cases stay provisional. Human acceptance remains required for analytical adoption.

Reproduce: `.venv/bin/python -m kyiv_alerts.classification_v16 --root .`. Stop marker development after this evidence-supported iteration; no forecasting or automatic commit.
