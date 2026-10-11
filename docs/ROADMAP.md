# Task roadmap

Deadline: October 12, 2026, 23:59 Europe/Kyiv. Effort ranges below are new planning assumptions, not measured work or guarantees; no previous estimates were supplied. Reassess after input inventory. Required data validation and final reporting take precedence over optional forecasting. Tasks are dependency-based, not assigned to days.

| ID | Phase / priority | Depends on | Active effort assumption | Deliverable and acceptance / decision gate |
| --- | --- | --- | --- | --- |
| 001 | Initialization / P0 | None | 1–2 h | Documentation, valid configuration, importable skeleton, ignore rules; no processing. |
| 002 | Ingestion and normalization / P0 | 001, supplied source files | 3–5 h | Immutable inventory/hashes, parsed separate alerts/messages, documented timestamp/null rules and coverage; reconcile counts and investigate rejected records. Gate: approve schema/time conventions. |
| 003 | Temporal linking / P0 | 002 | 2–3 h | Separate links with boundary/overlap policy and evidence; tests cover interval edges, gaps, DST, and foreign keys. Gate: review mapping samples. |
| 004 | Dictionary classification / P0 | 003, taxonomy/rule approval | 3–5 h | Versioned multi-label markers with message evidence; labeled sample audit addresses ambiguity, negation, geography, reposts. Gate: approve measured quality criteria. |
| 005 | Data quality validation / P0 | 002–004 | 2–4 h | Reconciled integrity/coverage report and reproducible dataset; unresolved critical defects block inference. |
| 006 | Time series analysis / P0 | 005, analytical-plan approval | 4–6 h | Descriptive patterns, structural changes and regime stability with uncertainty; report absent/unstable signal. Gate: assess evidence and approve any forecast target. |
| 007 | Conditional aggregate forecasting / P1 | 006, evidence/target gate | 3–5 h | Chronological/walk-forward baseline comparisons, leakage audit, uncertainty. MVP only if robust evidence supports it; otherwise record a justified no-go. |
| 008 | Final research report / P0 | 006; 007 results or no-go | 2–3 h | Reproducibility instructions, limitations, uncertainty, negative results, and reviewed findings; no operational safety claims. |

Validation begins in ingestion and continues through every phase; Task 005 consolidates it rather than deferring all checks. If time is insufficient, explicitly renegotiate scope and record deferred tasks without weakening integrity or silently changing success criteria. Do not begin Task 002 automatically after initialization.
