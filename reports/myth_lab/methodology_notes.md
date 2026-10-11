# Myth Lab methodology · frozen v1

The seven public questions are hypotheses, not confirmed beliefs. Their wording is
retained exactly, but the estimand is official **Kyiv warning starts**, not physical
strikes throughout Ukraine or targeting intent. No new raw-message classification,
model training, significance scan or operational forecast. All comparisons are
exploratory; verdicts do not mean confirmed truth. Calendar, thresholds and state
policy were frozen in config before reading resulting contrasts.

## Inputs / masks

Read saved Task005 daily/fact tables, v1.5 frozen features for sensitivity, and
Task005 statistical_tests.csv. 2594 all-record starts reconcile independently of
resolution; 2593 ends are resolved. 1681 days in the source span;1671 used for new
daily contrasts after omitting both endpoint days, unresolved-end day and the
7day no-record week2023-10-09…15 already flagged in Task006. A skipped date breaks
preceding windows: the calendar is never compressed. Remaining zero counts mean
no recorded start, not verified absence of alerts. No source span extended to the
export date. Source completeness and archival publication latency remain unknown.

## 1–2: calendar contrasts

Three recurring symbolic dates: Feb23, May9, Oct7. Symbolism is a selected calendar
proxy; no intent or exhaustive sacred-date taxonomy. Six fixed Ukrainian dates
stable during the study: Jan1, Mar8, May1, Jun28, Aug24, Dec25. This selected subset
is **not every Ukrainian holiday**; Easter/Trinity and moving/renamed holidays are
not tested. Legal non-working status during martial law is irrelevant to the test.

Each event-day outcome uses a same-weekday control at±7/14/21/28days, restricted
to the same calendar month/year. All available eligible controls averaged first;
events then given equal weight. Controls exclude the selected event set. Holiday
controls additionally omit a conservative superset of fixed historical dates
(Jan7, May8/9, Jul15/28, Oct1/14) plus versioned Easter/Trinity dates, regardless of
legal status in that year. This avoids treating known/potential holidays as controls
without claiming a fully validated changing legal calendar. Easter dates follow the
Orthodox Julian computus (Gregorian +13days in2022–2026); Trinity=Easter+49days.

Primary event-day results and prespecified±1day sensitivity both exported; neither
chosen according to effect. Window controls use complete3day windows centered on
the matching weekday/month. A window may cross a month boundary, so seasonal
matching is approximate. All unavailable event/control windows are omitted with
reasons. Same control dates can support different events; dates/events are not
independent. No IID p-value or confidence level is invented. Small repeated samples
and residual regime confounding keep targeting/calendar conclusions inconclusive,
even when the descriptive difference is positive or negative.

Provenance: source_register.csv. Wikipedia supports fixed calendar definitions;
dated CNN/Moscow Times reports support negotiation dates. Revision IDs recorded
for holiday/negotiation encyclopedia pages, retrieved current-page status stated.
Rada HTTP503 and Reuters401 mean no retrieved official legal validation/Reuters
article is claimed; no access controls bypassed. Source dates are not attack data.

## 3: night overlap

Night22:00–06:00, day06:00–22:00, local Europe/Kyiv. It is a reproducible social-clock
window, not astronomical darkness. Union of v1.6 shahed_uav OR jet_uav gives691
unique alerts (630+131−70), not761. All resolved category intervals used, including
mixed-label warnings. The whole warning interval is counted; a UAV marker does not
establish that UAV activity continued throughout it. UTC elapsed overlap avoids
DST rounding: spring night7hours, autumn9hours. Half-open intervals avoid counting
a day-only interval touching22:00 at its end as a night intersection.

Publish distinct measures: night start share, any-night intersection share,
night-warning-minute share; night fraction of continuous Telegram-span calendar
exposure (~one-third); yearly decomposition and frozen v1.5 sensitivity. Exposure
is a clock reference, not measured channel uptime. These are selected reported
contexts, not confirmed Shahed/physical attacks. Provisional annotations, unequal
message opportunities and missing categories can bias night shares. Pooled63.18%
night minutes does **not** generalize across years:2026 has39.90%. The headline and
visible year table disclose this reversal. Partial support refers to the pooled
reported-minute metric only.

## 4: weekends

Saturday/Sunday vs Monday–Friday. Counts per available day, not pooled totals for
2 vs5days. Also equal-month mean(weekend daily mean−weekday daily mean) for months
with≥4weekend/≥10weekday days. Equal-month adjustment is retrospective descriptive
normalization, not a prospective input or causal weekend effect. Monthly contrasts
retained; endpoints excluded as above. No new inferential test.

## 5: calm

Primary: previous3calendar days together have≤1officialstart. Target: number of
starts on the next day. Sensitivity: previous3days have exactly0starts. Preceding
windows and target must all be observed; no interpolation. Both groups' daily means,
counts, equal-month differences where both groups exist, and annual differences
published. Adjacent targets/windows overlap and are dependent. Sparse calm days in
some months give unstable adjusted contrasts; the pooled negative comparison and
month-adjusted small positive comparison are both prominently disclosed. No
predictive validation follows from either.

## 6: negotiations

Curated Istanbul meetings29Mar2022,16May2025,2Jun2025; clearly dated sources checked
before counting alerts. Not a comprehensive diplomatic calendar. Before/after3days
primary and7days sensitivity, event day omitted, equal event weights. Complete
windows required; selected windows do not overlap each other. No causal design:
negotiation timing is endogenous, numerous wartime events occur, only3samples.
Do not imply physical launches or nationwide attack escalation/de-escalation.

## 7: yesterday/today

Reuse Task005 values verbatim: rawlag1 .4661410331780032, 14day block pointwise95%CI
[.22433659953464732,.5660183735320764]; month-adjusted .07310022627707846,
[-.03836717424286721,.19470779964672033]. Task005's own resolved-count population
and masks remain unchanged; these are not recalculated on the new daily all-start
mask. Month demeaning uses later-in-month information and is not a live feature.
Partial support refers to raw descriptive dependence, not the universal conditional
claim or a prediction rule. Task006 final39weeks lacked stable candidate superiority.

## Publishing / compatibility

Three new allowlisted aggregate files: questions/results/summary. Input SHA256 and
calendar sources recorded; no raw text, IDs, local filesystem paths or tokens.
Existing Task007 public JSON/manifest remain byte-identical. New component loads its
own results; load/schema errors preserve the core dashboard. Seven cards reveal
result/chart only after user action, with badges and expandable limits. No website
workflow or settings changed; hosting approval remains outstanding separately.
