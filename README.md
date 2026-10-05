# Smart Wardrobe

## 1. Project Overview

A single-user wardrobe demo with photo-based clothing management and deterministic,
explainable outfit recommendations. A modular FastAPI API powers a responsive React
dashboard. No ML, external weather service or authentication is required.

## 2. Features

- Clothing CRUD and partial editing via PATCH; metadata and multiple seasons.
- Multipart image uploads with UUID filenames; local static serving or Supabase Storage.
- Category, color, season and frontend style filters.
- Ranked outfits with color, season, style and formality scores and explanations.
- Responsive cards, edit/confirmation dialogs, image preview, loading/error/retry states.

## 3. Screenshots

Actual local application, using the six existing wardrobe items.

### Wardrobe

![Wardrobe](docs/screenshots/wardrobe.jpg)

### Add clothing

![Add clothing](docs/screenshots/add-clothing.jpg)

### Outfit recommendations

![Outfit recommendations](docs/screenshots/recommendations.jpg)

## 4. Architecture

```text
app/
  main.py, config.py, database.py, models.py, schemas.py
  routers/     clothes.py, recommendations.py
  services/    clothing_service.py, image_service.py, storage.py, recommendation.py
  migrate.py   explicit production schema bootstrap/additive migrations
frontend/src/
  components/  reusable forms, cards, dialogs and feedback
  pages/       wardrobe, add clothing, recommendations
  services/    API client and display labels
  types/, styles/
tests/         backend unit and live API smoke tests
docs/          screenshots, quality audit and deployment runbook
```

Routers handle HTTP; services handle storage/business logic. The recommendation
service works on supplied objects without database access. Local SQLite and uploads
share a configurable data directory; defaults remain at the project root. Production
uses PostgreSQL via `DATABASE_URL` and Supabase Storage, independent of Render's disk.

## 5. Tech Stack

Backend: Python, FastAPI, Pydantic, SQLAlchemy 2, SQLite/PostgreSQL (psycopg), Uvicorn,
python-multipart and httpx (Supabase Storage REST). Frontend: React, TypeScript, Vite and plain CSS. Tests: Python
unittest, FastAPI TestClient and Node's built-in test runner.

## 6. Recommendation Engine

V2.2 forms one top (`tshirt/shirt/polo/sweater/hoodie`), one bottom
(`pants/jeans/shorts`) and shoes; autumn/winter may include one suitable
`jacket` (also recognizing `coat`). Pairwise color/style/
formality compatibility is averaged. Multiple seasons, `all-season` and legacy
`season` fallback are supported. Missing color/style/formality metadata receives
a neutral fallback; missing season data is penalized.

```text
weighted = color × 0.35 + season × 0.25 + style × 0.25 + formality × 0.15
quality_factor = season_score if a season is requested and season_score < 0.80 else 1
total = clamp((weighted + jacket_bonus) × quality_factor, 0, 1)
GET /recommendations?season=spring&limit=3
```

Scores are bounded to 0–1 and exposed with reasons/penalties. Stable ID tie-breaking
makes repeated requests deterministic. Limit is 1–20 (default 3). Seasons:
spring, summer, autumn/fall, winter, all-season (plus all/any aliases).
Exact season matches score 1; `all-season` scores 0.85; mismatches score 0.10.
The core outfit's color/style/formality calculations and weights are unchanged.
An eligible jacket adds up to 0.05, scaled by its compatibility with the core
pieces; the season quality penalty also applies to that bonus. Jackets are never
added for spring, summer or an unspecified season. One best jacket per core outfit
avoids near-duplicate results. The additive nullable `jacket` response uses the same
clothing serializer, including a `seasons` array. Reasons and penalties identify
the outer layer and unsuitable pieces; details expose `jacket_bonus` and
`season_quality_factor` alongside existing scores.
The frontend renders top → optional jacket → bottom → shoes, with four pieces
on desktop/tablet and a two-by-two layered layout on mobile. Responses without a
jacket retain the original three-piece layout and explanation sections.
Out-of-season pieces are penalized, not excluded. See the historical
[real six-item quality audit](docs/recommendation-quality.md), including the lack
of a summer bottom and cross-request repetition. Fit/material do not affect scores.

