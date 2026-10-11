# Kyiv research dashboard · Task 007

Ukrainian static research presentation: React, Vite, TypeScript, bundled Plotly basic charts. Six sections and twelve interactive charts; no backend, runtime API, chat, live forecast or CDN. All numbers derive from frozen research artifacts. Unknown does not mean absence; category counts overlap.

## Run from a clone

Node 24 is tested. From `dashboard/`:

```sh
npm install
npm test
npm run dev
npm run build
npm run preview
```

For deterministic installation use `npm ci`. In the restricted cloud machine use `npm ci --cache /tmp/task007-npm-cache`. Vite prints the local development address; open it on your own computer. This cloud interface does not provide a supported localhost preview link. Production assets are under `dist/` and base `/KSHE_alert_test/`; serve the repository subpath, not filesystem `file://`.

The checked-in `public/data/` works without the private workspace. Optional regeneration from the existing complete research workspace:

```sh
.venv/bin/python scripts/export_dashboard_data.py
.venv/bin/python -m pytest -q tests/test_dashboard_export.py
```

Run these from repository root. Export is not a new research pipeline: selected report fields plus a binned duration presentation of the saved fact table. Input/output SHA256 recorded in `manifest.json`. No source texts, alert/message IDs, original clocks or local paths are exported. One unresolved end is excluded from duration bins, retained in start counts. Annual cards and threat statistics cover the complete source scope; monthly filtering does not fabricate filtered medians. Duration histogram responds to year only. Missing category tests are explicitly unavailable.

Browser checks of the actual production build (preview running on port4173): `node browser-check.mjs` in dashboard. Requires Chromium; set `CHROMIUM_PATH` for a non-default path. Screenshots/results go to `reports/dashboard/`. This helper is for local/cloud verification; frontend unit tests and production build run in Actions.

## Deployment after research-lead approval

**Hosting has not been activated and repository settings were not modified.** Existing authorization permits pushing source/docs; Task007 requires separate research-lead approval for public hosting.

1. Review `reports/dashboard/validation_report.md` and screenshots, approve the concrete dashboard for public viewing.
2. Repository owner: Settings → Pages → Build and deployment → Source → GitHub Actions.
3. Actions → **Publish approved research dashboard** → Run workflow → branch **main**.
4. Workflow builds, tests and uploads `dashboard/dist`; deploy job uses `github-pages` environment. Approve its environment protection if configured. Repository/org policy may require owner permission for Actions/Pages.
5. Open the URL emitted by the deploy step (expected `https://OlenaAI18.github.io/KSHE_alert_test/` only after successful activation/deployment). Verify all charts load under the repository subpath.

Manual `workflow_dispatch` only: a push cannot activate hosting. No repository settings/API are changed by the implementation. Hash navigation avoids SPA deep-link 404s. Assets and aggregate fetches respect Vite base. Backend/chat may be added as a separate approved component; the frozen aggregate loader remains the presentation contract. No chat interface or service is instantiated.

## Scope of inference

Source interval: 2022-02-28 to final end2026-10-05; partial2022/2026, partialOctober. All yellow/red official warnings retained. September policy and intensity changes are descriptive, not causal. v1.6 broad UAV is not confirmed Shahed; MiG channel shorthand is not confirmed MiG31K. 71.82% is classification yield, not accuracy. Task006 evaluates39 final weeks; Task006.1 evaluates36 and does not score the lateSeptember tail. Retrospective taxonomy and incomplete source latency information restrict prospective claims.
