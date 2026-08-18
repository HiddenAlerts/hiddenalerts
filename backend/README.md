# HiddenAlerts

AI-driven fraud intelligence monitoring system. Collects raw data from trusted government and cybersecurity sources, processes articles with OpenAI GPT-4o-mini, scores them using a 5-factor Signal Scoring System, and surfaces actionable fraud alerts through an admin dashboard.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Local Development Setup](#local-development-setup)
- [Environment Variables](#environment-variables)
- [Database](#database)
- [Source Adapters](#source-adapters)
- [Ingestion Pipeline (M1)](#ingestion-pipeline-m1)
- [AI Processing Pipeline (M2)](#ai-processing-pipeline-m2)
- [Signal Scoring System](#signal-scoring-system)
- [Admin Dashboard](#admin-dashboard)
- [API Endpoints](#api-endpoints)
- [Scheduler](#scheduler)
- [Running Tests](#running-tests)
- [Testing the AI Pipeline](#testing-the-ai-pipeline)
- [Milestone Roadmap](#milestone-roadmap)

---

## Architecture Overview

```
                    ┌───────────────────────────────────────────────┐
                    │            APScheduler                        │
                    │   Collection: every 6h · Processing: every 30m│
                    └──────────┬─────────────────────┬──────────────┘
                               │                     │
                    ┌──────────▼───────────┐  ┌──────▼──────────────────┐
                    │   Source Adapters    │  │  Alert Pipeline         │
                    │  (RSS + HTML scrape) │  │  keyword → AI → score   │
                    └──────────┬───────────┘  └──────┬──────────────────┘
                               │  RawItemData        │  ProcessedAlert
                    ┌──────────▼───────────┐  ┌──────▼──────────────────┐
                    │  Normalization       │  │  Signal Scoring         │
                    │  Deduplication       │  │  5-factor (5–25 pts)    │
                    └──────────┬───────────┘  └──────┬──────────────────┘
                               │                     │
                    ┌──────────▼─────────────────────▼─────────────────┐
                    │              PostgreSQL Storage                  │
                    │  raw_items · processed_alerts · events · reviews │
                    └──────────────────────┬───────────────────────────┘
                                           │
                    ┌──────────────────────▼───────────────────────────┐
                    │            FastAPI REST API + Admin Dashboard    │
                    │  /api/v1/alerts · /api/v1/events · React Admin   │
                    └──────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+, FastAPI |
| Database | PostgreSQL 16 |
| ORM | SQLAlchemy 2.x (async) + Alembic |
| HTTP | httpx (async) |
| RSS parsing | feedparser |
| HTML scraping | BeautifulSoup4 + lxml |
| Scheduling | APScheduler 3.x |
| Config | pydantic-settings |
| AI Processing | OpenAI GPT-4o-mini (structured outputs) |
| Auth | python-jose (JWT) + passlib/bcrypt |
| Admin UI | React (Next.js) frontend, served separately |

---

## Project Structure

```
hiddenalerts/
├── alembic/
│   ├── env.py                          # Async Alembic config
│   └── versions/
│       ├── 0001_initial_schema.py      # All tables + seed 10 sources
│       ├── 0002_signal_scoring.py      # credibility_score + 6 scoring fields
│       ├── 0003_fix_source_urls.py     # Correct RSS URLs; FTC/FinCEN → HTML
│       ├── 0004_ai_fields_and_admin_seed.py  # 3 AI columns + admin user seed
│       ├── 0005_user_roles.py         # M3: role, full_name, email prefs, last_login_at
│       └── 0006_alert_publication.py  # M3: is_published, published_at, published_by_user_id
├── app/
│   ├── main.py                         # FastAPI app + lifespan + static mount
│   ├── config.py                       # Pydantic settings (loaded from .env)
│   ├── database.py                     # Async engine + session factory
│   ├── auth.py                         # JWT + bcrypt utilities; cookie + Bearer auth; role dependencies
│   ├── models/
│   │   ├── base.py                     # DeclarativeBase
│   │   ├── source.py                   # SOURCES table
│   │   ├── raw_item.py                 # RAW_ITEMS table
│   │   ├── processed_alert.py          # PROCESSED_ALERTS table (AI + scoring fields)
│   │   ├── event.py                    # EVENTS + EVENT_SOURCES tables
│   │   ├── user.py                     # USERS table
│   │   ├── review.py                   # ALERT_REVIEWS table
│   │   ├── weekly_report.py            # WEEKLY_REPORTS table
│   │   └── run_log.py                  # RUN_LOGS table
│   ├── schemas/
│   │   ├── source.py                   # SourceRead, SourceUpdate
│   │   ├── raw_item.py                 # RawItemRead, RawItemDetail
│   │   ├── run_log.py                  # RunLogRead
│   │   ├── alert.py                    # ProcessedAlertRead/Detail, EventRead/Detail
│   │   └── auth.py                     # M3: LoginRequest, TokenResponse, UserRead, ChangePasswordRequest
│   ├── sources/                        # Source adapters (10 total — unchanged from M1)
│   │   ├── base.py
│   │   ├── rss_adapter.py
│   │   ├── registry.py
│   │   ├── sec_press.py · ftc_feeds.py · fincen_press.py
│   │   ├── ic3_alerts.py · doj_press.py · krebs.py
│   │   └── fbi_national.py · fbi_blog.py · fbi_news.py · bleeping.py
│   ├── pipeline/
│   │   ├── normalizer.py               # URL norm, SHA-256, text extraction, date parsing
│   │   ├── deduplicator.py             # url_hash + content_hash duplicate checks
│   │   ├── collector.py                # M1: fetch → normalize → dedup → store
│   │   ├── keyword_filter.py           # M2: case-insensitive keyword gate
│   │   ├── ai_processor.py             # M2: OpenAI GPT-4o-mini structured analysis
│   │   ├── signal_scorer.py            # M2: 5-factor arithmetic signal scoring
│   │   ├── event_grouper.py            # M2: entity overlap + category event matching
│   │   └── alert_pipeline.py           # M2: orchestrator for the 4-step pipeline
│   ├── scheduler/
│   │   └── jobs.py                     # APScheduler: collection (6h) + processing (30m)
│   ├── api/
│   │   ├── health.py                   # GET /api/v1/health
│   │   ├── sources.py                  # CRUD + trigger endpoints
│   │   ├── raw_items.py                # Query + stats endpoints
│   │   ├── alerts.py                   # M2: alerts + events REST API
│   │   ├── auth.py                     # M3: JSON auth endpoints (login, me, change-password)
│   │   ├── client_alerts.py           # M3: subscriber-safe published alert feed
│   │   ├── public_alerts.py           # M3 Slice 4: public feed (list, detail, stats) — no auth
│   │       ├── index.html              # HIGH/MEDIUM/LOW alert panels
│   │       ├── alert_detail.html       # Score breakdown + review form
│   │       └── monitoring.html         # Source health + run logs
│   └── static/
├── tests/
│   ├── conftest.py                     # pytest fixtures (SQLite, JWT secret patch)
│   ├── test_pipeline/
│   │   ├── test_normalizer.py          # M1: hashing, text extraction, date parsing
│   │   ├── test_keyword_filter.py      # M2: keyword matching, word boundary, multi-word
│   │   ├── test_signal_scorer.py       # M2: all 5 scoring factors, risk bucketing
│   │   ├── test_ai_processor.py        # M2: mock OpenAI, retry logic, edge cases
│   │   └── test_event_grouper.py       # M2: event creation, entity matching, 7-day window
│   └── test_api/
│       ├── test_health.py              # API smoke tests
│       ├── test_auth.py                # JWT, bcrypt, login endpoint
│       ├── test_alerts_api.py          # Alerts + events REST API
│       └── test_public_alerts.py      # M3 Slice 4: public list, detail, stats — no auth
├── .env.example                        # All config variables with defaults
├── .env.production.example             # Production config template
├── alembic.ini
├── docker-compose.yml                  # Production: PostgreSQL + FastAPI
├── docker-compose.dev.yml              # Dev: PostgreSQL 16 only
├── pytest.ini                          # asyncio_mode = auto
└── requirements.txt
```

---

## Local Development Setup

### Prerequisites
- Python 3.11+ (project uses conda env `HiddenAlerts`)
- PostgreSQL 16 (local install or Docker)
- Git

### 1. Clone and install dependencies

```bash
git clone https://github.com/adnanit035/HiddenAlerts.git
cd hiddenalerts

conda activate HiddenAlerts
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — set OPENAI_API_KEY, JWT_SECRET_KEY, ADMIN_EMAIL, ADMIN_PASSWORD
```

### 3. Set up the database

**Option A — Docker:**
```bash
docker compose -f docker-compose.dev.yml up -d
```

**Option B — Local PostgreSQL:**
```sql
CREATE DATABASE hiddenalerts;
CREATE USER hiddenalerts WITH PASSWORD 'dev_password';
GRANT ALL PRIVILEGES ON DATABASE hiddenalerts TO hiddenalerts;
\c hiddenalerts
GRANT ALL ON SCHEMA public TO hiddenalerts;
ALTER SCHEMA public OWNER TO hiddenalerts;
```

### 4. Run migrations

```bash
ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD=yourpassword alembic upgrade head
```

This creates all 9 tables, seeds all 10 sources, and creates the admin user.

### 5. Start the server

```bash
uvicorn app.main:app --reload --port 8000
```

### 6. Verify

```
http://localhost:8000/api/v1/health  → DB + scheduler status
http://localhost:8000/docs           → OpenAPI documentation
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | Async DB URL (used by app) |
| `DATABASE_URL_SYNC` | `postgresql://...` | Sync DB URL (used by Alembic) |
| `APP_ENV` | `development` | Environment name |
| `DEBUG` | `false` | SQLAlchemy query logging |
| `LOG_LEVEL` | `INFO` | Python log level |
| `SCHEDULER_ENABLED` | `true` | Start APScheduler on app startup |
| `SCHEDULER_INTERVAL_HOURS` | `6` | How often to poll all sources |
| `OPENAI_API_KEY` | _(empty)_ | OpenAI key — required for AI processing |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model name |
| `AI_PROCESSING_ENABLED` | `true` | Enable/disable AI processing pipeline |
| `AI_MAX_RETRIES` | `3` | Max retries on OpenAI rate limit errors |
| `AI_RETRY_DELAY_SECONDS` | `2.0` | Base delay for exponential backoff |
| `JWT_SECRET_KEY` | _(empty)_ | Secret for signing JWT tokens — required |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `JWT_EXPIRE_MINUTES` | `43200` | Token lifetime (30 days) |
| `ADMIN_EMAIL` | _(empty)_ | Admin user email — set before first migration |
| `ADMIN_PASSWORD` | _(empty)_ | Admin user password (plain-text; hashed at migration time) |
| `TEST_SUBSCRIBER_EMAIL` | _(empty)_ | Optional test subscriber seed (M3, dev only) |
| `TEST_SUBSCRIBER_PASSWORD` | _(empty)_ | Test subscriber password (plain-text) |
| `TEST_SUBSCRIBER_FULL_NAME` | `Test Subscriber` | Test subscriber display name |

---

## Database

### Schema

| Table | Purpose |
|-------|---------|
| `sources` | Source registry — URLs, adapter class, keywords, credibility score, polling config |
| `raw_items` | Every collected article — raw text + raw HTML snapshot |
| `run_logs` | Per-source poll history — status, item counts, errors |
| `processed_alerts` | AI summaries, signal scores, risk level, entities, matched keywords |
| `events` | Grouped fraud events across multiple sources |
| `event_sources` | Links events to their contributing alerts |
| `alert_reviews` | Human review decisions on alerts |
| `users` | Admin and subscriber users — role-aware (`admin` / `subscriber`) |
| `weekly_reports` | Generated weekly intelligence reports (Milestone 3) |

### `processed_alerts` — Key Columns (M2)

| Column | Type | Description |
|--------|------|-------------|
| `summary` | TEXT | 3–5 sentence AI-generated summary |
| `primary_category` | VARCHAR | Investment Fraud / Cybercrime / Consumer Scam / Money Laundering / Cryptocurrency Fraud |
| `secondary_category` | VARCHAR | Optional secondary classification |
| `entities_json` | JSONB | Named entities: companies, individuals, domains |
| `matched_keywords` | JSONB | Which keywords triggered AI processing |
| `is_relevant` | BOOLEAN | AI confirmed fraud relevance (false = filtered out) |
| `financial_impact_estimate` | VARCHAR | Raw AI estimate e.g. `"$4.2 million"` |
| `victim_scale_raw` | VARCHAR | `"single"` / `"multiple"` / `"nationwide"` |
| `ai_model` | VARCHAR | Model that produced the analysis |
| `score_source_credibility` | INTEGER | 1–5 |
| `score_financial_impact` | INTEGER | 1–5 |
| `score_victim_scale` | INTEGER | 1–5 |
| `score_cross_source` | INTEGER | 1–5 |
| `score_trend_acceleration` | INTEGER | 1–5 |
| `signal_score_total` | INTEGER | Internal sum of 5 factors (5–25). API responses normalize this to 0–100 before exposing it (the field name in the response is also `signal_score` / `signal_score_total`, but the value is on a 0–100 scale). |
| `risk_level` | VARCHAR | Legacy `low`/`medium`/`high` band, **display-only**. Not used for filtering, badges, or publication eligibility on any endpoint. |
| `risk_band` | VARCHAR | **Canonical** V1 band: `critical` / `high` / `medium` / `below_60`. The sole source of truth for badge/filter/eligibility purposes on both the Admin and Subscriber alert APIs — materialized once at write time (pipeline scoring, manual review, or the one-time legacy-row normalization tool) and never recomputed from `signal_score_total` at read time. A `NULL` value means the row hasn't been normalized yet. |

### Migrations

```bash
alembic upgrade head        # apply all migrations
alembic downgrade -1        # roll back one migration
alembic revision --autogenerate -m "description"
```

| Revision | Description |
|----------|-------------|
| `0001` | Initial schema — all 9 tables + 10 source seed data |
| `0002` | Signal scoring — `credibility_score` on sources, 6 scoring fields on processed_alerts |
| `0003` | Fix source URLs — correct SEC/FBI RSS URLs; FTC and FinCEN converted to HTML scrapers |
| `0004` | AI columns — adds `financial_impact_estimate`, `victim_scale_raw`, `ai_model`; seeds admin user |
| `0005` | User roles — adds `role`, `full_name`, email preference flags, `last_login_at`; sets existing admin to `role='admin'` |
| `0006` | Alert publication — adds `is_published`, `published_at`, `published_by_user_id` to processed_alerts; partial index on published rows |
| `0007`–`0010` | Subscriber billing/subscriptions (Auth/Payment Phase 1) + V1 alert-publishing state |
| `0011` | `intelligence_briefs` table — Intelligence Brief module (admin CMS + subscriber library); unique `slug`/`brief_code`, btree + GIN indexes |
| `0012` | Splits `run_logs` skip telemetry into url/content/invalid counters; adds a `(source_id, run_started_at DESC)` index |
| `0013` | Durable per-source URL exclusion decisions (`source_url_decisions`); adds `run_logs.items_skipped_external` |

Current head: **`0013`** (repository and production — verified via `alembic current` against both).

---

## Intelligence Brief — Production Deployment

The Intelligence Brief module adds one dependency (`nh3`), migration `0011`, an
admin-uploaded featured-image feature served from `/uploads`, and the
`UPLOAD_DIR` setting. Deploying it on the VPS (`/opt/hiddenalerts`) requires a
rebuild (new dependency), the migration, and a persistent uploads directory.

**Persistent uploads:** `docker-compose.yml` bind-mounts
`/opt/hiddenalerts/uploads` → `/app/uploads`, and production `.env` sets
`UPLOAD_DIR=/app/uploads`. Featured images therefore live on the host and
survive `--build` rebuilds. Keep the two in sync — the container path in the
mount must equal `UPLOAD_DIR`.

### Deploy steps

```bash
# 1. Pull latest code (git repo root)
cd /opt/hiddenalerts
git pull

# Remaining commands run from the Compose project directory, where
# docker-compose.yml and .env live.
cd /opt/hiddenalerts/backend

# 2. Ensure production .env has the uploads dir
grep -q '^UPLOAD_DIR=' .env || echo 'UPLOAD_DIR=/app/uploads' >> .env
#    UPLOAD_DIR must equal the container side of the bind mount (/app/uploads).

# 3. Create the host uploads directory (parent of the module subdir)
mkdir -p /opt/hiddenalerts/uploads/intelligence-briefs

# 4. Safe permissions (do NOT use 777)
chmod -R 755 /opt/hiddenalerts/uploads

# 5. Rebuild (picks up the nh3 dependency and the /uploads mount)
docker compose up -d --build

# 6. Apply migrations
docker compose exec app alembic upgrade head

# 7. Confirm the migration applied
docker compose exec app alembic current      # -> head (0013 as of 18 August 2026; check the Migrations table above for the current value)

# 8. Health check
curl -s https://api.hiddenalerts.com/api/v1/health
```

**Nginx:** featured-image uploads are capped at **5 MB** in the app. Ensure the
API server block allows a slightly larger body so uploads aren't rejected before
reaching FastAPI:

```nginx
client_max_body_size 6M;   # api.hiddenalerts.com server block
```

There is no Nginx config tracked in this repo, so apply this manually on the VPS.
The `/uploads` path is a normal proxied GET (no special Nginx rules needed).

### Production verification

Use placeholders `<ADMIN_TOKEN>`, `<SUBSCRIBER_TOKEN>`, `<BRIEF_ID>`,
`<FILENAME>`. These are read-only or non-destructive checks.

```bash
# Health + migration
curl -s https://api.hiddenalerts.com/api/v1/health
docker compose exec app alembic current            # -> head (0013 as of 18 August 2026)

# Admin + subscriber lists reachable
curl -s "https://api.hiddenalerts.com/api/v1/admin/intelligence-briefs?limit=5" \
  -H "Authorization: Bearer <ADMIN_TOKEN>"
curl -s "https://api.hiddenalerts.com/api/v1/subscriber/intelligence-briefs?limit=5" \
  -H "Authorization: Bearer <SUBSCRIBER_TOKEN>"

# Upload a featured image, then open the returned URL against the API host
curl -sX POST "https://api.hiddenalerts.com/api/v1/admin/intelligence-briefs/<BRIEF_ID>/featured-image" \
  -H "Authorization: Bearer <ADMIN_TOKEN>" -F "file=@cover.jpg;type=image/jpeg"
#   -> open https://api.hiddenalerts.com/uploads/intelligence-briefs/<FILENAME>.jpg

# Persistence: rebuild, then re-open the same image URL (must still load)
docker compose up -d --build
```

Read-only database checks:

```bash
docker compose exec db psql -U hiddenalerts -d hiddenalerts -c "\dt intelligence_briefs"

docker compose exec db psql -U hiddenalerts -d hiddenalerts -c "
SELECT status, risk_level, COUNT(*)
FROM intelligence_briefs
GROUP BY status, risk_level
ORDER BY status, risk_level;"

docker compose exec db psql -U hiddenalerts -d hiddenalerts -c "
SELECT id, title, status, risk_level, is_featured, featured_image_url
FROM intelligence_briefs
ORDER BY id DESC
LIMIT 10;"
```

Subscriber visibility spot-check: a published Critical/High brief appears in the
subscriber list and by slug; draft/archived/Medium/Low briefs return 404 by slug
and never appear in the list. OpenAPI at `/docs` lists both the admin and
subscriber Intelligence Brief routes.

> **Docs note:** `backend/docs/` (including `INTELLIGENCE_BRIEF_API_CONTRACT.md`)
> is gitignored, so the API contract is not version-controlled by default. To
> track it, `git add -f backend/docs/INTELLIGENCE_BRIEF_API_CONTRACT.md`, or keep
> it as a shared file alongside the other V1 docs.

---

## Source Adapters

All adapters live in `app/sources/` and implement `BaseSourceAdapter`. No changes in M2 — the 10 source adapters from M1 are unchanged.

### 3-Tier HTTP Fallback

| Tier | Method | Handles |
|------|--------|---------|
| 1 | `httpx` + Chrome browser UA | Most sites |
| 2a | `requests` + bot-identifying UA | `.gov` sites with 403 (SEC, FBI) |
| 2b | `requests` + minimal headers | Aggressive WAFs |
| 3 | Playwright headless Chromium | Akamai/Cloudflare JS challenges (DOJ) |

---

## Ingestion Pipeline (M1)

`app/pipeline/collector.py` orchestrates a 2-stage flow:

```
Stage 1 — Stub fetch (1 HTTP call per source)
    adapter.fetch_item_stubs()
        └─► list of (url, title, published_at)

Pre-filter 1 — Date check
    skip if stub.published_at <= last_successful_run_at

Pre-filter 2 — URL hash batch check
    single IN query — discard known URLs

Stage 2 — Full article fetch (only for new stubs)
    fetch_full_article(url) → (raw_text, raw_html)
    compute content_hash → skip if duplicate
    INSERT raw_item
```

---

## AI Processing Pipeline (M2)

`app/pipeline/alert_pipeline.py` runs after each collection and every 30 minutes:

```
For each unprocessed raw_item (batch of 50):

Step 1 — Keyword Filter (keyword_filter.py)
    Case-insensitive word-boundary match vs source.keywords JSONB
    Zero matches → save ProcessedAlert(is_relevant=False) → skip AI

Step 2 — AI Analysis (ai_processor.py)
    POST to OpenAI GPT-4o-mini with structured output schema
    Returns: summary, primary_category, entities, financial_impact_estimate,
             victim_scale, is_relevant
    Retry up to AI_MAX_RETRIES on RateLimitError (exponential backoff)

Step 3 — Signal Scoring (signal_scorer.py)
    score_source_credibility  = source.credibility_score
    score_financial_impact    = bucket(financial_impact_estimate)
    score_victim_scale        = map(victim_scale)
    score_cross_source        = f(event_source_count)
    score_trend_acceleration  = compare keyword freq last 7d vs prior 7d
    signal_score_total        = sum(5 factors)         # internal 5–25 (in DB)
    # API exposes the same field as 0–100: round(total / 25 * 100)
    risk_band                 = critical(≥80) / high(70–79) / medium(60–69) / below_60(<60)  # canonical, written once here
    risk_level                = low(<40) / medium(40–69) / high(≥70)  # legacy, display-only, not used for publish/badge decisions

Step 4 — Event Grouping (event_grouper.py)
    Match: same primary_category + entity name overlap + within 7 days
    Hit → link alert to existing event, recalculate cross_source scores
    Miss → create new Event record
```

---

## Signal Scoring System

Each processed alert receives five independent scores (1–5 each):

| Factor | Rule |
|--------|------|
| Source Credibility | Inherited from `sources.credibility_score` — SEC/FBI/DOJ=5, FTC/FinCEN/IC3=4, Krebs/Bleeping=3 |
| Financial Impact | `<$1M`→1, `$1M–$10M`→2, `$10M–$100M`→3, `>$100M`→5; unknown/none→1 |
| Victim Scale | `single`→1, `multiple`→2, `nationwide`→4 |
| Cross-Source | 1 source→1, 2 sources→3, 3+→5 (updated as events gain more sources) |
| Trend Acceleration | Compare keyword matches last 7d vs prior 7d — stable→1, 25–99% increase→3, 100%+ surge→5 |

**Risk bands** — the DB column `signal_score_total` is on the internal 5–25
scale; every API response (public, admin, subscriber) normalizes that value to
a 0–100 score before exposing it. The field name on the response stays
`signal_score` / `signal_score_total` / `score` so no frontend change is
required. The **canonical** band is `processed_alerts.risk_band`, computed
once at write time from the score and never recomputed at read time — it is
the sole source of truth for badges, filtering, and publish eligibility on
both the Admin and Subscriber alert APIs:

| Band | API score (0–100) | DB `signal_score_total` (5–25) |
|------|-------------------|-------------------------------|
| `critical` | 80–100 | ≥20 |
| `high` | 70–79 | 18–19 |
| `medium` | 60–69 | 15–17 |
| `below_60` | <60 (or unset) | ≤14 / `NULL` |

The legacy `risk_level` column (`low`/`medium`/`high`) still exists and is
returned on some responses for backward display compatibility, but it is
**not** used for filtering, badges, or publish eligibility anywhere.

**V1 auto-publish policy (`DEFAULT_V1_POLICY`):** an alert is auto-published only when **all** conditions hold:

1. `ai_result.is_relevant == True` — AI confirmed the article describes a real fraud / financial-crime mechanism.
2. `risk_band` is `critical` or `high` — **`medium` alerts route to manual admin review, not auto-publish**; `below_60` is excluded outright. (There is no "Medium auto-publishes" rule anymore — that was an earlier, superseded policy.)
3. Effective source credibility ≥ 4 (subject to source-specific rule overrides — see `app/pipeline/publishing/source_rules.py`).
4. `primary_category` is in the auto-publish allowlist:
   `Investment Fraud`, `Cybercrime`, `Consumer Scam`, `Money Laundering`, `Cryptocurrency Fraud`.

`Other` and any unknown / borderline category **never auto-publish** — they go to manual admin review. Manual admin approval remains available for any alert (including `Other`, `medium`, and `below_60`) via the Admin review workflow in the React Admin UI (there is no server-rendered dashboard anymore).

---

## Admin Dashboard

Alert review, source monitoring and the Intelligence Brief CMS are served by the React Admin UI against the Internal-JWT Admin APIs (`/api/v1/alerts`, `/api/v1/events`,
`/api/v1/sources*`, `/api/v1/admin/*`).

Shared Internal JWT authentication is unchanged — `POST /api/v1/auth/login`,
`GET /api/v1/auth/me` and `POST /api/v1/auth/change-password` all remain.


## API Endpoints

Base URL: `http://localhost:8000`  
Authenticated endpoints accept either a valid `access_token` cookie **or** an `Authorization: Bearer <token>` header. Cookie takes priority when both are present.

> **Subscriber vs internal endpoints:**  
> `/api/v1/subscriber/alerts` and `/api/v1/subscriber/alerts/{id}` (Supabase JWT + active subscription) are the
> **subscriber-safe** published feed to use in the frontend — see the Subscriber Feed table below.
> `/api/v1/client/alerts` and `/api/v1/client/alerts/{id}` are a retained **transitional internal** API with no known
> frontend consumer, hidden from Swagger (`include_in_schema=False`) — do not build against these.
> `/api/v1/alerts` and `/api/v1/alerts/{id}` are **internal, any-authenticated-user** endpoints — they return all
> alerts regardless of publication state and expose internal review and scoring fields. Auth is `get_current_user`
> (a valid JWT cookie/Bearer token), **not** role-gated to admins specifically today — see the note in
> `MVP-API-Contract-V2.md` §3. That's a distinct guard from the `/api/v1/admin/*`, Sources, Raw Items and Stats
> routes below, which do require the `admin` role (`require_admin`).

### System

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/health` | No | DB + scheduler status |
| `GET` | `/api/v1/stats` | Admin (`require_admin`) | Item counts by source + totals |

### Sources

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/sources` | Admin (`require_admin`) | List all sources |
| `GET` | `/api/v1/sources/{id}` | Admin (`require_admin`) | Single source detail |
| `PATCH` | `/api/v1/sources/{id}` | Admin (`require_admin`) | Update `is_active` or polling interval |
| `GET` | `/api/v1/sources/{id}/runs` | Admin (`require_admin`) | Recent run logs |
| `POST` | `/api/v1/sources/{id}/trigger` | Admin (`require_admin`) | Manual collection run (202) |

### Raw Items

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/raw-items` | Admin (`require_admin`) | Paginated items (filter: source_id, since, is_duplicate) |
| `GET` | `/api/v1/raw-items/{id}` | Admin (`require_admin`) | Full detail incl. raw_text + raw_html |

### Public Feed — No Auth Required

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/alerts` | No | Landing Page marketing teaser — max 3 items, Critical/High only (by stored `risk_band`), narrow field set (`title`, `risk_band`, `category`, `published_at`, `summary`) — not a general paginated feed |

> **Retired by 06 August 2026.** `GET /api/alerts/top`, `GET /api/alerts/{id}`,
> `GET /api/alerts/stats` and `GET /api/search/alerts` were **removed** and now
> return 404. They had no frontend caller. Their protected replacements are
> below.

### Subscriber Feed — Supabase token + active subscription

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/subscriber/alerts` | Supabase + subscription | Paginated published feed with the V1 `risk_band`; filters `risk_band` (critical/high/medium/below_60 — the only risk filter, no `risk_level`), `category`, `source`, `published_from`/`published_to`, `source_published_from`/`source_published_to` |
| `GET` | `/api/v1/subscriber/alerts/{alert_id}` | Supabase + subscription | Enriched alert detail (replaces the public detail route) |
| `GET` | `/api/v1/subscriber/alerts/top` | Supabase + subscription | Top Alerts This Week — Critical/High, rolling 7 days, max 3 |
| `GET` | `/api/v1/subscriber/alerts/stats` | Supabase + subscription | Aggregate counts with V1 bands (`critical_count`) |
| `GET` | `/api/v1/subscriber/search/alerts` | Supabase + subscription | Free-text search (replaces the public search route) |
| `GET` | `/api/v1/subscriber/alerts/categories` | Supabase + subscription | Canonical categories with published-scoped counts |
| `GET` | `/api/v1/subscriber/me` · `/access` | Supabase | Profile and subscription state |
| `GET` | `/api/v1/subscriber/intelligence-briefs` | Supabase + subscription | Brief library |
| `GET` | `/api/v1/subscriber/intelligence-briefs/featured` | Supabase + subscription | The single featured Brief (404 when none) |
| `GET` | `/api/v1/subscriber/intelligence-briefs/{slug}` | Supabase + subscription | Brief detail |

### Admin metadata and monitoring — Internal JWT (admin)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/admin/alerts/categories` | Canonical categories, counts across all processed alerts |
| `GET` | `/api/v1/admin/sources/health` | Per-source health for every configured source |
| `GET` | `/api/v1/admin/sources/{source_id}/health` | One source's health plus recent runs |
| `GET` | `/api/v1/admin/system/health-summary` | Instance-wide collection health, scheduler state, Alembic revision |
| `GET`/`POST` | `/api/v1/admin/intelligence-briefs*` | Brief CMS — CRUD, publish, archive, feature, unfeature, featured-image |

### Client APIs — Internal JWT (`require_subscriber_or_admin`), retained

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/client/alerts` | Client alert list |
| `GET` | `/api/v1/client/alerts/{alert_id}` | Client alert detail |


> Detail-endpoint conventions (now `GET /api/v1/subscriber/alerts/{alert_id}`):
> `risk_level` and `confidence` are returned in
> Title Case (`"High"|"Medium"|"Low"`); `published_date` resolves in priority
> order `source_published_at` → `published_at` → `processed_at`. See
> `MVP-API-Contract-V2.md` §0.2 for the full schema.

> Search-endpoint conventions (now `GET /api/v1/subscriber/search/alerts`):
> `q` is trimmed and required (empty/whitespace
> → 422). `limit > 100` and `group_limit > 50` are clamped (200 OK), values
> `< 1` are rejected with 422. `min_score` is on the same 0–100 scale used
> elsewhere; default 0 returns all matching published alerts (low + medium +
> high). Multi-word queries are matched as a literal phrase — no fuzzy /
> typo / semantic search. An alert tagged with multiple matching entities
> appears in multiple entity groups; `total_alerts` counts unique alerts.

### Alerts (M2)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/alerts` | Yes | List alerts (filter: `risk_band` — no `risk_level` filter — plus `category`, `source_id`, `since`, `is_published`, `publish_decision`, and more; see `MVP-API-Contract-V2.md` §3.1) |
| `GET` | `/api/v1/alerts/{id}` | Yes | Alert detail with score breakdown |
| `POST` | `/api/v1/alerts/process` | Yes | Manually trigger AI pipeline (202) |
| `POST` | `/api/v1/alerts/{id}/review` | Yes | Submit review action |

### Events (M2)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/events` | Yes | List fraud events with source counts |
| `GET` | `/api/v1/events/{id}` | Yes | Event detail with linked alerts |

### Auth (M3)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/auth/login` | No | JSON login — returns JWT + sets cookie; works for both roles |
| `GET` | `/api/v1/auth/me` | Yes | Current user profile (cookie or Bearer) |
| `POST` | `/api/v1/auth/change-password` | Yes | Update password (validates current first) |

### Client — Subscriber-Safe Feed (M3)

> **Hidden from Swagger, no known frontend consumer.** Kept for backward compatibility only — do not build new
> frontend work against this table. `GET /api/v1/subscriber/alerts*` (above) is the real subscriber path. Unlike the
> Admin and Subscriber alert APIs, this legacy route still accepts a `risk_level` filter alongside `risk_band` — that
> is specific to this one retained internal route, not the current contract described elsewhere in this document.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/client/alerts` | Subscriber or Admin | Published alert feed — filters: risk_level, category, source, limit, offset |
| `GET` | `/api/v1/client/alerts/{id}` | Subscriber or Admin | Published alert detail; 404 if unpublished |

Full interactive docs at `http://localhost:8000/docs`.

---

## Scheduler

APScheduler (`AsyncIOScheduler`) starts automatically when `SCHEDULER_ENABLED=true`.

| Job | Trigger | What it does |
|-----|---------|--------------|
| `collect_all_sources` | Every 6 hours | Runs all 10 source adapters; writes new raw_items; calls processing pipeline when new items found |
| `process_new_alerts` | Every 30 minutes | Runs AI pipeline on any unprocessed raw_items |

Both jobs use `max_instances=1` — parallel runs are prevented.

```bash
# Disable scheduler during development
SCHEDULER_ENABLED=false uvicorn app.main:app --reload --port 8000
```

---

## Running Tests

Tests use an in-memory SQLite database — no PostgreSQL or OpenAI key required.

```bash
pytest tests/ -v
```

**265 tests, 0 failures.** Test breakdown:

| File | Tests | What it covers |
|------|-------|---------------|
| `test_normalizer.py` | 13 | URL normalization, SHA-256 hashing, text extraction, date parsing |
| `test_keyword_filter.py` | 13 | Word boundary matching, case sensitivity, multi-word phrases, deduplication |
| `test_ai_processor.py` | 8 | Mock OpenAI, rate-limit retry, max retries exhaustion, short text skip; SYSTEM_PROMPT financial-risk-intelligence scope (OFAC, sanctions, governance, liquidity, network exposure); cybercrime/organized-crime conditional relevance |
| `test_alert_pipeline.py` | 7 | Tier1 auto-publish guard (allowed category + score + credibility + is_relevant); Other category never auto-publishes; irrelevant alert never auto-publishes; manual admin can publish Other; M3 final tier1 — Medium score auto-publishes from credible source, Medium score from low-credibility source does NOT auto-publish, Low score never auto-publishes |
| `test_event_grouper.py` | 6 | Event creation, entity overlap matching, 7-day window, cross-source recalculation |
| `test_health.py` | 5 | API health, sources, raw-items, stats smoke tests |
| `test_auth.py` | 29 | Password/JWT utilities; JSON login (admin + subscriber); Bearer + cookie auth; change-password; role enforcement; inactive-account handling. Since 06 August 2026: asserts the removed Jinja `/login`, `/logout` and `/dashboard*` routes return 404 while `POST /api/v1/auth/login` still authenticates and still rejects bad credentials. |
| `test_alerts_api.py` | 21 | Auth gate, list/filter/detail, 202 trigger, 409 lock, review validation; publication state; approval publish; client feed access control |
| `test_public_alerts.py` | 71 | Public Landing feed `GET /api/alerts` (no auth, published-only, field mapping, ordering, filters, pagination). Since 06 August 2026 the shared-serializer coverage (`_to_public_read`, `_to_public_detail`, `published_stats_impl`, enrichment) runs through the retained Subscriber endpoints, plus regression tests asserting the four removed public routes return 404 — the detail check uses a known-existing alert id. |
| `test_signal_scorer.py` | 42 | All 5 scoring factors; M3 final 0–100-aligned bands (≤9 low, 10–17 medium, ≥18 high); boundary tests including the new band-shift cases (16/17 now Medium, 18 is the new High floor); recalibrated victim/financial buckets; realistic alert scenarios |
| `test_search_api.py` | 37 | Alert search via `GET /api/v1/subscriber/search/alerts` — matching across title/summary/source/parsed entities (case-insensitive, partial, multi-word literal phrase), unpublished excluded, entity grouping with multi-entity dedup, mixed-mode entity + keyword fallback, group ordering, `alertCount`/`sourceCount`, `group_limit` cap, `signal_score` DESC + recency tiebreaker, `min_score` boundaries, clamping and 422s. The public `/api/search/alerts` route was removed on 06 August 2026; these assertions were repointed to the subscriber route and one asserts the old path now 404s. |
| **Total** | **265** | |

---

## Testing the AI Pipeline

Unit tests mock OpenAI and use SQLite — they don't make real API calls or require PostgreSQL. To verify the full end-to-end AI pipeline against real data, use the included test script.

### `run_pipeline_test.py`

Processes a configurable number of unprocessed `raw_items` through the full pipeline (keyword filter → OpenAI → signal scoring → event grouping) and prints a results summary.

**Prerequisites:** PostgreSQL running, `.env` configured with a valid `OPENAI_API_KEY`, and `raw_items` already collected (run the ingestion pipeline first).

```bash
conda activate HiddenAlerts

# Process 5 items (safe starting point — uses ~5 OpenAI calls)
python run_pipeline_test.py --limit 5

# Process 50 items (one full scheduler batch)
python run_pipeline_test.py --limit 50
```

**Expected output:**

```
=== HiddenAlerts — Pipeline Test (5 items) ===

INFO  app.pipeline.alert_pipeline — Alert pipeline: starting processing run
INFO  app.pipeline.alert_pipeline — Alert pipeline: processing 5 unprocessed items
INFO  httpx — HTTP Request: POST https://api.openai.com/v1/chat/completions "HTTP/1.1 200 OK"
INFO  httpx — HTTP Request: POST https://api.openai.com/v1/chat/completions "HTTP/1.1 200 OK"
INFO  app.pipeline.alert_pipeline — raw_item 8 → alert 9 [MEDIUM score=12]
INFO  app.pipeline.alert_pipeline — raw_item 11 → alert 11 [HIGH score=20]
INFO  app.pipeline.alert_pipeline — Alert pipeline complete: examined=5, processed=2, ...

=== Results ===
  Items examined       : 5
  Processed (relevant) : 2
  Skipped (no keywords): 1
  Skipped (AI said no) : 2
  Failed               : 0
```

> **Note on score values in CLI / internal logs:** the `score=` value in
> pipeline log lines is the raw internal `signal_score_total` on the 5–25
> scale (12 above maps to risk_score 48 → Medium; 20 maps to 80 → High).
> Public, admin, and subscriber API responses always normalize to the 0–100
> frontend scale (Ken-approved M3 final). Logs show internal sums; APIs and
> UIs show 0–100. Risk band cutoffs on the internal scale: ≤9 Low, 10–17
> Medium, ≥18 High.

**Understanding the results:**

| Line | Meaning |
|------|---------|
| `Processed (relevant)` | Passed keyword filter AND AI confirmed fraud — shown in dashboard |
| `Skipped (no keywords)` | No source keywords matched — no OpenAI call made (cost gate working correctly) |
| `Skipped (AI said no)` | Keywords matched but AI judged the article as non-fraud |
| `Failed` | Unrecoverable errors (OpenAI failure after retries, DB error) — should be 0 |

**Expected ratios** — with 790 articles from 10 government/security sources:
- ~20–40% relevant (confirmed fraud alerts)
- ~30–50% keyword-skipped (general agency news)
- ~20–40% AI-filtered (keyword matched but content not fraud-relevant)

The script never re-processes the same item twice — each run picks up the next batch of unprocessed items.

### Verifying the Scheduler Runs Every 30 Minutes

```bash
# Check that the job was registered at startup
# Should show: "Scheduler: process_new_alerts every 30min"
grep -i "scheduler\|process_new" app.log

# Watch live for the scheduler firing
uvicorn app.main:app --reload --port 8000 2>&1 | grep -E "pipeline|scheduled"
```

Every 30 minutes you should see:
```
Alert pipeline: scheduled processing run starting
Alert pipeline complete: processed=X, no_keywords=Y, failed=0
```

`processed=0` on subsequent runs is correct — it means all items have already been processed.

### Verifying Results in the Dashboard and API

After running the script, confirm alerts appear:

```bash
# Obtain an Internal JWT, then call the Admin API with a Bearer token.
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"YOUR_ADMIN_EMAIL","password":"YOUR_ADMIN_PASSWORD"}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl "http://localhost:8000/api/v1/alerts?is_relevant=true&risk_band=high&limit=10" \
  -H "Authorization: Bearer $TOKEN"

# Alert review and source monitoring are served by the React Admin UI against
# these APIs. The legacy Jinja dashboard was removed on 06 August 2026.
```

---

## Milestone Roadmap

| Milestone | Scope | Status |
|-----------|-------|--------|
| **M1** | Source ingestion (10 sources), raw storage, deduplication, run logging, REST API | ✅ Complete |
| **M2** | Keyword filtering, AI analysis (GPT-4o-mini), 5-factor signal scoring, event grouping, admin dashboard | ✅ Complete |
| **M3 — Slice 1** | Role-aware auth foundation (admin/subscriber roles, Bearer token support, JSON auth endpoints) | ✅ Complete |
| **M3 — Slice 2** | Alert publication workflow — Tier 1 auto-publish, Tier 2 admin review, subscriber-safe client feed | ✅ Complete |
| **M3 — Slice 3** | Signal score recalibration — stricter HIGH threshold, recalibrated victim/financial buckets, re-scoring script | ✅ Complete |
| **M3 — Slice 4** *(historical implementation, retired by 06 August 2026)* | Public read-only alert detail + stats — GET /api/alerts/{id}, GET /api/alerts/stats, category breakdown | ✅ Complete |
| **M3 — Top Alerts + Inclusion Criteria** *(historical implementation, retired by 06 August 2026)* | GET /api/alerts/top with score≥15 / strength / credibility / recency ranking + duplicate-entity suppression; AI prompt extended with financial-risk-intelligence scope (OFAC, sanctions, governance, liquidity, network exposure); cybercrime/organized-crime conditional relevance; defensive `is_relevant` guard on auto-publish; agency stoplist excludes FBI/DOJ/SEC/etc. from entity dedup so unrelated alerts no longer collapse together | ✅ Complete |
| **M3 — Public-feed cleanup** | Off-topic legacy alerts (CSAM / terrorism / weapons / drug-trafficking) reviewed and unpublished manually; `audit_offtopic_alerts.py` reports the live feed as clean; new pipeline guards prevent these from re-publishing | ✅ Complete |
| **M3 — QA + VPS deployment handoff** | Backend deployed on VPS, smoke tests green, public endpoints verified live, frontend handoff docs updated | ✅ Complete |
| **M3 — Risk score normalization (0–100)** | API responses now expose `signal_score` / `signal_score_total` / `score` on a 0–100 scale (normalized server-side from the internal 5–25 sum). No frontend change required. `risk_level` derived from the 0–100 value with Ken-approved bands (≥70 high, 40–69 medium, 1–39 low). Tier 1 auto-publish gate moved from ≥16 to ≥10 so Medium-and-above auto-publishes. Admin and client mappers re-derive `risk_level` so legacy stored values stay consistent with the displayed value. Admin Jinja templates updated to show 0–100 too. | ✅ Complete |
| **M3 — Slice 5** | Full-text search across alerts | ✅ Complete |
| **Auth/Payment Phase 1 — Slice 1** | DB + config foundation for Supabase Auth + Stripe subscriptions: new `subscriber_profiles`, `subscriptions`, `stripe_webhook_events` tables (migration `0007`); new Supabase / Stripe / billing settings on `app/config.py` (all secrets default to empty); pure `has_active_subscription_access` helper encoding the access matrix; Pydantic schemas for `/subscriber/me` and `/billing/*` ready for later slices. No endpoints exposed yet; no public behavior changed. | ✅ Complete |
| **Auth/Payment Phase 1 — Slice 2** | Supabase JWT validation (JWKS fetch + 10-minute cache, RS256/ES256) in `app/auth/supabase.py`. `app/auth.py` converted to package — admin auth unchanged. `get_current_subscriber` dependency upserts a `SubscriberProfile` on first sight of a Supabase user (refreshes `last_seen_at` and email on every request). New router `/api/v1/subscriber/*` with `GET /me` (identity + access state) and `GET /access` (lightweight route-guard helper). No content gated yet; existing public endpoints unchanged. | ✅ Complete |
| **Auth/Payment Phase 1 — Slice 3** | Stripe checkout + customer portal + local billing status. New `app/services/stripe_service.py` wraps the sync Stripe SDK via `anyio.to_thread.run_sync` (customer create-or-reuse, checkout session with subscription mode + metadata, portal session). New router `/api/v1/billing/*` with `POST /checkout` (creates Stripe customer on first call and persists `stripe_customer_id`), `POST /portal`, and read-only `GET /status` (local DB only — webhook sync ships in Slice 4). Checkout/portal URLs fall back to `{FRONTEND_BASE_URL}/billing/success`, `/pricing`, `/account/billing` when the explicit Stripe URLs aren't set. CORS extended to `GET, POST, OPTIONS` and locked to `FRONTEND_BASE_URL` when configured. Supabase validator hardened with an RS256/ES256 algorithm allowlist — HS256 and `alg: "none"` are rejected before signature verification. | ✅ Complete |
| **Auth/Payment Phase 1 — Slice 4** | Stripe webhook sync — `POST /api/v1/stripe/webhook` (no auth; signature-verified via `STRIPE_WEBHOOK_SECRET`). New `app/services/stripe_webhook_service.py` is the trusted writer for the `subscriptions` table: idempotent on `stripe_event_id` (pre-SELECT + claim-by-insert race handling), dispatches `checkout.session.completed`, `customer.subscription.created/updated/deleted`, `invoice.payment_failed/succeeded`; unknown events stored + ignored. Maps Stripe objects to local profiles via `client_reference_id` / metadata / customer-id fallback; upserts by `stripe_subscription_id`; plan_type derived from configured price IDs. Returns `{status: processed\|duplicate\|ignored}`. Billing status now flips to active automatically once events arrive. | ✅ Complete |
| **Auth/Payment Phase 1 — Slice 5** | Backend-enforced paid content. New `require_active_subscription` guard (`app/auth/subscriber_access.py`) = valid Supabase token + active subscription (`has_active_subscription_access`, now with optional `subscription_access_grace_seconds`). New subscriber content endpoints `GET /api/v1/subscriber/{alerts, alerts/top, alerts/{id}, alerts/stats, search/alerts}` — all gated, returning **only published** alerts with response shapes identical to the public endpoints (the public handler bodies were extracted into shared `*_impl` functions; public routes now delegate, behavior unchanged). 401 = no/invalid token, 403 `active_subscription_required` = logged-in-but-unpaid, 404 = absent/unpublished. Old public endpoints remain unchanged and unauthenticated. | ✅ Complete |
| **Auth/Payment Phase 1 — Slice 6** | Webhook hotfix + payment reliability. `process_stripe_event` now normalizes real `stripe.Event` / `StripeObject` via `stripe_object_to_dict` (fixes prod `AttributeError: get`); malformed events get a controlled `400 invalid_stripe_event`; events with `processed_at IS NULL` (prior crashes) are **reprocessed** instead of incorrectly skipped; dispatch failures roll back + log + re-raise so Stripe retries work. New `POST /api/v1/billing/sync` (Supabase-auth) reconciles local state from Stripe with priority `active > trialing > canceled-future > past_due > newest` — an older active row is never overwritten by a newer incomplete. `POST /api/v1/billing/checkout` now reads optional `X-Idempotency-Key`, validates it (no `@`, len ≤ 255), folds header-less double-clicks via a 30-min recent-attempt window, persists every attempt in the new `billing_checkout_attempts` table (migration `0008`), passes operation-scoped `idempotency_key` to Stripe's `Customer.create` and `Checkout.Session.create`, returns 409 `already_subscribed` for active users, 409 `idempotency_key_conflict` for cross-user reuse, 409 `checkout_in_progress` for in-flight retries. | ✅ Complete |
| **Auth/Payment Phase 1 — Slice 7+** | Lock/deprecate old public content endpoints once frontend migrates; subscriber reports/briefs; frontend integration | 🔄 Next |
| **Future / Paused** | Email alerts (HIGH immediate + MEDIUM daily digest), weekly fraud intelligence report generation | Paused — revisit after Auth/Payment ships |

---

## VPS Deployment & Testing (Hostinger)

Production runs on a Hostinger VPS at `/opt/hiddenalerts` via Docker Compose.
The app container is named `hiddenalerts_app`. Public URL:
`https://hiddenalerts.com`.

### Standard deploy (after pushing code to `main`)

SSH to the VPS, then from `/opt/hiddenalerts`:

```bash
docker compose build app

# 1. Pull latest code
git pull

# 2. Rebuild the app image and restart the container.
#    Use --no-deps so the postgres container (with live data) is NOT touched.
docker compose build app
docker compose up -d --no-deps app

# 3. Confirm the container came up cleanly
docker compose ps
docker compose logs --tail=100 app

# 4. Run the test suite inside the container
docker exec hiddenalerts_app pytest tests/ -q

# 5. Smoke-test the retained endpoints from the host
#    Public Landing feed — no authentication.
curl -s https://api.hiddenalerts.com/api/alerts | python3 -m json.tool | head -40

#    Infrastructure health — no authentication.
curl -s https://api.hiddenalerts.com/api/v1/health | python3 -m json.tool

#    Admin APIs need an Internal JWT (Bearer); Subscriber APIs need a Supabase
#    access token *and* an active subscription. The full authenticated smoke is
#    scripted — see scripts/e2e/README.md:
#      python -m scripts.e2e.production_smoke --env-file /secure/path/e2e.env

#    Removed on 06 August 2026 — these must now return 404:
#      /api/alerts/top  /api/alerts/stats  /api/alerts/{id}  /api/search/alerts
```

### Code-only changes vs. dependency / Dockerfile changes

- **Code only** (Python files, templates, docs, no `requirements.txt` /
  `Dockerfile` / `docker-compose.yml` change): step 2's
  `docker compose build app` is fast (cached layers) and step 3 restarts
  cleanly. This is the common path.
- **Dependency or Dockerfile change**: same commands; the `build` step will
  reinstall packages. Watch the build log for failures before restarting.
- **`docker-compose.yml` change**: re-run `docker compose up -d` (no
  `--no-deps`) so the orchestration picks up the new compose config.
- **Migration** (`alembic` revision added): after step 3, run
  `docker exec hiddenalerts_app alembic upgrade head`, then re-run step 4.

### Rollback if a deploy goes bad

```bash
cd /opt/hiddenalerts
git log --oneline -5                  # find the last good commit
git checkout <good-sha>
docker compose build app
docker compose up -d --no-deps app
docker exec hiddenalerts_app pytest tests/ -q
```

### Useful diagnostic commands

```bash
# Tail live application logs
docker compose logs -f app

# See the scheduler / pipeline activity
docker exec hiddenalerts_app tail -f logs/app.log    # if file-logging is on

# Open a Python shell inside the container (DB access, ad-hoc queries)
docker exec -it hiddenalerts_app python

# Run any maintenance script inside the container
docker exec hiddenalerts_app python scripts/audit_offtopic_alerts.py
docker exec hiddenalerts_app python scripts/audit_offtopic_alerts.py --json

# Postgres shell (read-only browsing — be careful with writes)
docker exec -it hiddenalerts_db psql -U hiddenalerts -d hiddenalerts

# Container resource use
docker stats --no-stream
```

### What's safe to run, what isn't

| Command | Safe? | Notes |
|---------|-------|-------|
| `docker compose build app` | Always | Builds a new image; doesn't replace the running container yet. |
| `docker compose up -d --no-deps app` | Yes | Recreates only the app container — Postgres untouched. |
| `docker compose up -d` (no `--no-deps`) | Cautious | Will recreate Postgres if its image/config changed. Don't use unless you intend that. |
| `docker compose down` | **No** | Stops everything. Only use if you mean to take the site offline. |
| `docker compose down -v` | **NEVER** | Deletes volumes — wipes the production database. |
| `docker exec hiddenalerts_app pytest tests/ -q` | Always | Tests run in isolated session-scoped SQLite, not the prod DB. |
| `docker exec hiddenalerts_app alembic upgrade head` | Yes | Idempotent; only applies pending migrations. |
| `docker exec hiddenalerts_app alembic downgrade …` | **No** without backup | Downgrades can drop columns. Take a DB dump first. |

### Quick sanity check that scoring is on the 0–100 scale (M3 final)

`GET /api/alerts` (the unauthenticated Landing Page teaser) does **not** expose `signal_score` or `risk_level` —
its field set is narrow by design (`title`, `risk_band`, `category`, `published_at`, `summary` only). Check the
canonical `risk_band` there instead, or use an authenticated endpoint for the actual score:

```bash
# Public teaser — confirms risk_band is one of the four canonical values.
curl -s https://api.hiddenalerts.com/api/alerts | python3 -c \
  "import json, sys; \
   d = json.load(sys.stdin); \
   for a in d['alerts'][:5]: print(a['risk_band'], a['title'])"

# Authenticated Admin check — should show signal_score_total values in the 0–100 range (not 5–25).
curl -s "https://api.hiddenalerts.com/api/v1/alerts?limit=5" \
  -H "Authorization: Bearer $TOKEN" | python3 -c \
  "import json, sys; \
   for a in json.load(sys.stdin): print(a['signal_score_total'], a['risk_band'])"
```

---

## Maintenance Scripts

| Script | Purpose | Default mode |
|--------|---------|--------------|
| `scripts/audit_public_alert_quality.py` | List published alerts in non-allowed categories (e.g. `Other`); unpublish by ID with `--apply --ids …` | dry-run |
| `scripts/audit_offtopic_alerts.py` | Flag published alerts whose title/summary contains off-topic terms (CSAM, terrorism, weapons, etc.) without any positive fraud term; unpublish by ID with `--apply --ids …`. Use `--json` for machine-readable output | report |
| `scripts/rescore_alerts.py` | Recompute signal scores under current thresholds | dry-run |
| `scripts/approve_alerts.py` | Bulk-publish reviewed alerts | requires explicit IDs |
