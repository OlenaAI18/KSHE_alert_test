# Task006 — retrospective forecastability validation

Status COMPLETE; decision **B — NO_STABLE_GAIN_OVER_BASELINES**. Target approved by Task006: weekly recorded official Kyiv alert starts, all colors. A count is an administrative alert start, not an attack or weapon. No live forecast or individual danger/safety prediction.

## Frozen design and chronological evaluation

Conservative complete Europe/Kyiv Monday–Monday weeks: 2022-03-07 through week 2026-09-28; 239 weeks. Exclude initial boundary week even though first record falls on Monday; partial final week excluded. Initial52 calendar weeks: 2022-03-07–2023-02-27. Development origins: 2023-03-06–2025-12-29 (139); untouched selection holdout: 2026-01-05–2026-09-28 (39). Each forecast predicts exactly the next week from its Monday00:00 origin; prior outcomes become available at subsequent origins. Historical replay assumes archived counts were available at week end; true source publication/revision latency is unverified. This is conditional retrospective skill, not a real-time service validation.

B0 expanding historical mean; B1 previous4; B2 previous8; B3 previousweek; B4 recent13/26/52 chosen once on development MAE. One candidate M1 L2 Poisson autoregression with log1p lag1/2/4 and preceding4/8 means; StandardScaler fit separately within each training window; alpha1/10/100 development selection. No seasonal features, Telegram categories, future month means, or full-history normalization. Poisson is a penalized nonnegative mean model, not a claim of equidispersion: no Poisson prediction intervals used. A second model was unnecessary given the small weekly sample and constrained interpretable scope.

Selected B4 window=13; M1 alpha=10; strongest development baseline=B1. Parameters and comparator remain fixed across all final origins. Complete development grid is in training_only_selection.csv; all approaches shown, without selecting a winner for deployment after inspecting holdout.

## Source quality and reconciliation

All2594 starts (including the one unresolved end) are retained; aggregation preserves per-week source IDs. No end is needed to count the known start. No DST fold correction or historical overwrite. Weekly calendar length can be167/168/169 hours. No record week(s): ['2023-10-09']; primary target is null, not observed zero. Eight preceding calendar weeks must be available for common-origin comparison; 9 origins excluded. No unavailable week is compressed away or imputed. The archived-zero robustness run is explicitly conditional and does not certify that zero was observed. Positive counts too have unverified internal completeness. Task005.1 confirms same-source export equality, not historical completeness or independent truth.

Secondary monthly counts are descriptive complete-month references; endpoint months flagged. Minutes forecasting is deferred because of unresolved end/completeness; monthly forecasting has too few observations to justify another experiment. Old classification and temporal outputs remain unchanged (298 protected file hashes).

## Final one-week holdout results

| model | n | MAE | RMSE | mean_bias | WAPE | skill_vs_selected_baseline |
| --- | --- | --- | --- | --- | --- | --- |
| B0 | 39 | 9.5752 | 16.4780 | -7.9917 | 0.5452 | -0.6821 |
| B1 | 39 | 5.6923 | 8.8932 | -3.0513 | 0.3241 | 0.0000 |
| B2 | 39 | 7.0801 | 11.0375 | -4.8301 | 0.4031 | -0.2438 |
| B3 | 39 | 5.6154 | 7.8724 | -1.5128 | 0.3197 | 0.0135 |
| B4 | 39 | 7.7712 | 12.6985 | -5.8698 | 0.4424 | -0.3652 |
| M1 | 39 | 7.3921 | 11.6273 | -5.6294 | 0.4209 | -0.2986 |

Errors are alerts/week; WAPE is fraction; skill=1−MAE/model comparator MAE. Development/all scores also retained in baseline_comparison.csv; development selection results are not independent superiority evidence. Best realized final MAE=B3; this retrospective ranking does not change frozen selection.

Primary paired difference: candidate absolute error minus B1 error, mean=1.6998 alerts/week; pointwise95% circular4-week block interval [-0.0923, 4.1317],2000 reps,seed20261011. Negative favors M1. Blocks8/13 and each baseline are in robustness_checks.csv. These overlapping contrasts are exploratory, not multiple independent discoveries. No superiority claim from an interval crossing zero;39 or fewer final origins and nonstationary changes constrain calibration. No forecast interval calibration is claimed.

## Regime checks

