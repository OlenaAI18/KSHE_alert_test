# Verified public deployment — 2026-10-11

Status: PUBLISHED and verified.

Site: https://olenaai18.github.io/KSHE_alert_test/

[Successful workflow38166996572](https://github.com/OlenaAI18/KSHE_alert_test/actions/runs/38166996572)
built and deployed a96fa43150ed4f6757825db13849f219cb31d017 from main.
Owner enabled Pages in workflow mode after the earlier integration403.

- GitHub Actions: publication audit, frontend tests, build, artifact upload and deploy passed.
- Public HTML: HTTP200 with standard curl certificate validation.
- All15 public JSON: valid and byte-identical to reviewed local public assets; see public_assets.json.
- Real public-site Chromium checks: desktop1440×1000 and mobile390×844 passed.
- Core12 charts, September2026 count190, filtering, tooltip, no horizontal overflow, no page errors or external runtime dependencies.
- Myth Lab7 cards reveal19 total charts; methods, reversals, expand/collapse and filters pass.
- Simulated missing/invalid data shows explicit errors, preserves unaffected charts and invents no zeros.

Evidence: core/browser_validation.json and myth/browser_validation.json with
screenshots in their respective directories. Browser helpers used the public URL.
Chromium did not trust this environment's HTTPS proxy certificate, so temporary
helper copies used ignoreHTTPSErrors for browser checks only; curl validated TLS
using the system trust store. No production TLS or application change was made.
This verification is not a comprehensive accessibility or mobile-network benchmark.
Scientific results, classification and private inputs remain unchanged.
