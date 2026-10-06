# Multi-user authentication and deployment cutover

## Security boundary

- Supabase JS handles email/password signup, confirmation, persistent sessions and
  automatic token refresh. No server key is shipped in the browser bundle.
- FastAPI `get_current_user()` verifies every token with the configured Supabase
  project's `/auth/v1/user`; identity is taken only from its verified UUID result.
  Invalid/expired/missing tokens are 401; Auth outages are a safe 503.
- Clothes, PATCH, filters, recommendations and photo downloads use `owner_id`.
  Another owner's ID is 403; missing/unowned legacy records are 404.
- New DB ownership is nullable only for safe migration of existing data. New
  records always receive the authenticated UUID, never a form-supplied owner.
- New photos use `clothing-images/<owner UUID>/<file UUID>.<extension>` in a
  **private** bucket. The backend checks clothing ownership before read/delete;
  it never accepts arbitrary remote image URLs or another user's object prefix.
- API `image_path` is an authenticated relative route (`clothes/123/image`). The
  browser downloads a Blob with its token; protected responses are `no-store`.
  Old public `/uploads` is not mounted. A public bucket would bypass read RLS.
- SQLAlchemy's trusted table-owner connection and the server Storage key bypass
  RLS. Backend checks are mandatory; restrictive SQL guards additionally block
  publishable-key/Data API bypasses, even with pre-existing permissive policies.

## Required dashboard actions (before pushing the auth cutover)

1. **Supabase → Authentication → Sign In / Providers → Email**: ensure email/password
   is enabled. Keep email confirmation enabled if desired; the UI supports it.
2. **Authentication → URL Configuration**:
   - Site URL: `https://wonderful-quokka-3c636d.netlify.app`
   - Redirect URLs: `https://wonderful-quokka-3c636d.netlify.app/` and
     `http://127.0.0.1:5173/` for local development.
   The PKCE confirmation flow uses the browser that initiated registration;
   users can always confirm email then return to the login screen.
3. Back up the database. **SQL Editor → New query**: paste and run
   [`supabase-multi-user.sql`](supabase-multi-user.sql). It adds nullable UUID
   ownership/index, installs two restrictive guards, and makes `clothing-images`
   private. It does not delete/claim rows or move/remove photos. Keep the bucket
   private in **Storage → clothing-images → Configuration**.
4. **Netlify → Project configuration → Environment variables** (Production):

   | Name | Value |
   | --- | --- |
   | `VITE_API_BASE_URL` | `https://smart-wardrobe-api-xskr.onrender.com` |
   | `VITE_SUPABASE_URL` | `https://rjgidtsdzqhrbbeubtzn.supabase.co` |
   | `VITE_SUPABASE_PUBLISHABLE_KEY` | The `sb_publishable_...` key from Supabase **Settings → API Keys** |

   Only the publishable key belongs here. Never enter a secret/service-role key,
   database password, DSN or server token in any `VITE_*` variable. Do not paste
   credentials into chat. The production build guard rejects missing Auth settings
   and recognized secret/service-role configuration.
5. **Render**: keep the existing `SUPABASE_URL`, `SUPABASE_SECRET_KEY`,
   `DATABASE_URL`, `APP_ENV=production`, `IMAGE_STORAGE=supabase`,
   `SUPABASE_STORAGE_BUCKET=clothing-images`, and exact `FRONTEND_ORIGINS`.
   No additional Auth env is needed. Keep the existing start command:

   ```sh
   python -m app.migrate && python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1
   ```

Prepare all settings before deployment; turning off public bucket access will
stop photo reads in the **old unauthenticated** UI until the cutover is complete.
Use a short maintenance window or paused traffic. Never restore public access to
work around auth failures. Then deploy both backend and rebuilt frontend.

## Migration and legacy data

Migration is additive, transactional and repeatable. Existing IDs, metadata and
raw image paths are retained. Old `owner_id=NULL` rows remain hidden, not assigned
to the first signup. Existing images are not moved. Even administrative ownership
assignment alone does not make an old public/flat object path eligible for private
reads: legacy adoption requires a separate explicit row+image mapping migration.

Production checks require RLS to be enabled, the restrictive guards present for
`anon`/`authenticated`, and the bucket private. The current bounded DB preflight,
migration/lock timeouts and credential-safe diagnostics remain unchanged. An
unprepared deployment fails startup rather than exposing wardrobes.

## Final live QA (after dashboard setup/deploy)

Use two disposable accounts A/B, confirm emails if required. Keep credentials
out of logs/chat. Sign in as A, add one TEST clothing/photo; B must see an empty
wardrobe and receive 403 for A's item/photo/PATCH/DELETE IDs. Add B's own TEST
item; verify each account sees only its own records and recommendations. Refresh
the page, sign out, switch accounts and verify stale photos/data are not shown.
Redeploy Render and verify both records and private photos remain. Delete only
these TEST items/photos and then delete the two TEST accounts in Supabase Auth.
Do not delete accounts with real data: automatic account-data erasure is not
implemented.

Local automated tests use disposable SQLite/files and mocked Supabase Auth/Storage
HTTP. They validate routes and security contracts, not a live PostgreSQL/RLS
execution or real two-account confirmation/redeploy flow. SQL guards need the
dashboard execution above. Server-key compromise still bypasses Storage/RLS;
protect and rotate credentials. XSS, auth rate limits, upload hardening and recovery
procedures remain operational concerns beyond this sprint.

## References

- [Server-verified user identity](https://supabase.com/docs/reference/javascript/auth-getuser)
- [Email signup and confirmation](https://supabase.com/docs/reference/javascript/auth-signup)
- [Storage access control](https://supabase.com/docs/guides/storage/security/access-control)
- [Private versus public buckets](https://supabase.com/docs/guides/storage/buckets/fundamentals)
