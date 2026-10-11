# Leakage and quality audit — Task006

- Forecast origin is Monday00:00 Europe/Kyiv; target is that next complete calendar week.
- Every training target ends at or before origin; feature latest week is strictly earlier.
- Lag/calendar windows use exact original indices; missing weeks are not deleted or filled.
- Scaling and Poisson fitting use only supervised rows before origin; no target-week feature.
- B4 window, candidate alpha, comparator are selected only using origins before2026-01-05.
- Final outcomes may update later expanding fits, never selection. Development scores are selection evidence, not untouched test evidence.
- No source end inference, future detrending, retrospective Telegram features or random splits.
- Source boundary weeks excluded; no-record week null in primary, separate explicitly conditional zero sensitivity.
- All known official starts included, no color exclusions. Source IDs reconcile to2594 records.
- Actual historical publication/revision latency and positive-week completeness are unverified: archived week-end availability is a retrospective assumption, not a validated live feature feed.
- Block intervals account approximately for error dependence; short nonstationary final series prevents guaranteed coverage.
- Synthetic suffix perturbation and scaler/training reconstruction tests verify past-only predictions; real-output cutoff assertions verify every origin. Actual results in validation_results.json.
