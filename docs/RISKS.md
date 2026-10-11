# Research risk register

| Risk | Impact | Mitigation | Detection |
| --- | --- | --- | --- |
| Incorrect temporal mapping | Misattributed message evidence | Preserve timestamps, approve endpoint/overlap policy, handle DST explicitly | Boundary fixtures, foreign-key checks, reviewed linked/unlinked samples |
| Ambiguous threat terminology | Misleading contextual markers | Reviewed dictionary, explicit ambiguity/unknown states | Labeled audit samples and error analysis |
| Uneven Telegram coverage | Apparent absence interpreted as no threats | Record coverage/gaps; retain pre-coverage alerts | Coverage timelines and missingness stratification |
| Changes in reporting behavior | Artificial historical trends | Separate reporting intensity from alert outcomes, period sensitivity | Message-volume/composition shifts and source-format audit |
| False-positive classifications | Overstated threat composition | Address negation, reposts, historical mentions and geography | Precision/recall or suitable multi-label metrics on reviewed samples |
| Data leakage | Inflated forecast performance | Record feature availability, chronological splits, training-only fitting | Feature provenance audit and fold boundary checks |
| Non-stationary temporal patterns | Unstable pooled conclusions | Regime comparisons and structural-break sensitivity | Windowed diagnostics and temporal error profiles |
| Insufficient out-of-sample evidence | Unsupported MVP | Baselines, multiple chronological windows, explicit evidence gate | Held-out errors/uncertainty and gate review |
| Deadline overrun | Incomplete valid report | Prioritize core validation/report, reassess effort, defer optional MVP explicitly | Task acceptance tracking and remaining-effort review |
| Input corruption or unsafe archive paths | Lost evidence or unsafe extraction | Immutable copies, hashes, safe archive inventory | Checksum comparisons and member-path validation |
| Privacy / source reuse uncertainty | Inappropriate disclosure | Ignore exports and personal data; review reuse before publication | Git content review and report disclosure review |

A risk register does not establish that any failure has occurred. Log observed issues with evidence during later tasks; unresolved critical data-quality defects block affected conclusions.
