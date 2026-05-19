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
                    │  /api/v1/alerts · /api/v1/events · /dashboard    │
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
| Dashboard | Jinja2 templates + Bootstrap 5 |

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
│   │   └── dashboard.py               # M2: Jinja2 HTML routes (admin-only)
│   ├── templates/                      # Jinja2 HTML templates
│   │   ├── base.html                   # Bootstrap 5 layout + navbar
│   │   ├── auth/login.html             # Login page
│   │   └── dashboard/
│   │       ├── index.html              # HIGH/MEDIUM/LOW alert panels
│   │       ├── alert_detail.html       # Score breakdown + review form
│   │       └── monitoring.html         # Source health + run logs
│   └── static/
│       └── css/dashboard.css           # Custom dashboard styles
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
http://localhost:8000/login          → Admin dashboard login
http://localhost:8000/docs           → Swagger UI (all endpoints)
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
| `risk_level` | VARCHAR | M3 final 0–100 bands (Ken-approved May 06): `low` (1–39) / `medium` (40–69) / `high` (≥70). Public, admin, and client endpoints all derive risk from the score at read time rather than from this stored column, so legacy rows with stale levels still display correctly. |

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
    risk_level                = low(<40) / medium(40–69) / high(≥70)  # M3 final bands

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

**Risk bands (M3 final, Ken-approved May 06)** — the DB column
`signal_score_total` is on the internal 5–25 scale; every API response (public,
admin, subscriber) normalizes that value to a 0–100 score before exposing it.
The field name on the response stays `signal_score` / `signal_score_total` /
`score` so no frontend change is required. `risk_level` is derived from the
0–100 value:

| Band | API score (0–100) | DB `signal_score_total` (5–25) |
|------|-------------------|-------------------------------|
| High | 70–100 | ≥18 |
| Medium | 40–69 | 10–17 |
| Low | 1–39 | ≤9 |

**Tier 1 auto-publish rule:** an alert is auto-published only when **all four** conditions hold:

1. `ai_result.is_relevant == True` — AI confirmed the article describes a real fraud / financial-crime mechanism (defensive guard against any code path that lets an irrelevant alert reach scoring).
2. `signal_score_total ≥ 10` — Medium-and-above under M3 final bands. Ken explicitly approved Medium auto-publish on May 06; Low alerts remain admin-manual-only.
3. `source.credibility_score ≥ 4` — government / regulator / law-enforcement source.
4. `primary_category` is in the auto-publish allowlist:
   `Investment Fraud`, `Cybercrime`, `Consumer Scam`, `Money Laundering`, `Cryptocurrency Fraud`.

`Other` and any unknown / borderline category **never auto-publish** — they go to manual admin review. Manual admin approval remains available for any alert (including `Other` and below-threshold scores) via the dashboard's review workflow.

---

## Admin Dashboard

The dashboard is a Jinja2 HTML interface for reviewing fraud alerts:

| URL | Description |
|-----|-------------|
| `/login` | Login with admin email + password |
| `/logout` | Clear session cookie |
| `/dashboard` | HIGH / MEDIUM / LOW alert panels, sortable by signal score |
| `/dashboard/alerts/{id}` | Alert detail — summary, score breakdown, entities, review form |
| `/dashboard/monitoring` | Source health table + last 50 run logs |

**Authentication:** HTTP-only JWT cookie (`access_token`), 30-day expiry. Admin-only — subscribers are redirected to `/login`.

**Review workflow:** On each alert detail page, reviewers can:
- Approve the alert as accurate
- Mark it as a false positive
- Edit the AI summary
- Override the risk level

---

## API Endpoints

Base URL: `http://localhost:8000`  
Authenticated endpoints accept either a valid `access_token` cookie **or** an `Authorization: Bearer <token>` header. Cookie takes priority when both are present.

> **Subscriber vs internal endpoints:**  
> `/api/v1/client/alerts` and `/api/v1/client/alerts/{id}` are the **subscriber-safe** published feed — use these in the frontend.  
> `/api/v1/alerts` and `/api/v1/alerts/{id}` are **internal/admin** endpoints — they return all alerts regardless of publication state and expose internal review and scoring fields.

### System

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/health` | No | DB + scheduler status |
| `GET` | `/api/v1/stats` | No | Item counts by source + totals |

### Sources

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/sources` | No | List all sources |
| `GET` | `/api/v1/sources/{id}` | No | Single source detail |
| `PATCH` | `/api/v1/sources/{id}` | No | Update `is_active` or polling interval |
| `GET` | `/api/v1/sources/{id}/runs` | No | Recent run logs |
| `POST` | `/api/v1/sources/{id}/trigger` | No | Manual collection run (202) |

