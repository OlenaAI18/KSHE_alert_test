# Task007 — research dashboard validation

Status: COMPLETE FOR REVIEW / HOSTING NOT ACTIVATED.

## Implemented

Six Ukrainian research sections: overview, historical dynamics, overlapping threat categories, temporal patterns, retrospective forecastability, methodology/limitations. Twelve bundled Plotly interactive charts; year/month filtering, threat highlighting/overlaps, single/multiple-category duration selector, hover details, expandable methodology, hash navigation and responsive layouts. No live API, chat, forecasting model or new analytical experiment.

11 presentation aggregate JSON files plus SHA256 input/output manifest. Export allowlists fields and reads frozen report outputs; duration bins are a display aggregation of the saved fact table. Source data, texts, individual provenance and machine paths are excluded. All source analytical outputs remain unchanged.

## Numerical reconciliation

- Official start denominator2594, resolved durations2593. Monthly/yearly official totals2594; histogram total2593.
- Eligible1803, classified1295, unknown508=410text+98no-text; yield1295/1803=71.82473655%, displayed71.82%.
- Overall duration median37.36666667min, displayed37.37.
- Category counts630/131/458/99/293/77/70 match v1.6; diagonals and single+multi counts reconcile. Sum exceeds1295 because categories overlap.
- Single1015, multi280, unknown508; respective median32.35/110.15/26.13333333min.
- Daily lag1 .4661410331780032; month-adjusted .07310022627707846. All four Holm seasonal p-values exceed.05.
- Final Task006 history234rows=39weeks×6methods; mean saved absolute errors equals published MAE per method. M1=7.39213, B1=5.69231, B3=5.61538 alerts/week. Tested candidate did not demonstrate stable superiority.
- Task006.1 category states and nullable MAE copied from saved decisions: UAV inconclusive, ballistic no stable gain, five insufficient. 36weeks with lateSeptember tail unscored. No forced prediction for failed categories, no zero substituted for missing results.
- Yearly2022/2026 and October2026 explicitly partial. Yellow/red warnings retained. No policy-causation claim or safe-time recommendation.

## Executed checks

- Full Python suite: **632 passed**,0failed,0skipped;88.40seconds. Includes6 exporter/reconciliation tests.
- Frontend Vitest: **8 passed**,0failed. Public data contract, numeric datasets, category/overlap counts, partial periods, filter behavior, missing data, subpath/navigation, privacy scan and failed fetch handling.
- `npm ci --cache /tmp/task007-npm-cache`: PASS from lockfile.
- `npm run build`: PASS TypeScript and Vite production build. Browser tests target production assets under `/KSHE_alert_test/`, not dev transforms.
- Chromium1440×1000 desktop and390×844 mobile:12charts, no page errors, no horizontal body overflow, no external runtime data/CDN requests. Year/month filter yields190 September starts; category/duration selector verified against saved26.96666667min jet single-category median. Hash navigation, expandable details and592-alert tooltip verified. Failed summary fetch shows explicit error without fabricated statistics. See browser_validation.json/screenshots.
- Export repeated to two independent directories: all12JSON outputs byte-identical.
- Prior Tasks005/005.1/006/006.1 reports and all existing analysis/classification sources unchanged.

## Deployment and remaining steps

Manual-only Pages workflow prepared; push will not deploy. No settings modified, no live-site URL verified. Research lead must approve public hosting, then repository owner selects Settings→Pages→GitHub Actions and runs the workflow on main. Org/environment protections may require owner action. See dashboard/README.md for exact procedure.

Build emits a nonfatal bundle-size warning: bundled Plotly+React JS≈1.386MB, gzip≈459KB. Local/offline-chart functionality verified; public mobile network load performance not benchmarked. No external font/CDN. No claim of comprehensive accessibility certification or prospective statistical validation. Git source reproduction needs onlyNode; aggregate regeneration/full Python suite needs the retained private workspace. Cloud environment install/start instructions saved as draft; review/save and Publish in environment settings activates the updated reusable environment, separate from website hosting.
