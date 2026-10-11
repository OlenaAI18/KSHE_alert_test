# Research dashboard publication readiness

Date:2026-10-11. Status: **READY FOR REVIEWED STATIC PUBLICATION**.
This is readiness for a historical research dashboard, not independently validated
classification truth, a live alert service or an operational forecasting product.
Hosting has not been enabled or deployed by this review.

## Corrections

- Current Ukrainian README replaces outdated initialization-only status and gives
  Node24/frozen-lock startup, research findings, source boundaries and exact release
  procedure. Old per-task commands/counts remain in docs/REPRODUCTION.md labelled
  historical. Architecture/roadmap/charter/validation introduction reflect delivered
  Tasks007/007.1; scientific objectives and frozen decisions stay unchanged.
- v1.6 dashboard report URL now targets the tracked review_downloads handoff instead
  of an ignored reports/classification_v1_6 file available only in the local workspace.
- Node24 pinned via engines/.nvmrc. Vitest upgraded3.2.7→5.0.3 after confirmed mocker/
  tinypool security advisories. Lockfile installation verified and npm audit now0
  findings across production/development dependencies; no claim of a comprehensive
  Python vulnerability audit.
- New dependency-free Node publication gate runs before each build: exact15asset
  allowlist, core/reviewed MythLab SHA256, present research input hashes, private-field
  and absolute-path exclusion, population/coverage/year/partial-period/duration/
  multi-label/holdout/night/correlation reconciliation. Missing private input references
  are explicit and do not block a public frontend-only checkout.
- Read-only push/PR CI runs repository audit, exact install,19tests, guarded build
  and npm audit. Manual Pages build runs repository/data checks; Pages/id-token write
  permissions limited to deploy job. No workflow auto-enables hosting.
- Browser helpers use portable fileURLToPath and configurable evidence output so
  current validation does not overwrite historical Task007/MythLab evidence.
- Previously user-authorized Excel/CSV/ZIP explicitly described as historical human
  review material, potentially containing source excerpts/individual provenance,
  not production ground truth. These are not copied into Pages assets.

## Executed verification

| Check | Result |
| --- | --- |
| Full retained-workspace Python suite |647passed;0failures/errors/skips;94.86s |
| Frontend tests on clean checkout |19passed;0failed;3test files |
| Clean-checkout npm ci and production build |PASS on Node24.19.0 /Vite7.3.7 /TypeScript5.9 |
| Public data gate |15files;2594starts;1803eligible;1295classified;7myths;PASS |
| npm audit |0vulnerabilities, including development dependencies |
| Python dependency compatibility |pip check: no broken requirements |
| Python wheel build |PASS using standard isolated build; no raw dataset included |
| Desktop/mobile production browser |12core/19revealedcharts;filters/tooltips/navigation/reveal/collapse;PASS |
| Missing/invalid MythLab data |Core12charts stay available;explicit error;no fake zeros |
| Repository source/link/artifact audit |Valid JSON/CSV/ZIP/Excel;no broken tracked links or scanned credential/phone patterns |
| Historical preservation |261research/source/config/review/public-data files byte-identical to edd1982;all15public JSON unchanged |
| Production artifact boundary |Only index/assets/data;no review downloads/source text/service API |

The fresh verification used a new local Git clone of baseline edd1982 with the
staged release changes applied; it has no retained data/ or .venv. Four references
to private Parquet inputs were explicitly unavailable; existing versioned report
inputs and public checksums matched. No private input regeneration was claimed.
Both browser helpers ran against the actual built repository subpath, writing only
new release_readiness/core and release_readiness/myth evidence. No external runtime
requests, page errors or horizontal body overflow at1440×1000/390×844.

## Release procedure

1. Review this report, current screenshots and the research limitations.
2. Research lead approves public hosting of the concrete research dashboard.
3. Repository owner selects Settings→Pages→GitHub Actions.
4. On main manually run **Publish approved research dashboard**. Resolve organization/
   github-pages environment approval requirements if configured.
5. Verify the deployment URL emitted by the deploy step. No live URL or successful
   remote Actions run is claimed by local verification; only the verified Git push
   and local/fresh-checkout checks are reported.

## Remaining boundaries

Classification v1.6 remains experimental;71.82% is yield, not accuracy. Unknown/null
is not absent threat; categories overlap. Endpoint years/months are partial, warning
levels changed; source comparisons can share origin. Retrospective taxonomy and
archive-latency assumptions limit forecast interpretation. MythLab calendars are
selected subsets and comparisons descriptive/noncausal. Pooled night share reverses
in2026; calm contrasts depend on adjustment. No research results were revised.

The repository is not an aggregate-only public dataset: authorized historical human
review downloads intentionally retain excerpts. The **website** is aggregate-only.
Pattern scanning is not a complete privacy certification; it scans tracked text and
ZIP/XML contents for specific key/token/phone patterns, not decoded compressed
Parquet field contents or every possible identifier. Original raw sources remain
ignored. Vite reports a nonfatal Plotly bundle warning (~1.396MBJS/~461KBgzip);
real mobile network timing and comprehensive accessibility certification were not
performed. Old archive documents describe their historical stage and are not
rewritten to change evidence. No unrelated research or deployment was started.
