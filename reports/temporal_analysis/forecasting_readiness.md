# Forecasting readiness — Task005

**FURTHER_VALIDATION_NEEDED**

Aggregate official counts have measurable nonstationary variation, overdispersion and serial structure (statistical_tests.csv; official_monthly_rate.png). Daily/weekly counts and union alert-minutes are reasonable candidate aggregate targets for prospective validation, after verifying official completeness and resolving endpoint exposure. No model was built.

2593 valid intervals across more than four years are adequate for descriptive diagnostics; only three fully observed calendar years and shifting regimes limit replicated seasonality. The sharp recent rate change and classification/reporting drift prevent a stationarity assumption. Retrospective autocorrelation is not out-of-sample skill.

Telegram bias is substantial:790 alerts outside history,508 eligible unknowns, one DST unresolved; v1.6 labels are experimental.101 already-classified combinations changed between v1.5 and v1.6. Recent yield weakens despite changing publication density. Generic UAV and conditional MiG aliases are not verified technical types. Validate classifier error by chronological/coverage strata and preserve unknowns before category forecasting.1096/2581 source/target discrepancies remain open.

Future aggregate validation must approve target/horizon; use strictly chronological walk-forward evaluation, training-only transforms and an untouched future period. Compare historical constant/training-window mean, last-observed aggregate, rolling mean and calendar-conditioned historical means, with Poisson and overdispersed empirical count reference intervals. Evaluate calibration and errors by regime, compare to no-change baselines, and ensure features were available at prediction time. In-alert messages are unavailable before the alert and would leak information. No operational safe-period or individual attack prediction is justified.

Misleading analyses: extrapolating partial October totals; treating pre-Telegram zeros as no threats; deleting unknowns; treating multi-label counts as weapon counts; interpreting dictionary/vocabulary growth as physical growth; IID alerts, random train/test splits, uncorrected seasonal searches and using retrospective month-centering prospectively. Authorize a separate aggregate-validation task only after these checks. Stop here.
