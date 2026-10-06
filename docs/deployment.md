# Deployment and durable persistence

Production uses **Supabase PostgreSQL + Supabase Storage**, not Render's ephemeral
filesystem. Local development still defaults to the existing SQLite database and
`uploads/`; Supabase Auth is required for real login in either mode. Configuration/
contract tests are not proof of a live Supabase deploy. For the multi-user cutover,
complete [Auth, private bucket and RLS setup](authentication.md) before pushing.

## Supabase setup (manual)

1. Sign in at <https://supabase.com/dashboard>, create an organization/project
   named `smart-wardrobe`, choose a nearby region and save the database password.
2. In the project's **Connect** dialog, choose **Session pooler** and copy its
   PostgreSQL URI (port **5432**). Use the exact host and `postgres.PROJECT_REF`
   username shown there; don't guess the region/cluster. Direct connections need
   IPv6 or the IPv4 add-on, so the session pooler is a suitable IPv4 fallback.
   Set `DATABASE_URL` using `postgresql+psycopg://` and `?sslmode=require`.
   Percent-encode reserved characters in the password (`@` -> `%40`, `/` -> `%2F`).
   The database password is **not** a Supabase API key. Transaction pooler port
   6543 is intentionally rejected by this application.
3. **Storage → New bucket**: name `clothing-images`, leave **Public bucket OFF**,
   then **Create bucket**. For the existing bucket, disable Public without deleting
   it or its objects. New files use `<owner UUID>/<file UUID>.<extension>`.
   Run [the restrictive RLS setup](supabase-multi-user.sql) in the SQL Editor
   before deployment. Do not create anonymous storage-write policies. The backend's
   secret/service-role key performs storage operations after user authorization.
   The adapter stores durable object keys, never public or expiring signed URLs.
4. **Settings → API Keys**: copy a backend **Secret key** (`sb_secret_...`) into
   `SUPABASE_SECRET_KEY`. Existing legacy service-role JWTs can instead be supplied
   as `SUPABASE_SERVICE_ROLE_KEY`. If both are set, `SUPABASE_SECRET_KEY` wins.
   Copy the project HTTPS URL from **Connect** into `SUPABASE_URL`.
   Never give these credentials to the frontend or put them in Git/chat/logs.

## Render configuration

Update the existing `smart-wardrobe-api` service's **Environment**:

| Variable | Value/format | Secret? |
| --- | --- | --- |
| `APP_ENV` | `production` | No |
| `DATABASE_URL` | `postgresql+psycopg://postgres.PROJECT_REF:ENCODED_PASSWORD@POOLER_HOST:5432/postgres?sslmode=require` | **Yes** |
| `IMAGE_STORAGE` | `supabase` | No |
| `SUPABASE_URL` | `https://PROJECT_REF.supabase.co` | No |
| `SUPABASE_SECRET_KEY` | `sb_secret_...` | **Yes** |
| `SUPABASE_SERVICE_ROLE_KEY` | Legacy service-role JWT; alternative to the secret key, not required with it | **Yes** |
| `SUPABASE_STORAGE_BUCKET` | `clothing-images` | No |
| `FRONTEND_ORIGINS` | `https://wonderful-quokka-3c636d.netlify.app` | No |

Use the actual frontend origin if it changes, without a path or trailing slash;
comma-separated origins are supported. `WARDROBE_DATA_DIR` is for local SQLite/
uploads only, not production persistence. `RENDER=true` also enforces production
rules even if `APP_ENV` is forgotten. Missing production settings fail startup
explicitly: the application **never silently falls back** to SQLite or local images.
An empty/invalid production `FRONTEND_ORIGINS` also fails startup rather than
silently selecting localhost CORS defaults. `.env.example` separates safe active
local settings from the complete commented production overrides for Render.

**Build command**: `python -m pip install -r requirements.txt`

**Start command** (update it on an existing service; merely editing the Blueprint
does not automatically update manually configured services):

```sh
python -m app.migrate && python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1
```