### Raw Items

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/raw-items` | No | Paginated items (filter: source_id, since, is_duplicate) |
| `GET` | `/api/v1/raw-items/{id}` | No | Full detail incl. raw_text + raw_html |

### Public Feed — No Auth Required (M3 Slice 4 + Frontend Completion)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/alerts` | No | Paginated published alert feed |
| `GET` | `/api/alerts/top` | No | Curated top 3 published alerts (`signal_score >= 60` on the 0–100 API scale; equivalent to internal `signal_score_total >= 15`). Ranked by score → signal-strength → credibility → recency, duplicate primary entities suppressed. Returns `{"alerts": []}` when none qualify. |
| `GET` | `/api/alerts/{id}` | No | Enriched published alert detail (`confidence`, `why_it_matters`, `key_intelligence`, `risk_assessment`, `sources`, `published_date`, `subcategory`, `affected_group`, `timeline`, `related_signals` + backward-compat aliases). Optional sections omitted when empty. 404 if unpublished. |
| `GET` | `/api/alerts/stats` | No | Published alert aggregate counts + category breakdown |
| `GET` | `/api/search/alerts` | No | Free-text search across published alerts. Required `q`; optional `min_score` (0–100, default 0), `limit` (default 50, max 100), `group_limit` (default 20, max 50). Matches title, summary, source name, and parsed entities (case-insensitive ILIKE). Returns entity-grouped results plus a unique top-level `alerts` list; non-entity matches collect into a single `keyword` fallback group. See `MVP-API-Contract-V2.md` §0.5. |

> Detail-endpoint conventions: `risk_level` and `confidence` are returned in
> Title Case (`"High"|"Medium"|"Low"`); `published_date` resolves in priority
> order `source_published_at` → `published_at` → `processed_at`. See
> `MVP-API-Contract-V2.md` §0.2 for the full schema.

> Search-endpoint conventions: `q` is trimmed and required (empty/whitespace
> → 422). `limit > 100` and `group_limit > 50` are clamped (200 OK), values
> `< 1` are rejected with 422. `min_score` is on the same 0–100 scale used
> elsewhere; default 0 returns all matching published alerts (low + medium +
> high). Multi-word queries are matched as a literal phrase — no fuzzy /
> typo / semantic search. An alert tagged with multiple matching entities
> appears in multiple entity groups; `total_alerts` counts unique alerts.

