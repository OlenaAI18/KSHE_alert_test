# Pavlo Loiek comparison — pinned10b4d32f37843533f59f2197153993be338f7f51

Read README, committed snapshot and notebook, not just headline results. Source references PAVLO_README/PAVLO_DATA/PAVLO_NOTEBOOK in source_register.csv.

| Dimension | External research | This project | Consequence |
|---|---|---|---|
| Geography |25 regions,101705 starts; Kyiv City2299 |Kyiv City2594 official records |Nationwide rates/weekday/hour results cannot validate Kyiv rates |
| Source |Vadimkin volunteer eTryvoga snapshot |Municipal Kyiv Digital intervals; Telegram context |Different recording paths, shared underlying public alert events |
| Dates |2022-02-25 through frozen2026-06-23 |2022-02-28 through2026-10-05 |Reconcile only common complete days; endpoints partial |
| Durations |Naive+30min ends flagged |One DST end unresolved |Exclude volunteer estimates for end validation; do not repair originals |
| Trend/seasonality |README calls trend dominant and annual component unreliable |Holm-adjusted seasons not established; monthly-centering removes much raw ACF |Conceptual agreement, not independent Kyiv seasonal replication |
| Weekly/hour findings |Nationwide descriptive counts and Prophet components |Kyiv-only common-span weekday rates in kyiv_weekday_comparison.csv |Different denominators; no weekday forecast conclusion |
| Forecast |Nationwide Prophet fitted to available history minus final partial day |No forecasts in Task005/005.1 |No held-out forecast evaluation located; do not adopt external projection |
| Independence |Same dataset lineage as current Vadimkin volunteer |Distinct municipal file, but administrative alert process shared |Two volunteer snapshots do not constitute two ground truths |

The external README warns projection is extrapolation and strategic changes could break it. The statement that decomposition is “decisive” is stronger than a fitted component plot can establish: no independent calendar-seasonality or prospective skill validation is shown. No forecasts were executed or imported.

Quantified Kyiv disagreements and matching tolerance sensitivity are in historical_reconciliation_summary.csv/historical_count_periods.csv. No whole-history2299-vs2594 discrepancy is interpreted without date alignment. Current official-channel archive duplicates and incomplete later coverage are separate source-quality findings. Physical/context labels do not exist in Pavlo's four-column snapshot.
