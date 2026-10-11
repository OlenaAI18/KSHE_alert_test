# Agent instructions

## Mission
Build a trustworthy, reproducible Python research project for historical Kyiv air raid alerts by **October 12, 2026, 23:59 Europe/Kyiv**.

## Working principles
Research correctness over complexity; explicit assumptions over hidden assumptions; reproducibility over one-off scripts; simple solutions over unnecessary abstraction; measured evidence over speculation. Preserve original data and trace derived features to source records. Respect the deadline and prioritize required research deliverables over optional forecasting.

## Development workflow
1. Read this file and relevant documents under `docs/`.
2. Inspect existing code and Git changes before editing; preserve user work.
3. Implement only the current requested task scope. Historical task restrictions describe their original stages; later explicit user tasks authorize scoped extensions.
4. Add or update appropriate tests; use pytest for future automated tests.
5. Run available tests and checks; distinguish passed, failed, skipped, and unrun checks. A zero-test run is not validation.
6. Report actual results and limitations; never invent execution results.
7. Update documentation when behavior or assumptions change.

Use the existing checkout in each isolated cloud task; do not create Git worktrees unless the user explicitly requests one. Python 3.11+ is required. Use pathlib and configurable relative paths; support Windows and Linux. Keep processing deterministic where applicable. Install dependencies only when needed.

## Change control
Do not independently change the research objective, success criteria, threat taxonomy, statistical target definition, data interpretation rules, or approved methodology. Propose necessary changes explicitly, explain consequences, and coordinate research decisions outside the code implementation workflow. Provisional items require review before implementation. Log decisions in `docs/DECISIONS.md`.

## Data protection
Never overwrite raw source files or commit large raw exports, personal data, secrets, or credentials. Preserve originals, record input hashes and transformation versions in future work, and maintain reproducible transformations and source-record traceability. Never introduce an arbitrary timestamp offset: source timestamps are user-confirmed as aligned. Unknown information is not confirmed absence.

## Safety and interpretation
Distinguish retrospective analysis from prediction. Do not present historical correlations as reliable warning forecasts or recommend when it is safe to ignore official warnings. Any evidence-supported MVP concerns aggregate historical indicators, never individual attacks or protective behavior. Report uncertainty and coverage limitations.

## Task completion protocol
Return task summary, files created/changed, executed checks and outcomes, actual quantitative results where applicable, unresolved issues/risks, recommended next task, and commit hash if created. Do not create commits without workflow authorization. For an authorized Task 001 commit use `chore: initialize Kyiv air alert research architecture`.
