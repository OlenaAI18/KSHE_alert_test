# Research questions and hypotheses

The statements below are questions and hypotheses, not established empirical findings. User-confirmed timestamp alignment is an assumption recorded separately in the decision log.

| ID | Question | Testable hypothesis | Planned evidence |
| --- | --- | --- | --- |
| RQ1 | Are alert frequency and duration temporally structured? | Distributions and dependence differ from an explicitly defined no-pattern reference. | Descriptive aggregates, dependence diagnostics, appropriate uncertainty estimates. |
| RQ2 | Are patterns stable across historical periods? | Temporal associations change across threat/reporting regimes. | Chronological period comparisons and structural-break analysis. |
| RQ3 | Do supplementary threat mentions explain historical variation? | Marker composition is associated with frequency/duration within observed coverage. | Coverage-aware comparisons retaining multi-label evidence; no causal claims. |
| RQ4 | Does full-history training remain useful? | A model using full history can perform worse than one using a recent regime. | Matched chronological evaluation windows and baseline comparisons. |
| RQ5 | Is aggregate prediction justified? | A candidate improves on simple baselines in multiple chronological out-of-sample windows. | Walk-forward errors, uncertainty, stability, and leakage audit. |

Before analysis, approve aggregate target, horizon, binning, comparison metrics, reference hypotheses, multiplicity handling, and stability criteria. Report null/negative results and sensitivity to coverage and regime definitions. Non-stationarity is central, not a post-hoc explanation for failed forecasts. Telegram associations do not verify weapon use or causal mechanisms.