| period | model | n | MAE | skill_vs_selected_baseline |
| --- | --- | --- | --- | --- |
| 2023 | B1 | 34 | 3.1250 | 0.0000 |
| 2023 | M1 | 34 | 3.1172 | 0.0025 |
| 2024 | B1 | 53 | 3.0519 | 0.0000 |
| 2024 | M1 | 53 | 3.2258 | -0.0570 |
| 2025 | B1 | 52 | 2.4375 | 0.0000 |
| 2025 | M1 | 52 | 2.3281 | 0.0449 |
| 2026 | B1 | 39 | 5.6923 | 0.0000 |
| 2026 | M1 | 39 | 7.3921 | -0.2986 |
| September2026 | B1 | 4 | 8.1250 | 0.0000 |
| September2026 | M1 | 4 | 20.6105 | -1.5367 |
| pre_policy | B1 | 174 | 3.3578 | 0.0000 |
| pre_policy | M1 | 174 | 3.4705 | -0.0336 |
| policy_crossing | B1 | 1 | 0.7500 | 0.0000 |
| policy_crossing | M1 | 1 | 9.5876 | -11.7835 |
| post_policy | B1 | 3 | 10.5833 | 0.0000 |
| post_policy | M1 | 3 | 24.2848 | -1.2946 |
| lower_activity | B1 | 78 | 2.9263 | 0.0000 |
| lower_activity | M1 | 78 | 2.6145 | 0.1065 |
| higher_activity | B1 | 100 | 3.8850 | 0.0000 |
| higher_activity | M1 | 100 | 4.8237 | -0.2416 |
| shift_origin | B1 | 15 | 8.7500 | 0.0000 |
| shift_origin | M1 | 15 | 12.4265 | -0.4202 |

Low/high groups classify observed held-out activity against training-only expanding median (diagnostic groups, unavailable future labels are not features). Shift origins are tagged by past4-week mean versus preceding8 difference>=5. Allyear and non-yeargroups reported; year2023–2025 overlap development and are not independent replications. September includes the week starting Sep28, which extends into October. Pre/postSep10 excludes the crossingweek; few post-change weeks allow descriptive errors only. Yellow and red warnings are real alerts and every start is retained. Procedure changes may affect measurement comparability but do not explain away real activity or prove causation. Do not infer that high recorded September activity is artificial.

Final excluding September-start weeks and final pre-change-only errors are provided in robustness_checks.csv. These are diagnostic sensitivities, never alternative model selection. A short 2026/high-activity regime cannot establish stable future performance.

## Answers to the research questions

RQ1: recent-count baselines have lower final errors than the historical mean; this is conditional out-of-sample evidence for recent aggregate information, not a stable military mechanism. RQ2: the previous4-week mean adapts faster than the historical or8/13-week means in this holdout. RQ3: the selected candidate does not beat the strongest development baseline on final MAE. RQ4: errors and rankings change across years and low/high activity; small development-year gains do not replicate in2026. RQ5: no stable model gain supports a forecasting MVP in this scoped experiment.

Final sensitivity MAEs (alerts/week):

| check | comparison | n | estimate |
| --- | --- | --- | --- |
| final_excluding_September_starts | B0 | 35 | 6.2975 |
| final_excluding_September_starts | B1 | 35 | 5.4143 |
| final_excluding_September_starts | B2 | 35 | 5.7321 |
| final_excluding_September_starts | B3 | 35 | 4.9143 |
| final_excluding_September_starts | B4 | 35 | 5.7077 |
| final_excluding_September_starts | M1 | 35 | 5.8815 |
| final_pre_policy | B0 | 35 | 6.2975 |
| final_pre_policy | B1 | 35 | 5.4143 |
| final_pre_policy | B2 | 35 | 5.7321 |
| final_pre_policy | B3 | 35 | 4.9143 |
| final_pre_policy | B4 | 35 | 5.7077 |
| final_pre_policy | M1 | 35 | 5.8815 |

September materially increases the candidate error gap, but excluding September-start weeks does not change the decision. With only3 fully post-policy weeks, causal or stable post-policy superiority cannot be established.

## MVP and research interpretation

Decision **B**. Predeclared A gate: >=10% final MAE improvement over frozen baseline, primary interval strictly below0, final MAE below every baseline, positive skill in at least3/4 yearstrata. Gate outcome is in summary; all criteria apply jointly. Raw daily correlation (~0.47) and month-centered (~0.07) were descriptive, not forecast evidence. Count data can show persistence while a fitted model still fails to improve over recent means. Neither skill nor error reveals military causes, future individual timing, location or threat type.

Recommend a historical analytical dashboard/research findings as the MVP when B/C; do not build it in this task. Existing experiment is sufficient for the scoped archived-target question, but missingness, publication latency and warning-regime change prevent operational claims. No categorical weapon forecast. Stop after Task006.

## Reproduce

`.venv/bin/python -m kyiv_alerts.forecastability --root .`; uses frozen Task005 fact table, sklearn/numpy/scipy/pyarrow/matplotlib installed analysis environment. Same seed, single-thread fits. Output predictions contain cutoff/feature dates and source weekly IDs. See leakage_audit.md, validation_results.json and reproducibility_results.json for executed evidence. All outputs are retrospective historical values.
