# Deployment runbook

Status: configuration prepared and locally tested; no cloud resources provisioned.
No hosting CLI/token was available. This runbook does not claim a live public URL.

## Backend — Render

1. Import this repository as a Blueprint using `render.yaml`.
2. Set `FRONTEND_ORIGINS` to the exact frontend HTTPS origin. Comma-separated
   origins are supported; do not include a path or use `*`. CORS is not authorization.
3. Build: `python -m pip install -r requirements.txt`.
4. Start: `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1`.
   No `--reload` in production. Health check: `GET /`.
5. Check `/docs`, `/clothes`, `/recommendations?season=spring&limit=3`.

The supplied free-plan Blueprint is a **disposable demo**. Its filesystem is
ephemeral; SQLite and uploaded photos can disappear on redeploy/restart. Before
importing any data that must survive, select a paid service with a persistent disk
mounted at `/opt/render/project/src/storage` (the `WARDROBE_DATA_DIR` value).
This upgrade incurs charges and is not performed automatically by this sprint.
Do not deploy multiple replicas against this single local SQLite store.

`WARDROBE_DATA_DIR` contains `wardrobe.db` and `uploads/`. The API still exposes
image paths as `uploads/<uuid>.<extension>` at `/uploads/...`. Without this variable,
local development uses the original project-root paths, regardless of cwd.

The six local records/photos are **not** in Git and are **not** automatically
published. A new deployment starts empty. If explicitly choosing to publish them,
make a SQLite backup while local writes are stopped, copy that backup and the
six photos securely to the persistent directory, then start the backend. Never
commit the DB/uploads or overwrite the local originals. Back up both as one set.

## Frontend — Netlify

1. Import the same repository; `netlify.toml` sets base `frontend`, build
   `npm run build`, and publish `dist`.
2. Set the build environment variable `VITE_API_BASE_URL` to the actual backend
   HTTPS URL (no `/docs` or `/clothes` suffix). Production deploys fail early if
   it is missing or points at localhost.
3. Publish, then put the assigned frontend origin in Render's `FRONTEND_ORIGINS`
   and restart the backend. Environment URL changes require a new frontend build.
4. Check images, CORS preflight for POST/PATCH/DELETE, add/edit/delete on a
   temporary record, recommendations, and mobile navigation. Delete test data.

`VITE_*` values are public build-time settings, not secrets. Node 24 is configured;
the committed pnpm lockfile is detected by the build platform. No additional
frontend/backend runtime dependency is required by these changes.

## Public demo safety

There is no authentication by design. Anyone reaching a public API can create,
modify or delete its demo records; CORS only restricts browser access. Use a
disposable dataset, not private or irreplaceable user data. Current MIME-based
image validation lacks upload size/content hardening. Public deployment is a
portfolio demo, not a production-ready multi-user service.

## References

- [Render FastAPI deployment](https://render.com/docs/deploy-fastapi)
- [Render persistent disks](https://render.com/docs/disks)
- [Netlify configuration](https://docs.netlify.com/build/configure-builds/file-based-configuration/)
- [Netlify build environment variables](https://docs.netlify.com/build/environment-variables/overview/)