## 7. API Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/` | Root/health message |
| GET | `/clothes` | List; optional category/color/season queries |
| POST | `/clothes` | Multipart clothing + optional image |
| GET | `/clothes/{id}` | Retrieve one item |
| PATCH | `/clothes/{id}` | JSON partial metadata update |
| DELETE | `/clothes/{id}` | Delete record and associated image |
| GET | `/recommendations` | Ranked outfits; season/limit queries |
| GET | `/uploads/{filename}` | Local-mode static uploaded image |

POST accepts name, category, color, season/seasons, style, fit, material,
formality and image. Repeat the multipart `seasons` field for multiple values.
Responses include nullable legacy metadata and a `seasons` array. List/create
envelopes remain `{clothes: [...]}` and `{message: ..., clothing: {...}}`.
PATCH returns the clothing object directly.

```json
{"style":"smart_casual","formality":6,"seasons":["spring","summer"]}
```

PATCH preserves omitted fields and `image_path`. Updating seasons synchronizes
legacy season to the first value. Formality outside 1–10 returns 422; missing IDs
return 404. Swagger: <http://127.0.0.1:8001/docs>.

## 8. Local Development

Python 3.13 and Node 24 are the tested runtimes. Reuse an existing virtual environment
if available; activation is not required on Windows. For a new checkout:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8001
```

In this checkout the existing interpreter is `..\.venv\Scripts\python.exe`.
With an active environment, the equivalent start command is
`python -m uvicorn app.main:app --reload --port 8001`. In another terminal:

```sh
cd frontend
npm install
npm run dev
```

Frontend: <http://127.0.0.1:5173>. Backend: <http://127.0.0.1:8001>.
For lockfile-based installation, use `pnpm install --frozen-lockfile` instead.
`frontend/.env.example` documents `VITE_API_BASE_URL` (public build-time setting).
Backend `.env.example` documents `FRONTEND_ORIGINS` and `WARDROBE_DATA_DIR`;
export these in the shell/hosting dashboard (backend does not auto-load .env files).
Local defaults require no cloud credentials. `image_path` is `uploads/<uuid>.<ext>`
locally and a durable public HTTPS URL in Supabase mode; API envelopes are unchanged.

### Deployment

`render.yaml` supplies the backend migration/start/build/health configuration;
`netlify.toml` supplies the frontend build/publish configuration and production
URL check. Set the real HTTPS API URL and frontend CORS origin before deploying.
Supabase must be configured manually before deploying these changes. No external
account or data migration was performed. See [setup, secrets and persistence limits](docs/deployment.md).

Local DB/uploads are deliberately excluded from Git. A fresh cloud deployment is
empty. Production requires PostgreSQL + Supabase Storage; missing settings cause an
explicit startup error, never fallback to ephemeral local storage. Backups are still
necessary. The six local records/photos are not automatically transferred. Public CRUD has no authentication:
publish disposable demo data only, not irreplaceable or private records.

## 9. Testing

```powershell
..\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
..\.venv\Scripts\python.exe -m tests
# With the local API running:
..\.venv\Scripts\python.exe tests/smoke_live.py
```

```sh
cd frontend
npm test
npm run build
```

The test runner isolates all unittest tests in disposable storage, even if cloud
credentials exist in the shell. Persistence tests exercise CRUD/PATCH/recommendation
responses with mocked Supabase HTTP plus PostgreSQL config/DDL; live cloud setup
and redeploy checks remain manual. PATCH tests use in-memory SQLite; deployment tests use temporary storage.
Live smoke creates/cleans temporary records/photos and compares persistent rows,
schema and image hashes. UI verification covers add/edit/delete, recommendations,
loading/error/retry, and 390/768/1024/1440px layouts.

## 10. Roadmap

- More precise per-piece explanations and recommendation diversity.
- Upload size/content hardening and repeatable browser accessibility tests.
- Pagination and scalable combination ranking for larger wardrobes.
- Cloud persistence integration/redeploy verification, backups and access controls
  before multi-user production use.

This is a portfolio product demo, not a hardened multi-user production service.