Health check remains `GET /`. Test `/docs`, `/clothes`, and
`/recommendations?season=winter&limit=3` (the last two require a user's bearer token).
Root is a process-liveness check; it does
not independently probe Storage/bucket permissions on every request. Confirm those
with a temporary multipart upload, list/get, PATCH, recommendation and DELETE.
Then redeploy and verify a deliberately retained test record/image still exists;
delete that test record afterwards. Two-user cloud verification remains a separate
post-deploy step; local mocks do not prove live authorization or persistence.

## Schema bootstrap / migration safety

`python -m app.migrate` is an explicit, repeatable schema bootstrap. PostgreSQL
migrations hold a transaction-scoped advisory lock to serialize concurrent deploys.
They create missing tables, add **only known legacy metadata/owner columns**, and backfill
`seasons` from `season` **only when `seasons IS NULL`**. No DROP, truncation, renaming,
table replacement or ID reassignment occurs. Column names/types remain unchanged;
`seasons` remains portable JSON text and API responses remain lists.

RLS is enabled on the `clothes` table. Restrictive owner guards on `clothes` and
`storage.objects` must be prepared with `docs/supabase-multi-user.sql`. They restrict
any permissive client policy rather than deleting unrelated existing policies.
The SQLAlchemy connection uses the table owner (`postgres`) and is not subject to
RLS; FastAPI independently verifies bearer tokens and scopes all data operations.
Legacy nullable `owner_id` rows are retained but not exposed or automatically claimed.
PostgreSQL application startup validates that required columns exist without
performing DDL. SQLite retains the existing automatic additive migration behavior.
Back up before any migration. Future structural changes need explicit versioned
migrations; this small bootstrap is not a general-purpose schema reconciliation tool.

Migration startup logs fixed backend/driver labels and boolean connection metadata,
not the DSN or credentials. Failures include the exception types, PostgreSQL SQLSTATE
(when available), and the redacted driver/primary message; SQL parameters, quoted
values, usernames, encoded/decoded passwords and environment secrets are withheld.
Config/driver failures are caught before connection attempts as well. Use the
latest deploy's migration log to distinguish the actual connection or permission
failure; a healthy old service does not prove the new migration succeeded.

PostgreSQL startup runs a read-only `SELECT 1` preflight in a fresh process with a
10-second wall-clock deadline (including DNS/TLS/query waits). Failure exits 1
before DDL or Uvicorn. The driver and pool also use 10-second connection/checkout
timeouts. A successful preflight is followed by a separately bounded 30-second
migration worker; its transaction uses `lock_timeout=5s` and `statement_timeout=10s`
before the advisory lock. A blocked worker is terminated/reaped; no credentials
are passed through CLI arguments and uncontrolled child output is never logged.
Error categories distinguish authentication, missing user/database, DNS, TLS,
connection/lock/statement/migration timeouts and unreachable hosts. These small
bootstrap limits are deliberate; larger future migrations need a separate job.

**Existing data is not automatically transferred.** The six local records/photos
remain untouched and outside Git. A fresh PostgreSQL project starts empty. Before
entering new production data, deploy this configuration and verify persistence.
Transferring old SQLite rows/photos to PostgreSQL/Storage is a separate explicit
operation requiring a stopped-write backup, upload mapping and validation. Lost
ephemeral Render data cannot be recovered by changing configuration.

## Frontend — Netlify

The UI uses Supabase JS login/session refresh, adds bearer tokens centrally and
downloads private `clothes/<id>/image` routes as Blob URLs. Set:
`VITE_API_BASE_URL=https://smart-wardrobe-api-xskr.onrender.com`,
`VITE_SUPABASE_URL=https://rjgidtsdzqhrbbeubtzn.supabase.co`, and
`VITE_SUPABASE_PUBLISHABLE_KEY=sb_publishable_...` (copy it yourself from API Keys).
Base remains `frontend`, publish `dist`. The production build command is
`node scripts/check-production-env.mjs && npm run build`; `netlify.toml` supplies
the guard and SPA rewrite. Changes to `VITE_*` require a rebuild. Never put
database/secret/service-role keys in `VITE_*` values. CORS must allow the exact
frontend origin. Existing server Supabase settings are reused for token validation;
no additional Auth server secret is required.

## Tests and limits

```powershell
..\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
..\.venv\Scripts\python.exe -m tests
```

The isolated runner uses temporary SQLite, never real DB/uploads or environment
credentials. Tests cover actual FastAPI CRUD/PATCH/recommendation responses against
a mocked Supabase HTTP transport, safe object deletion, failed-upload/SQL cleanup,
local fallback, PostgreSQL driver/options/DDL, additive migrations and missing envs.
Live PostgreSQL/Storage, SSL/connectivity, bucket permissions and redeploy persistence
must still be validated after manual setup.

Durability is not a backup policy: free-tier quotas, service outages/project pausing,
account deletion and manual deletion remain possible. Configure DB and image backups
separately. Private bucket access and user-scoped API authorization are now required.
CORS is not authorization; bearer validation is enforced even for direct HTTP clients.

SQL and object storage cannot share one atomic transaction. A failed SQL insert
triggers image cleanup; storage DELETE failures roll back the SQL deletion so the
client can retry. A crash/network ambiguity or SQL commit failure **after** object
deletion can still leave an orphan/missing image. A transactional outbox/reconciliation
job would close that gap but is deliberately not added (no schema/feature expansion).
Image MIME checks remain basic; Supabase bucket quotas/limits still apply.

## References

- [Supabase PostgreSQL connection modes](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [Supabase Storage buckets](https://supabase.com/docs/guides/storage/buckets/creating-buckets)
- [Supabase API key safety](https://supabase.com/docs/guides/getting-started/api-keys)
- [Supabase Storage access control](https://supabase.com/docs/guides/storage/security/access-control)