### Alerts (M2)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/v1/alerts` | Yes | List alerts (filter: risk_level, category, source_id, since) |
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
| `test_auth.py` | 24 | Password/JWT utilities; JSON login (admin + subscriber); Bearer + cookie auth; change-password; role enforcement; inactive user; backwards compat |
| `test_alerts_api.py` | 21 | Auth gate, list/filter/detail, 202 trigger, 409 lock, review validation; publication state; approval publish; client feed access control |
| `test_public_alerts.py` | 87 | Public list (no auth, published-only, field mapping, ordering, filters); enriched detail (Ken's frontend schema — confidence, why_it_matters, key_intelligence, risk_assessment with strong-factor enrichment, sources, timeline, related_signals; safe-fields-only); public stats (counts, breakdown, empty state); top alerts (no auth, published-only, max 3, score ≥15 threshold, score-then-strength-then-credibility-then-recency ranking, duplicate-entity suppression, fallback key for entity-less alerts, empty when none qualify, no internal-field leakage); agency stoplist (FBI/DOJ/SEC/etc. excluded from primary-entity dedup and entity-overlap matching); derived risk_level from score on every public endpoint; related_signals entity-overlap + 2–4 quantity rule; **M3 final score normalization to 0–100** — `signal_score` / `score` exposed as 0–100, Ken's worked examples (17→68, 19→76, 21→84), band-boundary checks at 9/10 and 17/18 |
| `test_signal_scorer.py` | 42 | All 5 scoring factors; M3 final 0–100-aligned bands (≤9 low, 10–17 medium, ≥18 high); boundary tests including the new band-shift cases (16/17 now Medium, 18 is the new High floor); recalibrated victim/financial buckets; realistic alert scenarios |
| `test_search_api.py` | 39 | GET /api/search/alerts — auth-free 200/422 envelope, matching across title/summary/source/parsed entities (case-insensitive, partial, multi-word literal phrase), unpublished excluded, entity grouping with multi-entity dedup, mixed-mode entity + keyword fallback, group ordering (entity-first), `alertCount`/`sourceCount` correctness, source-published-at earliest/latest, `group_limit` cap; `signal_score` DESC + recency-tiebreaker ranking; `min_score` 0–100 boundary checks (60 → internal 15, 70 → internal 18); `limit`/`group_limit` clamping above max + 422 below 1; no-leak frontend safety; regression on /api/alerts list/top/stats/detail |
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
# Via API (requires JWT token — log in at /login first, copy cookie)
curl "http://localhost:8000/api/v1/alerts?is_relevant=true&risk_level=high&limit=10" \
  -H "Cookie: access_token=YOUR_JWT_TOKEN"

# Dashboard: http://localhost:8000/dashboard
# HIGH/MEDIUM/LOW panels — click any alert to see score breakdown + AI summary
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
| **M3 — Slice 4** | Public read-only alert detail + stats — GET /api/alerts/{id}, GET /api/alerts/stats, category breakdown | ✅ Complete |
| **M3 — Top Alerts + Inclusion Criteria** | GET /api/alerts/top with score≥15 / strength / credibility / recency ranking + duplicate-entity suppression; AI prompt extended with financial-risk-intelligence scope (OFAC, sanctions, governance, liquidity, network exposure); cybercrime/organized-crime conditional relevance; defensive `is_relevant` guard on auto-publish; agency stoplist excludes FBI/DOJ/SEC/etc. from entity dedup so unrelated alerts no longer collapse together | ✅ Complete |
| **M3 — Public-feed cleanup** | Off-topic legacy alerts (CSAM / terrorism / weapons / drug-trafficking) reviewed and unpublished manually; `audit_offtopic_alerts.py` reports the live feed as clean; new pipeline guards prevent these from re-publishing | ✅ Complete |
| **M3 — QA + VPS deployment handoff** | Backend deployed on VPS, smoke tests green, public endpoints verified live, frontend handoff docs updated | ✅ Complete |
| **M3 — Risk score normalization (0–100)** | API responses now expose `signal_score` / `signal_score_total` / `score` on a 0–100 scale (normalized server-side from the internal 5–25 sum). No frontend change required. `risk_level` derived from the 0–100 value with Ken-approved bands (≥70 high, 40–69 medium, 1–39 low). Tier 1 auto-publish gate moved from ≥16 to ≥10 so Medium-and-above auto-publishes. Admin and client mappers re-derive `risk_level` so legacy stored values stay consistent with the displayed value. Admin Jinja templates updated to show 0–100 too. | ✅ Complete |
| **M3 — Slice 5** | Full-text search across alerts | ✅ Complete |
| **Auth/Payment Phase 1 — Slice 1** | DB + config foundation for Supabase Auth + Stripe subscriptions: new `subscriber_profiles`, `subscriptions`, `stripe_webhook_events` tables (migration `0007`); new Supabase / Stripe / billing settings on `app/config.py` (all secrets default to empty); pure `has_active_subscription_access` helper encoding the access matrix; Pydantic schemas for `/subscriber/me` and `/billing/*` ready for later slices. No endpoints exposed yet; no public behavior changed. | ✅ Complete |
| **Auth/Payment Phase 1 — Slice 2+** | Supabase JWT validation, Stripe checkout / portal / webhook endpoints, `/api/v1/subscriber/*` paid feed, access guard, frontend integration | 🔄 Next |
| **Future / Paused** | Email alerts (HIGH immediate + MEDIUM daily digest), weekly fraud intelligence report generation | Paused — revisit after Auth/Payment ships |

---

## VPS Deployment & Testing (Hostinger)

Production runs on a Hostinger VPS at `/opt/hiddenalerts` via Docker Compose.
The app container is named `hiddenalerts_app`. Public URL:
`https://hiddenalerts.com`.

### Standard deploy (after pushing code to `main`)

SSH to the VPS, then from `/opt/hiddenalerts`:

```bash
cd /opt/hiddenalerts

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

# 5. Smoke-test the public endpoints from the host
curl -s https://hiddenalerts.com/api/alerts        | python3 -m json.tool | head -40
curl -s https://hiddenalerts.com/api/alerts/top    | python3 -m json.tool
curl -s https://hiddenalerts.com/api/alerts/stats  | python3 -m json.tool
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

```bash
# Should show signal_score values in the 40–95 range (not 5–25).
curl -s https://hiddenalerts.com/api/alerts | python3 -c \
  "import json, sys; \
   d = json.load(sys.stdin); \
   for a in d['alerts'][:5]: print(a['signal_score'], a['risk_level'])"
```

---

## Maintenance Scripts

| Script | Purpose | Default mode |
|--------|---------|--------------|
| `scripts/audit_public_alert_quality.py` | List published alerts in non-allowed categories (e.g. `Other`); unpublish by ID with `--apply --ids …` | dry-run |
| `scripts/audit_offtopic_alerts.py` | Flag published alerts whose title/summary contains off-topic terms (CSAM, terrorism, weapons, etc.) without any positive fraud term; unpublish by ID with `--apply --ids …`. Use `--json` for machine-readable output | report |
| `scripts/rescore_alerts.py` | Recompute signal scores under current thresholds | dry-run |
| `scripts/approve_alerts.py` | Bulk-publish reviewed alerts | requires explicit IDs |
