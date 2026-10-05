# Finalization QA — 2026-10-05

- Backend unittest discovery: **24/24 PASS**, including V2.1, V2.2, PATCH,
  CORS/environment/storage and actual single-worker Uvicorn startup.
- Existing API metadata smoke: PASS.
- Real HTTP CRUD/PATCH/filter/upload/recommendation smoke: PASS. Temporary
  records/photos cleaned; original rows, schema and image hashes unchanged.
- Frontend service tests: **7/7 PASS**. TypeScript and Vite production build: PASS.
- A production-format HTTPS API setting was built into the JS bundle and inspected;
  this was a configuration test, not a claim that the example hostname is live.
- Netlify production guard rejects missing/localhost URLs and accepts HTTPS URLs.
- Browser UI: six wardrobe images load; category and style filters work. Photo
  preview, create, prefilled edit/PATCH, success feedback, delete confirmation and
  deletion passed using a temporary `Final QA` item, then that item was removed.
- Browser responsive checks: wardrobe/add/recommendations at 390, 768, 1024 and
  1440px, no horizontal overflow. These are browser-driven checks, not a committed
  automated E2E suite.
- Browser failure checks: a separate temporary localhost HTTP proxy + Vite server
  injected a 2s delay and HTTP 503. Loading text/disabled action, error alert, retry
  and recovery to three outfits/six wardrobe cards passed. Both helpers stopped;
  primary localhost services were not stopped or reconfigured.
- Six real items updated **only via PATCH** with requested metadata. Original IDs,
  names, categories, colors and image paths remain unchanged. Six photo hashes and
  the SQLite schema remain unchanged. Recommendation code/weights unchanged.
- Actual wardrobe recommendation results: [quality audit](recommendation-quality.md).
- Three actual UI screenshots saved in `screenshots/`; no debug/error screens.
- Cloud deployment: **not performed**. Render and Netlify dashboards required login;
  no hosting CLI/token was present. Config/runbook ready, no paid resources created.

## Known limits

There is no summer-compatible bottom, so summer outfits use soft season penalties.
Aggregate explanation thresholds do not flag every individual seasonal mismatch.
One legacy jacket has an invalid color label; it is excluded from three-piece
outfits and was not changed beyond requested metadata. No cross-request diversity,
authentication or hardened upload validation. Free cloud filesystem storage is
ephemeral. See [deployment runbook](deployment.md) before publishing user data.
