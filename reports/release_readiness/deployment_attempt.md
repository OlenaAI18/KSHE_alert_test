# Public deployment attempt — 2026-10-11

Status: BLOCKED by GitHub integration permissions; site not published.

The user explicitly approved publication ("публікуй"). Repository is public,
default branch main; deployed candidate cde7a3cb75be36c81b08ab2e520d3947eee60526.

- GET repository Pages: HTTP404.
- POST repository Pages with build_type=workflow: HTTP403, Resource not accessible by integration.
- Manual workflow dispatch succeeded.
- [Workflow38165831348](https://github.com/OlenaAI18/KSHE_alert_test/actions/runs/38165831348): build passed, including publication audit, frontend tests, production build and Pages artifact upload.
- Deployment failed with HTTP404: Ensure GitHub Pages has been enabled.

## Required owner action

Open [Pages settings](https://github.com/OlenaAI18/KSHE_alert_test/settings/pages),
select Build and deployment → Source → GitHub Actions. Then rerun the failed
deployment job or manually dispatch Publish approved research dashboard on main.

Expected URL after successful deployment: https://OlenaAI18.github.io/KSHE_alert_test/.
This is not a verified live-site link. Public HTML, assets, all15 JSON files,
charts and mobile rendering still require verification after activation.
No research data or classifier behavior changed during this attempt.
