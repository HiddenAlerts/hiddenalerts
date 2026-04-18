# HiddenAlerts — MVP API Contract

**Version:** 1.0 (Milestone 1 & 2 — April 11, 2026)  
**Base URL (production):** `https://api.hiddenalerts.com`
**Base URL (dashboard):** `https://hiddenalerts.com/dashboard`
**Interactive API docs:** `https://api.hiddenalerts.com/docs` (Swagger UI — test every endpoint live)  
**Authentication:** JWT stored in an HTTP-only cookie named `access_token`

---

## Table of Contents

1. [Authentication](#1-authentication)
2. [System Endpoints](#2-system-endpoints)
3. [Alerts](#3-alerts)
4. [Events](#4-events)
5. [Sources](#5-sources)
6. [Raw Items](#6-raw-items)
7. [Schema Reference](#7-schema-reference)
8. [Signal Scoring System](#8-signal-scoring-system)
9. [Fraud Categories](#9-fraud-categories)
10. [Source Registry](#10-source-registry)
11. [Error Reference](#11-error-reference)
12. [Frontend Quick-Start](#12-frontend-quick-start)
13. [Roadmap](#13-roadmap)

---

## 1. Authentication

### How it works

All `/api/v1/alerts`, `/api/v1/events`, and `/api/v1/alerts/process` endpoints require a valid session. The token is a signed JWT stored in an HTTP-only cookie named `access_token`. There is currently one admin user (seeded during deployment).

### Login

```
POST /login
Content-Type: application/x-www-form-urlencoded
```

**Form fields**

| Field | Required | Description |
|-------|----------|-------------|
| `username` | Yes | Admin email address |
| `password` | Yes | Admin password |

**Success response:** `302 Found` — redirects to `/dashboard` and sets the `access_token` cookie.

**Failure response:** `401 Unauthorized` — re-renders the login page with an error message.

**Curl example:**
```bash
curl -c cookies.txt -X POST https://hiddenalerts.com/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=ken@hiddenalerts.com&password=yourpassword"
```

### Using the token for API calls

For **browser clients:** the cookie is set automatically on login and sent on every subsequent request. No extra headers needed.

For **API / non-browser clients:** extract the cookie value from the login response and send it as a header on every authenticated request:

```http
Cookie: access_token=<jwt_value>
```

**Curl example with saved cookie jar:**
```bash
# Login and save cookie
curl -c cookies.txt -X POST https://hiddenalerts.com/login \
  -d "username=ken@hiddenalerts.com&password=yourpassword"

# Use saved cookie on subsequent API calls
curl -b cookies.txt "https://api.hiddenalerts.com/api/v1/alerts?risk_level=high"
```

### Logout

```
GET /logout
```

Clears the `access_token` cookie and redirects to `/login`. No request body needed.

### Token details

| Property | Value |
|----------|-------|
| Cookie name | `access_token` |
| Algorithm | `HS256` |
| Payload | `{"sub": "<user_id>", "exp": <unix_timestamp>}` |
| Expiry | 30 days from login |
| Storage | HTTP-only, `SameSite=Lax` |

> **M3 note:** `Authorization: Bearer <token>` header support is planned for Milestone 3 to support cross-domain frontends.

---

## 2. System Endpoints

### 2.1 Health Check

Returns application status, database connectivity, and scheduler state.

```
GET /api/v1/health
```

**Authentication:** None required.

**Response** `200 OK`
```json
{
  "status": "ok",
  "env": "production",
  "database": "connected",
  "scheduler": "running"
}
```

| Field | Values | Description |
|-------|--------|-------------|
| `status` | `"ok"` / `"degraded"` | `"degraded"` if the database is unreachable |
| `env` | `"production"` / `"development"` | Matches `APP_ENV` in server config |
| `database` | `"connected"` / `"unavailable"` | Live PostgreSQL connectivity check |
| `scheduler` | `"running"` / `"stopped"` | APScheduler state (collection every 6h + AI processing every 30min) |

---

### 2.2 Statistics

Returns article counts by source and overall totals.

```
GET /api/v1/stats
```

**Authentication:** None required.

**Response** `200 OK`
```json
{
  "total_raw_items": 790,
  "unique_items": 790,
  "total_sources": 10,
  "active_sources": 10,
  "items_per_source": [
    { "source": "BleepingComputer", "item_count": 52 },
    { "source": "DOJ Press Releases", "item_count": 12 },
    { "source": "FBI National Press Releases", "item_count": 299 }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `total_raw_items` | integer | Total rows in `raw_items` table |
| `unique_items` | integer | Non-duplicate items (`is_duplicate = false`) |
| `total_sources` | integer | Total configured sources |
| `active_sources` | integer | Sources with `is_active = true` |
| `items_per_source` | array | Per-source article counts (all 10 sources, alphabetical) |

---

## 3. Alerts

> All alert endpoints require authentication (`Cookie: access_token=<jwt>`).

### 3.1 List Alerts

Returns a paginated list of processed fraud alerts, newest first.

```
GET /api/v1/alerts
```

**Query Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `risk_level` | string | — | `low`, `medium`, or `high` |
| `category` | string | — | Exact match on fraud category — see [§9 Fraud Categories](#9-fraud-categories) |
| `source_id` | integer | — | Filter by numeric source ID |
| `source` | string | — | Partial, case-insensitive match on source name (e.g. `FBI` matches all three FBI sources) |
| `keyword` | string | — | Case-insensitive substring match against article title OR matched keywords list |
| `start_date` | datetime | — | Only alerts processed **on or after** this datetime (ISO 8601, e.g. `2026-04-01T00:00:00Z`) |
| `end_date` | datetime | — | Only alerts processed **on or before** this datetime |
| `is_relevant` | boolean | — | `true` = AI-confirmed fraud alerts only (recommended for most frontend views) |
| `limit` | integer | `50` | Results per page — max `500` |
| `offset` | integer | `0` | Pagination offset |

**Example — high-risk alerts from the SEC in the last week:**
```
GET /api/v1/alerts?source=SEC&risk_level=high&is_relevant=true&start_date=2026-04-04T00:00:00Z&limit=20
```

**Response** `200 OK` — array of [`ProcessedAlertRead`](#processedAlertRead)

```json
[
  {
    "id": 42,
    "raw_item_id": 187,
    "title": "SEC Charges Investment Adviser with $4.2M Fraud Scheme",
    "source_name": "SEC Press Releases",
    "item_url": "https://www.sec.gov/news/press-releases/2026/...",
    "risk_level": "high",
    "primary_category": "Investment Fraud",
    "signal_score_total": 18,
    "relevance_score": 0.72,
    "matched_keywords": ["fraud", "charges", "investment adviser"],
    "is_relevant": true,
    "processed_at": "2026-04-05T14:22:31Z"
  }
]
```

**Notes:**
- Returns both relevant (`is_relevant=true`) and filtered-out (`is_relevant=false`) alerts by default. Always pass `is_relevant=true` unless you specifically need to see filtered items.
- Results are ordered by `processed_at` descending (newest first).
- `relevance_score` is a convenience field — `signal_score_total / 25` — normalized to 0.0–1.0. Use `signal_score_total` for precise sorting and `risk_level` for categorical display.

---

### 3.2 Get Alert Detail

Returns the full detail for a single alert including AI summary, score breakdown, named entities, event linkage, and latest review status.

```
GET /api/v1/alerts/{id}
```

**Path Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | integer | Alert ID from the list endpoint |

**Response** `200 OK` — [`ProcessedAlertDetail`](#processedAlertDetail)

```json
{
  "id": 42,
  "raw_item_id": 187,
  "title": "SEC Charges Investment Adviser with $4.2M Fraud Scheme",
  "source_name": "SEC Press Releases",
  "item_url": "https://www.sec.gov/news/press-releases/2026/...",
  "risk_level": "high",
  "primary_category": "Investment Fraud",
  "secondary_category": null,
  "signal_score_total": 18,
  "relevance_score": 0.72,
  "matched_keywords": ["fraud", "charges", "investment adviser"],
  "is_relevant": true,
  "processed_at": "2026-04-05T14:22:31Z",
  "summary": "The SEC charged a registered investment adviser with defrauding clients of $4.2 million over three years. The adviser falsified account statements and diverted client funds to personal accounts. The complaint seeks disgorgement and civil penalties. Three elderly clients were affected. The adviser is barred from the industry pending litigation.",
  "entities_json": {
    "names": ["John Smith", "Smith Capital Advisors LLC", "SEC"]
  },
  "financial_impact_estimate": "$4.2 million",
  "victim_scale_raw": "multiple",
  "ai_model": "gpt-4o-mini-2024-07-18",
  "score_source_credibility": 5,
  "score_financial_impact": 3,
  "score_victim_scale": 3,
  "score_cross_source": 3,
  "score_trend_acceleration": 4,
  "event_id": 7,
  "event_title": "Smith Capital Advisors Fraud Investigation",
  "review_status": null
}
```

**Error responses**

| Code | Description |
|------|-------------|
| `401 Unauthorized` | Missing or invalid `access_token` cookie |
| `404 Not Found` | No alert with this ID |

---

### 3.3 Trigger AI Processing Pipeline

Manually triggers the AI processing pipeline to process any unprocessed raw items. Runs in the background — returns immediately.

```
POST /api/v1/alerts/process
```

**Request body:** None.

**Response** `202 Accepted`
```json
{
  "message": "Alert processing started",
  "status": "accepted"
}
```

**Response** `409 Conflict` — if a pipeline run is already in progress:
```json
{
  "detail": "Processing already in progress"
}
```

> **Note:** The pipeline also runs automatically every 30 minutes and immediately after each source collection run. This endpoint is for on-demand triggering only. Monitor progress in server logs or check `/api/v1/stats` to track new alert counts.

---

### 3.4 Submit Alert Review

Submit a human review decision on an alert. Reviews are stored in history — each review is appended, not overwritten. The alert's `review_status` field reflects the most recent review.

```
POST /api/v1/alerts/{id}/review
Content-Type: application/json
```

**Path Parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | integer | Alert ID to review |

**Request Body** — [`AlertReviewCreate`](#alertReviewCreate)

```json
{
  "review_status": "approved",
  "edited_summary": null,
  "adjusted_risk_level": null
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `review_status` | string | Yes | `"approved"` — confirmed fraud alert; `"false_positive"` — not fraud; `"edited"` — content corrected |
| `edited_summary` | string | No | If provided, replaces the AI-generated summary on the alert |
| `adjusted_risk_level` | string | No | Override the computed risk level: `"low"`, `"medium"`, or `"high"` |

**Response** `200 OK` — [`AlertReviewRead`](#alertReviewRead)

```json
{
  "id": 15,
  "alert_id": 42,
  "user_id": 1,
  "review_status": "approved",
  "edited_summary": null,
  "adjusted_risk_level": null,
  "reviewed_at": "2026-04-05T16:00:00Z"
}
```

**Error responses**

| Code | Description |
|------|-------------|
| `401 Unauthorized` | Missing or invalid token |
| `404 Not Found` | Alert ID does not exist |
| `422 Unprocessable Entity` | `review_status` is not one of the three valid values |

---

## 4. Events

> All event endpoints require authentication.

Events group related alerts from multiple sources that report the same underlying fraud story. An event is created automatically when a new alert shares a `primary_category` and entity overlap with an existing event within 7 days.

### 4.1 List Events

```
GET /api/v1/events
```

**Query Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `category` | string | — | Exact match on fraud category |
| `risk_level` | string | — | `low`, `medium`, or `high` |
| `limit` | integer | `50` | Max `200` |
| `offset` | integer | `0` | Pagination offset |

**Response** `200 OK` — array of [`EventRead`](#eventRead)

```json
[
  {
    "id": 7,
    "title": "Smith Capital Advisors: Investment Fraud",
    "risk_level": "high",
    "category": "Investment Fraud",
    "primary_entity": "Smith Capital Advisors LLC",
    "first_detected_at": "2026-04-04T09:15:00Z",
    "last_updated_at": "2026-04-05T14:22:31Z",
    "source_count": 3
  }
]
```

Results are ordered by `last_updated_at` descending (most recently active first).

---

### 4.2 Get Event Detail

Returns an event with all its linked alerts.

```
GET /api/v1/events/{id}
```

**Response** `200 OK` — [`EventDetail`](#eventDetail)

```json
{
  "id": 7,
  "title": "Smith Capital Advisors: Investment Fraud",
  "risk_level": "high",
  "category": "Investment Fraud",
  "primary_entity": "Smith Capital Advisors LLC",
  "first_detected_at": "2026-04-04T09:15:00Z",
  "last_updated_at": "2026-04-05T14:22:31Z",
  "source_count": 3,
  "alerts": [
    {
      "id": 42,
      "title": "SEC Charges Investment Adviser with $4.2M Fraud Scheme",
      "source_name": "SEC Press Releases",
      "risk_level": "high",
      "signal_score_total": 18,
      "relevance_score": 0.72,
      "matched_keywords": ["fraud", "charges"],
      "is_relevant": true,
      "processed_at": "2026-04-05T14:22:31Z"
    },
    {
      "id": 38,
      "title": "DOJ Opens Criminal Probe into Smith Capital",
      "source_name": "DOJ Press Releases",
      "risk_level": "high",
      "signal_score_total": 20,
      "relevance_score": 0.80,
      "matched_keywords": ["criminal", "fraud", "probe"],
      "is_relevant": true,
      "processed_at": "2026-04-04T09:15:00Z"
    }
  ]
}
```

**Error responses**

| Code | Description |
|------|-------------|
| `401 Unauthorized` | Missing or invalid token |
| `404 Not Found` | Event ID does not exist |

---

## 5. Sources

> No authentication required for source endpoints.

### 5.1 List Sources

```
GET /api/v1/sources
```

**Response** `200 OK` — array of [`SourceRead`](#sourceRead) ordered by source ID.

---

### 5.2 Get Source

```
GET /api/v1/sources/{id}
```

**Response** `200 OK` — [`SourceRead`](#sourceRead)

**Error:** `404 Not Found` if source does not exist.

---

### 5.3 Update Source

Enable/disable a source or change its polling interval.

```
PATCH /api/v1/sources/{id}
Content-Type: application/json
```

**Request Body** — only include fields you want to change:

```json
{
  "is_active": false,
  "polling_frequency_minutes": 120,
  "notes": "Temporarily disabled — too noisy"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `is_active` | boolean | Enable or disable collection for this source |
| `polling_frequency_minutes` | integer | How often to check this source (scheduler reads this value) |
| `notes` | string | Internal notes — visible in dashboard monitoring view |

**Response** `200 OK` — updated [`SourceRead`](#sourceRead)

---

### 5.4 Get Source Run History

```
GET /api/v1/sources/{id}/runs?limit=20
```

**Query Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | `20` | Number of run logs to return (newest first) |

**Response** `200 OK` — array of [`RunLogRead`](#runLogRead)

```json
[
  {
    "id": 201,
    "source_id": 3,
    "run_started_at": "2026-04-10T18:00:00Z",
    "run_finished_at": "2026-04-10T18:00:12Z",
    "status": "success",
    "items_fetched": 5,
    "items_new": 2,
    "items_duplicate": 3,
    "error_message": null
  }
]
```

---

### 5.5 Manually Trigger Source Collection

Runs collection for a single source immediately as a background task.

```
POST /api/v1/sources/{id}/trigger
```

**Response** `202 Accepted`
```json
{
  "message": "Collection triggered for source 'SEC Press Releases'",
  "source_id": 3
}
```

**Error:** `404 Not Found` if source does not exist.

---

## 6. Raw Items

> No authentication required.  
> Raw items are the unprocessed articles collected from sources. The frontend will typically not need these — use `/api/v1/alerts` instead. Raw items are provided for traceability and audit.

### 6.1 List Raw Items

```
GET /api/v1/raw-items
```

**Query Parameters**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source_id` | integer | — | Filter by source |
| `is_duplicate` | boolean | — | `false` = unique items only |
| `since` | datetime | — | Items fetched after this datetime (ISO 8601) |
| `limit` | integer | `50` | Max `500` |
| `offset` | integer | `0` | Pagination offset |

**Response** `200 OK` — array of [`RawItemRead`](#rawItemRead) ordered by `fetched_at` descending.

---

### 6.2 Get Raw Item Detail

Returns the full article including raw text and original HTML snapshot.

```
GET /api/v1/raw-items/{id}
```

**Response** `200 OK` — [`RawItemDetail`](#rawItemDetail)

> **Note:** `raw_html` can be large (full page HTML). Only request this when you specifically need the original article content for audit or traceability.

---

## 7. Schema Reference

### ProcessedAlertRead

Returned by `GET /api/v1/alerts` and as nested objects in `EventDetail.alerts`.

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Unique alert ID |
| `raw_item_id` | integer | ID of the source article in `raw_items` table |
| `title` | string \| null | Article headline |
| `source_name` | string \| null | Source display name (e.g. `"SEC Press Releases"`) |
| `item_url` | string \| null | Direct URL to the original article |
| `risk_level` | string \| null | `"low"`, `"medium"`, or `"high"` |
| `primary_category` | string \| null | Fraud category — see [§9](#9-fraud-categories) |
| `signal_score_total` | integer \| null | Sum of 5 signal factors — range 5–25 |
| `relevance_score` | float \| null | `signal_score_total / 25` — convenience field for progress bars / sorting (0.0–1.0) |
| `matched_keywords` | string[] \| null | Source keywords that matched this article |
| `is_relevant` | boolean | `true` = AI confirmed fraud content; `false` = filtered out (keyword gate or AI rejection) |
| `processed_at` | datetime | UTC timestamp when the article was processed (ISO 8601) |

---

### ProcessedAlertDetail

All fields from `ProcessedAlertRead` plus:

| Field | Type | Description |
|-------|------|-------------|
| `summary` | string \| null | AI-generated factual summary (3–5 sentences) |
| `secondary_category` | string \| null | Optional secondary fraud category |
| `entities_json` | object \| null | Named entities extracted by AI: `{"names": ["entity1", "entity2", ...]}` |
| `financial_impact_estimate` | string \| null | Raw AI dollar estimate — e.g. `"$4.2 million"`, `"unknown"`, `"none"` |
| `victim_scale_raw` | string \| null | AI assessment: `"single"`, `"multiple"`, or `"nationwide"` |
| `ai_model` | string \| null | OpenAI model version used — e.g. `"gpt-4o-mini-2024-07-18"` |
| `score_source_credibility` | integer \| null | 1–5 — hard-coded per source |
| `score_financial_impact` | integer \| null | 1–5 — derived from `financial_impact_estimate` |
| `score_victim_scale` | integer \| null | 1–5 — derived from `victim_scale_raw` |
| `score_cross_source` | integer \| null | 1–5 — increases as more sources report the same event |
| `score_trend_acceleration` | integer \| null | 1–5 — based on recent keyword frequency trend |
| `event_id` | integer \| null | ID of the grouped fraud event (null if not linked) |
| `event_title` | string \| null | Title of the linked event |
| `review_status` | string \| null | Latest human review: `"approved"`, `"false_positive"`, or `"edited"` (null = not yet reviewed) |

> **`entities_json` structure note:** The `names` array is a flat list of all entities (individuals, organizations, and domains combined). Named entity type separation (individuals vs. organizations) is planned for M3.

---

### EventRead

Returned by `GET /api/v1/events`.

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Unique event ID |
| `title` | string | Auto-generated title: `"<primary_entity>: <category>"` |
| `risk_level` | string \| null | Highest risk level among all linked alerts |
| `category` | string \| null | Fraud category shared by all linked alerts |
| `primary_entity` | string \| null | First named entity extracted from the first alert |
| `first_detected_at` | datetime | When the first alert in this event was processed |
| `last_updated_at` | datetime | When the most recent alert was added to this event |
| `source_count` | integer | Number of distinct source alerts contributing to this event |

---

### EventDetail

All fields from `EventRead` plus:

| Field | Type | Description |
|-------|------|-------------|
| `alerts` | ProcessedAlertRead[] | All alerts linked to this event (full list, unordered) |

---

### AlertReviewCreate

Request body for `POST /api/v1/alerts/{id}/review`.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `review_status` | string | Yes | Must be exactly `"approved"`, `"false_positive"`, or `"edited"` |
| `edited_summary` | string \| null | No | Replaces the AI summary on the alert when provided |
| `adjusted_risk_level` | string \| null | No | Override computed risk level: `"low"`, `"medium"`, or `"high"` |

---

### AlertReviewRead

Response from `POST /api/v1/alerts/{id}/review`.

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Review record ID |
| `alert_id` | integer \| null | Alert this review belongs to |
| `user_id` | integer \| null | ID of the user who submitted the review |
| `review_status` | string \| null | `"approved"`, `"false_positive"`, or `"edited"` |
| `edited_summary` | string \| null | The edited summary text (if provided) |
| `adjusted_risk_level` | string \| null | The overridden risk level (if provided) |
| `reviewed_at` | datetime | UTC timestamp of review submission |

---

### SourceRead

Returned by source endpoints.

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Source ID |
| `name` | string | Display name (e.g. `"SEC Press Releases"`) |
| `base_url` | string | Source homepage URL |
| `source_type` | string | `"rss"` or `"html_scrape"` |
| `rss_url` | string \| null | RSS feed URL (null for HTML scrapers) |
| `category` | string \| null | General content category |
| `primary_focus` | string \| null | Free-text description of what this source covers |
| `keywords` | string[] \| null | Keyword list used to gate AI processing |
| `is_active` | boolean | Whether collection is currently enabled |
| `polling_frequency_minutes` | integer | Target polling interval |
| `adapter_class` | string \| null | Internal Python adapter class name |
| `notes` | string \| null | Admin notes |
| `created_at` | datetime | When this source was added |
| `updated_at` | datetime | Last modification time |

---

### RunLogRead

Returned by `GET /api/v1/sources/{id}/runs`.

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Run log ID |
| `source_id` | integer \| null | Source that was collected |
| `run_started_at` | datetime | UTC start time |
| `run_finished_at` | datetime \| null | UTC end time (null if still running) |
| `status` | string \| null | `"success"`, `"failed"`, or `"partial"` |
| `items_fetched` | integer | Total stubs fetched from source |
| `items_new` | integer | New articles stored (not duplicates) |
| `items_duplicate` | integer | Articles skipped as duplicates |
| `error_message` | string \| null | Error details if status is `"failed"` |

---

### RawItemRead

Returned by `GET /api/v1/raw-items`.

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Raw item ID |
| `source_id` | integer \| null | Source that collected this item |
| `item_url` | string | Original article URL |
| `title` | string \| null | Article title |
| `published_at` | datetime \| null | Publication date from the source |
| `content_hash` | string \| null | SHA-256 hash of article text (deduplication key) |
| `url_hash` | string \| null | SHA-256 hash of normalized URL |
| `is_duplicate` | boolean | True if another item with the same content hash already exists |
| `fetched_at` | datetime | When this item was collected |

---

### RawItemDetail

All fields from `RawItemRead` plus:

| Field | Type | Description |
|-------|------|-------------|
| `raw_text` | string \| null | Extracted plain text of the article |
| `raw_html` | string \| null | Full HTML snapshot of the article page |

---

## 8. Signal Scoring System

Every fraud-relevant alert receives a **5-factor signal score** — a transparent, deterministic risk rating. Each factor scores 1–5 points; the total determines the risk level.

### Scoring Factors

| Factor | Score 1 | Score 3 | Score 5 | Source |
|--------|---------|---------|---------|--------|
| **Source Credibility** | Low-trust source | Mid-tier source | SEC, FBI, DOJ | Hard-coded per source |
| **Financial Impact** | Under $1M or unknown | $1M–$10M | Over $10M | AI extracts dollar amount |
| **Victim Scale** | Single victim | Multiple victims | Nationwide | AI assesses from article |
| **Cross-Source** | 1 source only | 2 sources | 3+ sources | Counts linked event sources |
| **Trend Acceleration** | Stable frequency | 25–99% increase in 7d | Doubled or more in 7d | Keyword frequency query |

### Total → Risk Level

| Score Range | Risk Level | Meaning |
|-------------|------------|---------|
| 5–6 | `low` | Informational — stored in DB and visible in dashboard |
| 7–12 | `medium` | Notable — will trigger daily digest email (M3) |
| 13–25 | `high` | Urgent — will trigger immediate email alert (M3) |

### Key relationships between fields

- `signal_score_total` = `score_source_credibility + score_financial_impact + score_victim_scale + score_cross_source + score_trend_acceleration`
- `risk_level` is derived from `signal_score_total` (not set by AI)
- `relevance_score` = `signal_score_total / 25` — a 0.0–1.0 float for frontend convenience (e.g. progress bars). Always use `signal_score_total` for precise sorting and `risk_level` for categorical logic.
- `score_cross_source` is recalculated automatically when additional sources link to the same event — so an alert's score can increase over time without re-running AI.

---

## 9. Fraud Categories

The `primary_category` field on alerts, and the `category` field on events, use one of these exact string values:

| Value | Description |
|-------|-------------|
| `Investment Fraud` | Ponzi schemes, securities fraud, fake investment advisers |
| `Cybercrime` | Ransomware, data breaches, hacking, malware |
| `Consumer Scam` | Impersonation, phishing, retail fraud, identity theft |
| `Money Laundering` | Financial concealment, suspicious transaction patterns |
| `Cryptocurrency Fraud` | Crypto scams, exchange fraud, rug pulls, NFT fraud |

> An alert may have a `secondary_category` when the article covers more than one fraud type. The `primary_category` is always the dominant classification.

---

## 10. Source Registry

Ten sources are monitored continuously. These are the `source_name` values you will see in alert responses.

| ID | Source Name | Type | Credibility Score |
|----|-------------|------|:-----------------:|
| 1 | SEC Press Releases | RSS | 5 |
| 2 | FBI National Press Releases | RSS | 5 |
| 3 | FBI News Blog RSS | RSS | 5 |
| 4 | FBI in the News RSS | RSS | 5 |
| 5 | DOJ Press Releases | HTML scrape | 5 |
| 6 | FTC RSS Feeds | HTML scrape | 4 |
| 7 | FinCEN Press Releases | HTML scrape | 4 |
| 8 | IC3 Press Releases | HTML scrape | 4 |
| 9 | KrebsOnSecurity | RSS | 3 |
| 10 | BleepingComputer | RSS | 3 |

Use the `source` query parameter (name partial match) to filter by agency family:
- `source=FBI` — returns alerts from all three FBI sources
- `source=SEC` — SEC only
- `source=DOJ` — DOJ only

Use `source_id` (exact numeric ID) when you need pinpoint filtering.

---

## 11. Error Reference

All error responses follow FastAPI's standard format:

```json
{
  "detail": "Human-readable error message"
}
```

| HTTP Code | When it occurs |
|-----------|---------------|
| `401 Unauthorized` | Missing, expired, or invalid `access_token` cookie on a protected endpoint |
| `404 Not Found` | The requested resource ID does not exist |
| `409 Conflict` | `POST /api/v1/alerts/process` called while a pipeline run is already in progress |
| `422 Unprocessable Entity` | Request validation failed — invalid query parameter types or invalid `review_status` value |
| `500 Internal Server Error` | Unexpected server error — check server logs |

---

## 12. Frontend Quick-Start

### Step 1 — Get a token

Log in once to obtain the `access_token` cookie. In a browser, simply navigate to `https://hiddenalerts.com/login` and log in. For API access, extract the cookie value:

```bash
# Login and save cookie to file
curl -c cookies.txt -s -o /dev/null -w "%{http_code}" \
  -X POST https://hiddenalerts.com/login \
  -d "username=ken@hiddenalerts.com&password=yourpassword"
# → 302 (redirect after successful login)

# Extract the token value
grep access_token cookies.txt | awk '{print $NF}'
```

### Step 2 — Fetch high-risk alerts

```javascript
const BASE = "https://api.hiddenalerts.com";
const TOKEN = "your_jwt_token_here";

const headers = { Cookie: `access_token=${TOKEN}` };

// Get HIGH-risk fraud alerts (AI-confirmed, newest first)
const resp = await fetch(
  `${BASE}/api/v1/alerts?risk_level=high&is_relevant=true&limit=50`,
  { headers }
);
const alerts = await resp.json();

// Each alert has:
// id, title, source_name, item_url
// risk_level, primary_category
// signal_score_total (5–25), relevance_score (0.0–1.0)
// matched_keywords, processed_at
```

### Step 3 — Get full detail for an alert

```javascript
const detail = await fetch(
  `${BASE}/api/v1/alerts/${alerts[0].id}`,
  { headers }
);
const alert = await detail.json();

// Additional fields in detail:
// summary            — AI-generated 3–5 sentence summary
// entities_json      — { "names": ["entity1", ...] }
// score_*            — 5 individual scoring factor values
// event_id           — linked grouped event (if any)
// review_status      — latest human review decision
```

### Step 4 — Fetch fraud events

```javascript
// Events group related alerts from multiple sources
const eventsResp = await fetch(
  `${BASE}/api/v1/events?risk_level=high&limit=20`,
  { headers }
);
const events = await eventsResp.json();

// Each event has: id, title, risk_level, category,
// primary_entity, source_count, first_detected_at, last_updated_at

// Get full event with all linked alerts
const eventDetail = await fetch(
  `${BASE}/api/v1/events/${events[0].id}`,
  { headers }
);
const event = await eventDetail.json();
// event.alerts → array of ProcessedAlertRead
```

### Step 5 — System health check (no auth needed)

```javascript
const health = await fetch(`${BASE}/api/v1/health`);
const status = await health.json();
// { status: "ok", env: "production", database: "connected", scheduler: "running" }
```

### Recommended display logic

```javascript
// Risk level → color
const riskColor = {
  high:   "#dc3545",  // red
  medium: "#fd7e14",  // orange
  low:    "#6c757d",  // gray
};

// relevance_score → progress bar width
const barWidth = `${Math.round(alert.relevance_score * 100)}%`;

// Signal score badge
const badge = `Score: ${alert.signal_score_total}/25`;

// Show "N sources" badge on events with source_count > 1
const sourceLabel = event.source_count > 1
  ? `Confirmed by ${event.source_count} sources`
  : "Single source";
```

---

## 13. Roadmap

### Currently Live (Milestone 2)

| Endpoint | Status |
|----------|--------|
| `GET /api/v1/health` | ✅ Live |
| `GET /api/v1/stats` | ✅ Live |
| `GET /api/v1/sources` | ✅ Live |
| `GET /api/v1/sources/{id}` | ✅ Live |
| `PATCH /api/v1/sources/{id}` | ✅ Live |
| `GET /api/v1/sources/{id}/runs` | ✅ Live |
| `POST /api/v1/sources/{id}/trigger` | ✅ Live |
| `GET /api/v1/raw-items` | ✅ Live |
| `GET /api/v1/raw-items/{id}` | ✅ Live |
| `GET /api/v1/alerts` | ✅ Live |
| `GET /api/v1/alerts/{id}` | ✅ Live |
| `POST /api/v1/alerts/process` | ✅ Live |
| `POST /api/v1/alerts/{id}/review` | ✅ Live |
| `GET /api/v1/events` | ✅ Live |
| `GET /api/v1/events/{id}` | ✅ Live |
| `POST /login` + `GET /logout` | ✅ Live |
| Swagger UI at `/docs` | ✅ Live |

### Planned for Milestone 3

| Feature | Notes |
|---------|-------|
| `Authorization: Bearer <token>` header | Enables cross-domain frontends without cookie handling |
| `GET /api/v1/alerts/search?q=` | Full-text search across title, summary, and entities |
| Email alert webhooks / subscription endpoint | HIGH-risk immediate; MEDIUM daily digest |
| Weekly report endpoint | `GET /api/v1/reports/weekly` |
| Entity type separation in `entities_json` | Separate `individuals`, `organizations`, `domains` sub-keys |
| HTTPS on all traffic | Already live — `https://api.hiddenalerts.com` + `https://hiddenalerts.com` |
