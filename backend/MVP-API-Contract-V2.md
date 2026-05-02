# HiddenAlerts API Contract V2

**Last updated:** 22 April 2026  
**Version:** M3 (In Progress) / 0.2.0  
**Base URL:** `http://localhost:8000` (local dev)  /  `https://hiddenalerts.com` (production)  
**Interactive docs (Swagger UI):** `https://api.hiddenalerts.com/docs`  
**API Prefix:** All JSON REST endpoints live under `/api/v1`

**Backend contact:** Adnan


## Overview

- **Admin surface** — Ken and internal admins. Full access to all alerts, review workflow, pipeline controls. Currently served by a server-rendered dashboard at `/dashboard`. Admins can also use the API directly.
- **Subscriber surface** — End users (newsletter subscribers). Access only to curated, published alerts through the `/client` endpoints.
- **Public feed** — The endpoint frontend app uses for public display of curated alerts. No authentication required. Returns curated alerts only.

Both admin and subscriber surfaces authenticate through the same backend. Token is the same JWT regardless of role — what changes is which endpoints accept it.

---

## Table of Contents
0. [**Public Feed — Current Frontend MVP Endpoints**](#0-public-feed--current-frontend-mvp-endpoints)
   - [GET /api/alerts](#01-get-apialerts--published-alert-list)
   - [GET /api/alerts/{id}](#02-get-apialertsid--published-alert-detail-new)
   - [GET /api/alerts/stats](#03-get-apialertsstats--published-alert-stats-new)
1. [Authentication Overview](#1-authentication-overview)
2. [Auth Endpoints](#2-auth-endpoints)
3. [Alerts — Admin](#3-alerts--admin)
4. [Alerts — Subscriber (Public Feed)](#4-alerts--subscriber-public-feed)
5. [Events](#5-events)
6. [Sources (Admin Settings)](#6-sources-admin-settings)
7. [Raw Items & Stats](#7-raw-items--stats)
8. [Health Check](#8-health-check)
9. [HTML Dashboard Routes](#9-html-dashboard-routes-server-rendered)
10. [Roles & Access Matrix](#10-roles--access-matrix)
11. [Error Responses](#11-error-responses)
12. [Integration Guide](#12-frontend-integration-guide)

---

## 0. Public Feed

> **Hasnain: Use the three endpoints below for the current frontend MVP phase.**  
> No authentication required on any of them. All return published (admin-approved) alerts only.

Base URL: `http://localhost:8000/api/alerts` (local) / `https://hiddenalerts.com/api/alerts` (prod)

---

### 0.1 GET /api/alerts — Published Alert List

```json
{
  "alerts": [
    {
      "id": 42,
      "title": "SEC Charges Investment Firm with $4.2M Fraud",
      "summary": "The SEC charged a New York-based firm...",
      "category": "Investment Fraud",
      "risk_level": "high",
      "signal_score": 19,
      "source_name": "SEC Press Releases",
      "source_url": "https://sec.gov/news/press-release/...",
      "published_at": "2026-04-22T10:30:01Z"
    }
  ]
}
```

### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `id` | `int` | Unique alert ID |
| `title` | `string\|null` | Article/press release title |
| `summary` | `string\|null` | AI-generated summary |
| `category` | `string\|null` | Fraud category (see list below) |
| `risk_level` | `string\|null` | `"low"`, `"medium"`, or `"high"` |
| `signal_score` | `int\|null` | Composite risk score (1–25) |
| `source_name` | `string\|null` | Name of the originating source |
| `source_url` | `string\|null` | Direct link to the original article |
| `published_at` | `datetime\|null` | ISO 8601 UTC — when admin published it |

### Optional Query Parameters

| Param | Type | Example | Description |
|-------|------|---------|-------------|
| `risk_level` | string | `?risk_level=high` | Filter by risk level |
| `category` | string | `?category=Cybercrime` | Filter by category (exact) |
| `source` | string | `?source=FBI` | Partial source name search |
| `limit` | int | `?limit=20` | Max results (default 50, max 500) |
| `offset` | int | `?offset=20` | Pagination offset |

### Quick Test

```bash
# Fetch all published alerts
curl http://localhost:8000/api/alerts

# Filter high-risk only
curl "http://localhost:8000/api/alerts?risk_level=high"

# Paginate
curl "http://localhost:8000/api/alerts?limit=10&offset=0"
```

### Notes for Hasnain
- Results are sorted newest-published first.
- If `"alerts": []`, no alerts have been published yet — the admin reviews and publishes them.
- Do NOT use `/api/v1/alerts` or `/api/v1/client/alerts` for this phase — those require auth.
- `risk_level` values are lowercase here: `"low"`, `"medium"`, `"high"` — capitalise in the UI.
  **Derived from `signal_score` on the server** (M3 thresholds: `≥16` high, `9..15` medium, `<9` low).
  Older alerts whose stored value is stale will still display correctly. Filtering on `risk_level=high` also uses the derived bucket.
- Category values: `Investment Fraud`, `Cybercrime`, `Consumer Scam`, `Money Laundering`, `Cryptocurrency Fraud`, `Other`.
  `Other` is a real value — when shown, render it as a low-emphasis label (don't promote it to a primary fraud-type badge).
- **Use `source_published_at` for the date shown on list cards** (it's the article/press-release date — what readers expect). `published_at` is the platform publish time and is mainly an internal/sort key.

---

### 0.2 GET /api/alerts/{id} — Enriched Public Alert Detail

```
GET /api/alerts/{id}
```

**No authentication required.**  
Returns the full public detail for a single published alert.  
Returns `404` if the alert does not exist **or** is not yet published.

Optional sections (`why_it_matters`, `key_intelligence`, `risk_assessment`,
`sources`, `affected_group`, `subcategory`, `timeline`, `related_signals`) are
**omitted from the JSON when their underlying data is empty** — Hasnain does not
have to filter blanks on the frontend.

> Note: `risk_level` and `confidence` are returned in **Title Case** (`"High"`,
> `"Medium"`, `"Low"`) on the detail endpoint to match Ken's design spec. The
> list endpoint (`GET /api/alerts`) keeps the lowercase form for backward
> compatibility — convert as needed when navigating list → detail.
> `risk_level` is **derived from `score` on the server** (M3 thresholds: `≥16`
> High, `9..15` Medium, `<9` Low) — do not compute it on the client and do not
> trust the legacy stored value.

> **Timestamp reference (read this — frequently confused):**
> | Field | Meaning | Use it for |
> |---|---|---|
> | `source_published_at` | Original article / press-release publication date | List cards (what readers expect). Backward-compat alias on detail. |
> | `published_at` | When HiddenAlerts (admin) published the alert on the platform | Internal sort key; appears in `timeline`. |
> | `processed_at` | When the AI pipeline processed the alert | Audit only — not for display. |
> | `published_date` | Canonical display date for the **detail page** | Render this on the detail page header. Resolves in priority order: `source_published_at` → `published_at` → `processed_at`. |

> **`related_signals` cleanness + quantity rule:** an alert appears here only
> if it (a) is published, (b) shares an event with the current alert, AND
> (c) shares at least one named entity. Event grouping alone is too broad; the
> entity-overlap requirement keeps drift out. **At least 2 qualifying peers are
> required** (Ken's "two to four items max"); fewer means the section is
> **omitted entirely**. Capped at 4.

**Response `200 OK` (rich example with all optional sections populated):**
```json
{
  "id": 42,
  "title": "SEC Charges Investment Firm with $4.2M Fraud",
  "score": 20,
  "risk_level": "High",
  "confidence": "High",
  "summary": "The SEC charged a New York-based firm with defrauding investors...",

  "why_it_matters": [
    "Reported by a trusted source.",
    "Financial impact reported as $4.2M.",
    "Victim scope indicated as multiple."
  ],

  "key_intelligence": [
    { "label": "Fraud Type", "value": "Wire Fraud" },
    { "label": "Financial Impact", "value": "$4.2M" },
    { "label": "Affected Group", "value": "Multiple victims or organizations" },
    { "label": "Source Credibility", "value": "High" },
    { "label": "Named Entities", "value": "SEC, New York-based Firm" }
  ],

  "risk_assessment": "High risk based on credible source reporting and strong supporting fraud signals indicating broad or significant impact.",

  "sources": [
    { "name": "SEC Press Releases", "url": "https://sec.gov/news/press-release/..." }
  ],

  "published_date": "2026-04-22T08:00:00Z",

  "category": "Investment Fraud",
  "subcategory": "Wire Fraud",
  "affected_group": "Multiple victims or organizations",

  "timeline": [
    { "date": "2026-04-22T08:00:00Z", "event": "Source published the alert" },
    { "date": "2026-04-22T10:30:01Z", "event": "Alert published to dashboard" }
  ],

  "related_signals": [
    { "id": 38, "title": "DOJ indicts related actor", "score": 17, "risk_level": "High" }
  ],

  "signal_score": 20,
  "secondary_category": "Wire Fraud",
  "source_name": "SEC Press Releases",
  "source_url": "https://sec.gov/news/press-release/...",
  "source_published_at": "2026-04-22T08:00:00Z",
  "published_at": "2026-04-22T10:30:01Z",
  "processed_at": "2026-04-22T10:15:00Z",
  "entities": ["SEC", "New York-based Firm"]
}
```

**Field Reference:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | `int` | Unique alert ID |
| `title` | `string\|null` | Article/press release title |
| `score` | `int\|null` | Composite signal score (0–25) |
| `risk_level` | `string\|null` | **Title case**: `"High"`, `"Medium"`, or `"Low"` |
| `confidence` | `string\|null` | **Title case** — derived from source credibility + score + relevance |
| `summary` | `string\|null` | AI-generated summary |
| `why_it_matters` | `string[]?` | 1–3 short bullets — omitted if no qualifying signals |
| `key_intelligence` | `{label,value}[]?` | Structured data points — omitted if empty |
| `risk_assessment` | `string` | Short 1–2 sentence justification tied to `risk_level` |
| `sources` | `{name,url}[]?` | Source references (current source — array form for future multi-source) |
| `published_date` | `datetime\|null` | Best display date — `source_published_at` first, then `published_at`, then `processed_at` |
| `category` | `string\|null` | Primary fraud category |
| `subcategory` | `string?` | Secondary classification — omitted if absent |
| `affected_group` | `string?` | Human-readable victim scope — omitted if absent |
| `timeline` | `{date,event}[]?` | Source-pub + platform-pub timestamps — omitted if no timestamps |
| `related_signals` | `{id,title,score,risk_level}[]?` | 2–4 published peers via shared event **and** entity overlap — omitted when fewer than 2 qualifying peers exist |

**Backward-compatibility additive fields** (kept from the prior contract; safe to keep using if your frontend already references them):

| Field | Type | Description |
|-------|------|-------------|
| `signal_score` | `int\|null` | Alias for `score` |
| `secondary_category` | `string\|null` | Alias for `subcategory` |
| `source_name` | `string\|null` | First source's name (mirrors `sources[0].name`) |
| `source_url` | `string\|null` | First source's url (mirrors `sources[0].url`) |
| `source_published_at` | `datetime\|null` | Original source publication date |
| `published_at` | `datetime\|null` | When admin published on platform |
| `processed_at` | `datetime\|null` | When AI processed |
| `entities` | `string[]` | Flat entity list (always present, may be empty) |

**NOT returned** (intentionally excluded): score breakdown fields
(`score_source_credibility`, `score_financial_impact`, `score_victim_scale`,
`score_cross_source`, `score_trend_acceleration`), review history,
moderation state (`is_published`, `is_relevant`), raw `entities_json`,
`ai_model`, `matched_keywords`, `financial_impact_estimate`,
`victim_scale_raw`, `published_by_user_id`.

**Errors:**
| Code | Reason |
|------|--------|
| `404` | Alert not found or not published |

**Quick Test:**
```bash
curl http://localhost:8000/api/alerts/42
```

---

### 0.3 GET /api/alerts/stats — Published Alert Stats *(NEW)*

```
GET /api/alerts/stats
```

**No authentication required.**  
Returns aggregate counts for published alerts only. Use this to drive a summary dashboard panel or stats section.

**Response `200 OK`:**
```json
{
  "total_alerts": 42,
  "high_count": 8,
  "medium_count": 25,
  "low_count": 9,
  "category_breakdown": [
    { "category": "Investment Fraud", "count": 12 },
    { "category": "Cybercrime", "count": 10 },
    { "category": "Consumer Scam", "count": 8 },
    { "category": "Money Laundering", "count": 7 },
    { "category": "Cryptocurrency Fraud", "count": 5 }
  ]
}
```

**Field Reference:**

| Field | Type | Description |
|-------|------|-------------|
| `total_alerts` | `int` | Total number of published alerts |
| `high_count` | `int` | Published alerts with `risk_level = "high"` |
| `medium_count` | `int` | Published alerts with `risk_level = "medium"` |
| `low_count` | `int` | Published alerts with `risk_level = "low"` |
| `category_breakdown` | `array` | Per-category counts, ordered by count descending |
| `category_breakdown[].category` | `string` | Fraud category name |
| `category_breakdown[].count` | `int` | Number of published alerts in that category |

**Notes:**
- All aggregates are derived exclusively from published alerts. Unpublished alerts are never counted.
- Alerts with no `primary_category` are counted in `total_alerts` but excluded from `category_breakdown`.
- When no alerts are published, all counts are `0` and `category_breakdown` is `[]`.

**Quick Test:**
```bash
curl http://localhost:8000/api/alerts/stats
```

---

## 1. Authentication Overview

### How Auth Works
The API uses **JWT Bearer tokens**. On successful login, a token is returned in the JSON body **and** set as an `HttpOnly` cookie named `access_token`.

Frontend can authenticate requests in **two ways** (pick one per request):

| Method | Header/Cookie | Example |
|--------|--------------|---------|
| Bearer token | `Authorization: Bearer <token>` | API clients, mobile |
| Cookie | `Cookie: access_token=<token>` | Web browsers |

### Token Lifetime
- **30 days** (`expires_in` is returned in seconds from login response)
- No refresh token endpoint currently — re-login when expired

### Roles
| Role | Access |
|------|--------|
| `admin` | All endpoints |
| `subscriber` | Client feed + auth/me + change-password |

---

## 2. Auth Endpoints

### 2.1 Login
```
POST /api/v1/auth/login
```
Authenticates both admins and subscribers. Returns JWT + sets HttpOnly cookie.

**Request Body:**
```json
{
  "email": "admin@hiddenalerts.com",
  "password": "admin123"
}
```

**Response `200 OK`:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 2592000,
  "user": {
    "id": 1,
    "email": "admin@hiddenalerts.com",
    "role": "admin",
    "is_active": true,
    "full_name": null,
    "wants_high_alert_email": false,
    "wants_digest_email": false,
    "wants_weekly_report_email": false
  }
}
```

**Errors:**
| Code | Reason |
|------|--------|
| `401` | Invalid email or password |

**Cookie set on success:**
```
Set-Cookie: access_token=<token>; HttpOnly; SameSite=Lax; Max-Age=2592000
```

**Usage example:**
```js
const res = await fetch('/api/v1/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  credentials: 'include', // sends/receives cookies
  body: JSON.stringify({ email, password })
});
const data = await res.json();
// Store data.access_token in memory or localStorage for Bearer auth
// OR use credentials:'include' on all requests for cookie-based auth
```

---

### 2.2 Get Current User (Me)
```
GET /api/v1/auth/me
```
Returns the currently authenticated user's profile.

**Auth required:** Bearer token OR cookie (any role)

**Response `200 OK`:**
```json
{
  "id": 1,
  "email": "admin@hiddenalerts.com",
  "role": "admin",
  "is_active": true,
  "full_name": null,
  "wants_high_alert_email": false,
  "wants_digest_email": false,
  "wants_weekly_report_email": false
}
```

**Errors:**
| Code | Reason |
|------|--------|
| `401` | Not authenticated or token expired |

**Usage:** Call this on app load to restore session state.

---

### 2.3 Change Password
```
POST /api/v1/auth/change-password
```
Updates the authenticated user's password.

**Auth required:** Bearer token OR cookie (any role)

**Request Body:**
```json
{
  "current_password": "oldpassword",
  "new_password": "newpassword123"
}
```

**Response `200 OK`:**
```json
{
  "message": "Password updated successfully"
}
```

**Errors:**
| Code | Reason |
|------|--------|
| `400` | Current password is incorrect |
| `401` | Not authenticated |
| `422` | `new_password` shorter than 8 characters |

> **Note:** Password reset (forgot password) via email is not yet implemented. This endpoint only works for authenticated users who know their current password.

---

## 3. Alerts — Admin

These endpoints return **all** alerts (published and unpublished) and are intended for the admin review workflow.

**Auth required:** Cookie or Bearer token with **any** valid user (checked against `get_current_user`).

### 3.1 List Alerts
```
GET /api/v1/alerts
```

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `risk_level` | string | Filter: `low`, `medium`, `high` |
| `category` | string | Filter by `primary_category` (exact match) |
| `source_id` | int | Filter by source ID |
| `source` | string | Partial, case-insensitive source name search |
| `keyword` | string | Search in title or matched keywords |
| `start_date` | datetime | ISO 8601 — alerts processed after this time |
| `end_date` | datetime | ISO 8601 — alerts processed before this time |
| `is_relevant` | bool | `true` / `false` |
| `is_published` | bool | `true` / `false` |
| `limit` | int | Default `50`, max `500` |
| `offset` | int | Default `0` for pagination |

**Response `200 OK`** — Array of alert summaries:
```json
[
  {
    "id": 42,
    "raw_item_id": 101,
    "title": "FBI warns of rising elder fraud losses...",
    "source_name": "FBI Press Releases",
    "item_url": "https://www.fbi.gov/news/...",
    "risk_level": "high",
    "primary_category": "Consumer Scam",
    "signal_score_total": 18,
    "relevance_score": 0.72,
    "matched_keywords": ["elder fraud", "wire transfer"],
    "is_relevant": true,
    "processed_at": "2026-04-22T14:00:00Z",
    "is_published": false,
    "published_at": null
  }
]
```

**Field Reference:**
| Field | Description |
|-------|-------------|
| `signal_score_total` | Raw score out of 25 |
| `relevance_score` | Normalised `signal_score_total / 25` (0.0–1.0) |
| `is_published` | Whether admin has approved and published this alert |
| `is_relevant` | Whether AI determined the alert is relevant (Tier 1/2 vs Tier 3) |

---

### 3.2 Get Alert Detail (Admin)
```
GET /api/v1/alerts/{alert_id}
```

**Response `200 OK`** — Full alert detail including AI output and score breakdown:
```json
{
  "id": 42,
  "raw_item_id": 101,
  "title": "FBI warns of rising elder fraud losses...",
  "source_name": "FBI Press Releases",
  "item_url": "https://www.fbi.gov/news/...",
  "risk_level": "high",
  "primary_category": "Consumer Scam",
  "secondary_category": "Wire Fraud",
  "signal_score_total": 18,
  "relevance_score": 0.72,
  "matched_keywords": ["elder fraud", "wire transfer"],
  "is_relevant": true,
  "processed_at": "2026-04-22T14:00:00Z",
  "is_published": false,
  "published_at": null,
  "summary": "The FBI reports...",
  "entities_json": { "names": ["FBI", "Western Union"] },
  "financial_impact_estimate": "$3.4 billion",
  "victim_scale_raw": "nationwide",
  "ai_model": "gpt-4o-mini",
  "score_source_credibility": 5,
  "score_financial_impact": 5,
  "score_victim_scale": 4,
  "score_cross_source": 3,
  "score_trend_acceleration": 1,
  "event_id": 7,
  "event_title": "Elder Fraud Wave Q1 2026",
  "review_status": "approved"
}
```

**Errors:**
| Code | Reason |
|------|--------|
| `404` | Alert not found |

---

### 3.3 Submit Alert Review (Admin)
```
POST /api/v1/alerts/{alert_id}/review
```
Admin review action. Approving a relevant alert publishes it to the subscriber feed.

**Auth required:** Admin role

**Request Body:**
```json
{
  "review_status": "approved",
  "edited_summary": "Optional — override AI summary",
  "adjusted_risk_level": "high"
}
```

**`review_status` values:**
| Value | Effect |
|-------|--------|
| `approved` | Publishes alert if `is_relevant=true` and not already published |
| `false_positive` | Marks as not relevant; does NOT publish |
| `edited` | Saves edits without publishing |

**Response `200 OK`:**
```json
{
  "id": 15,
  "alert_id": 42,
  "user_id": 1,
  "review_status": "approved",
  "edited_summary": null,
  "adjusted_risk_level": null,
  "reviewed_at": "2026-04-22T14:30:00Z"
}
```

**Errors:**
| Code | Reason |
|------|--------|
| `404` | Alert not found |
| `422` | Invalid `review_status` value |

---

### 3.4 Trigger Pipeline (Admin)
```
POST /api/v1/alerts/process
```
Manually triggers the AI processing pipeline for unprocessed raw items. Runs in background.

**Auth required:** Any authenticated user

**Response `202 Accepted`:**
```json
{
  "message": "Alert processing started",
  "status": "accepted"
}
```

**Errors:**
| Code | Reason |
|------|--------|
| `409` | Pipeline already running |

---

## 4. Alerts — Subscriber (Public Feed)

These endpoints only return **published** alerts (`is_published = true`). Safe for subscriber-facing mobile/web apps.

**Auth required:** Bearer token OR cookie (`subscriber` or `admin` role)

### 4.1 List Published Alerts
```
GET /api/v1/client/alerts
```

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `risk_level` | string | Filter: `low`, `medium`, `high` |
| `category` | string | Filter by `primary_category` |
| `source` | string | Partial source name search |
| `limit` | int | Default `50`, max `500` |
| `offset` | int | Default `0` |

**Response `200 OK`:**
```json
[
  {
    "id": 42,
    "title": "FBI warns of rising elder fraud losses...",
    "source_name": "FBI Press Releases",
    "item_url": "https://www.fbi.gov/news/...",
    "risk_level": "high",
    "primary_category": "Consumer Scam",
    "signal_score_total": 18,
    "summary": "The FBI reports a significant increase...",
    "processed_at": "2026-04-22T14:00:00Z",
    "published_at": "2026-04-22T14:35:00Z",
    "matched_keywords": ["elder fraud", "wire transfer"]
  }
]
```

> Results are ordered by `published_at DESC` — newest published alerts first.

---

### 4.2 Get Published Alert Detail
```
GET /api/v1/client/alerts/{alert_id}
```

Returns `404` if the alert exists but is not published (subscriber cannot see unpublished alerts).

**Response `200 OK`:**
```json
{
  "id": 42,
  "title": "FBI warns of rising elder fraud losses...",
  "source_name": "FBI Press Releases",
  "item_url": "https://www.fbi.gov/news/...",
  "risk_level": "high",
  "primary_category": "Consumer Scam",
  "secondary_category": "Wire Fraud",
  "signal_score_total": 18,
  "summary": "The FBI reports a significant increase...",
  "processed_at": "2026-04-22T14:00:00Z",
  "published_at": "2026-04-22T14:35:00Z",
  "matched_keywords": ["elder fraud", "wire transfer"],
  "entities": ["FBI", "Western Union", "AARP"]
}
```

**Note:** `entities` is a flat `string[]` (unwrapped from the internal `{"names": [...]}` format). Internal scoring fields (`score_*`, `entities_json`, `ai_model`) are intentionally hidden from this endpoint.

**Errors:**
| Code | Reason |
|------|--------|
| `404` | Alert not found or not published |

---

## 5. Events

Events group related alerts about the same fraud incident across multiple sources.

**Auth required:** Any authenticated user

### 5.1 List Events
```
GET /api/v1/events
```

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `category` | string | Filter by event category |
| `risk_level` | string | Filter: `low`, `medium`, `high` |
| `limit` | int | Default `50`, max `200` |
| `offset` | int | Default `0` |

**Response `200 OK`:**
```json
[
  {
    "id": 7,
    "title": "Elder Fraud Wave Q1 2026",
    "risk_level": "high",
    "category": "Consumer Scam",
    "primary_entity": "Western Union",
    "first_detected_at": "2026-04-01T08:00:00Z",
    "last_updated_at": "2026-04-22T14:00:00Z",
    "source_count": 3
  }
]
```

---

### 5.2 Get Event Detail
```
GET /api/v1/events/{event_id}
```

**Response `200 OK`:**
```json
{
  "id": 7,
  "title": "Elder Fraud Wave Q1 2026",
  "risk_level": "high",
  "category": "Consumer Scam",
  "primary_entity": "Western Union",
  "first_detected_at": "2026-04-01T08:00:00Z",
  "last_updated_at": "2026-04-22T14:00:00Z",
  "source_count": 3,
  "alerts": [
    {
      "id": 42,
      "title": "FBI warns...",
      "risk_level": "high",
      "signal_score_total": 18,
      "is_published": true,
      "processed_at": "2026-04-22T14:00:00Z"
    }
  ]
}
```

**Errors:**
| Code | Reason |
|------|--------|
| `404` | Event not found |

---

## 6. Sources (Admin Settings)

Manage the scraping sources. Currently no auth guard — add auth guard before production exposure.

### 6.1 List Sources
```
GET /api/v1/sources
```

**Response `200 OK`:**
```json
[
  {
    "id": 1,
    "name": "FBI Press Releases",
    "base_url": "https://www.fbi.gov",
    "source_type": "html",
    "rss_url": null,
    "category": "Law Enforcement",
    "primary_focus": "Cybercrime, Fraud",
    "keywords": ["fraud", "scam", "cybercrime"],
    "is_active": true,
    "polling_frequency_minutes": 60,
    "adapter_class": "PlaywrightHTMLAdapter",
    "notes": null,
    "created_at": "2026-04-01T00:00:00Z",
    "updated_at": "2026-04-22T10:00:00Z"
  }
]
```

---

### 6.2 Get Source
```
GET /api/v1/sources/{source_id}
```
Returns single source. `404` if not found.

---

### 6.3 Update Source (Admin Settings)
```
PATCH /api/v1/sources/{source_id}
```
Partial update — only send fields you want to change.

**Request Body (all optional):**
```json
{
  "is_active": false,
  "polling_frequency_minutes": 120,
  "notes": "Temporarily disabled — site down"
}
```

**Response `200 OK`:** Updated `SourceRead` object.

---

### 6.4 Get Source Run History
```
GET /api/v1/sources/{source_id}/runs?limit=20
```

**Response `200 OK`:**
```json
[
  {
    "id": 55,
    "source_id": 1,
    "run_started_at": "2026-04-22T14:00:00Z",
    "run_finished_at": "2026-04-22T14:00:45Z",
    "status": "success",
    "items_fetched": 12,
    "items_new": 3,
    "items_duplicate": 9,
    "error_message": null
  }
]
```

---

### 6.5 Manually Trigger Source Collection
```
POST /api/v1/sources/{source_id}/trigger
```
Triggers a scraping run for one source in the background.

**Response `202 Accepted`:**
```json
{
  "message": "Collection triggered for source 'FBI Press Releases'",
  "source_id": 1
}
```

---

## 7. Raw Items & Stats

Internal pipeline data — useful for admin debugging.

### 7.1 List Raw Items
```
GET /api/v1/raw-items
```

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `source_id` | int | Filter by source |
| `is_duplicate` | bool | `true` / `false` |
| `since` | datetime | ISO 8601 — items fetched after |
| `limit` | int | Default `50`, max `500` |
| `offset` | int | Default `0` |

**Response `200 OK`:**
```json
[
  {
    "id": 101,
    "source_id": 1,
    "item_url": "https://www.fbi.gov/news/press-releases/...",
    "title": "FBI warns of rising elder fraud losses",
    "published_at": "2026-04-20T12:00:00Z",
    "content_hash": "abc123...",
    "url_hash": "def456...",
    "is_duplicate": false,
    "fetched_at": "2026-04-22T14:00:00Z"
  }
]
```

---

### 7.2 Get Raw Item Detail
```
GET /api/v1/raw-items/{item_id}
```
Includes `raw_text` and `raw_html` fields (full scraped content).

---

### 7.3 Get Pipeline Stats
```
GET /api/v1/stats
```
No auth required. Returns aggregate pipeline statistics.

**Response `200 OK`:**
```json
{
  "total_raw_items": 2847,
  "unique_items": 2103,
  "total_sources": 10,
  "active_sources": 10,
  "items_per_source": [
    { "source": "FBI Press Releases", "item_count": 312 },
    { "source": "FTC Consumer Alerts", "item_count": 287 }
  ]
}
```

---

## 8. Health Check

```
GET /api/v1/health
```
No auth required. Use for uptime monitoring / readiness checks.

**Response `200 OK`:**
```json
{
  "status": "ok",
  "env": "production",
  "database": "connected",
  "scheduler": "running"
}
```

**`status` values:** `ok` (all healthy) | `degraded` (DB unavailable)

---

## 9. HTML Dashboard Routes (Server-Rendered)

These are **not JSON API routes** — they return HTML pages rendered with Jinja2. Intended for the admin web UI. Frontend should not call these from React/Vue — use the JSON API routes instead.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/login` | Admin login page (HTML form) |
| `POST` | `/login` | Submit login form (admin only) |
| `GET` | `/logout` | Clear cookie, redirect to `/login` |
| `GET` | `/dashboard` | Alert index — HIGH/MEDIUM/LOW panels |
| `GET` | `/dashboard/alerts/{id}` | Alert detail with review form |
| `POST` | `/dashboard/alerts/{id}/review` | Submit review (form submit) |
| `GET` | `/dashboard/monitoring` | Source health + run log table |

> **For frontend development**, always use the `/api/v1/*` JSON endpoints, not these HTML routes.

---

## 10. Roles & Access Matrix

| Endpoint | `admin` | `subscriber` | No Auth |
|----------|---------|-------------|---------|
| `POST /api/v1/auth/login` | ✅ | ✅ | ✅ |
| `GET /api/v1/auth/me` | ✅ | ✅ | ❌ 401 |
| `GET /api/alerts` | ✅ | ✅ | ✅ |
| `GET /api/alerts/{id}` | ✅ | ✅ | ✅ |
| `GET /api/alerts/stats` | ✅ | ✅ | ✅ |
| `POST /api/v1/auth/change-password` | ✅ | ✅ | ❌ 401 |
| `GET /api/v1/alerts` | ✅ | ✅ | ❌ 401 |
| `GET /api/v1/alerts/{id}` | ✅ | ✅ | ❌ 401 |
| `POST /api/v1/alerts/{id}/review` | ✅ | ✅* | ❌ 401 |
| `POST /api/v1/alerts/process` | ✅ | ✅* | ❌ 401 |
| `GET /api/v1/client/alerts` | ✅ | ✅ | ❌ 401 |
| `GET /api/v1/client/alerts/{id}` | ✅ | ✅ | ❌ 401 |
| `GET /api/v1/events` | ✅ | ✅ | ❌ 401 |
| `GET /api/v1/events/{id}` | ✅ | ✅ | ❌ 401 |
| `GET /api/v1/sources` | ✅ | ✅ | ✅ |
| `PATCH /api/v1/sources/{id}` | ✅ | ✅ | ✅ |
| `POST /api/v1/sources/{id}/trigger` | ✅ | ✅ | ✅ |
| `GET /api/v1/raw-items` | ✅ | ✅ | ✅ |
| `GET /api/v1/stats` | ✅ | ✅ | ✅ |
| `GET /api/v1/health` | ✅ | ✅ | ✅ |

> *`✅*`* = technically allowed by current auth guard but admin-intended functionality.

---

## 11. Error Responses

All errors follow the standard FastAPI error format:

```json
{
  "detail": "Human-readable error message"
}
```

**Validation errors (422) include field-level detail:**
```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "new_password"],
      "msg": "String should have at least 8 characters",
      "input": "abc"
    }
  ]
}
```

**Common HTTP status codes:**
| Code | Meaning |
|------|---------|
| `200` | Success |
| `202` | Accepted (background task started) |
| `400` | Bad request (e.g. wrong current password) |
| `401` | Unauthenticated — missing or expired token |
| `403` | Forbidden — authenticated but insufficient role |
| `404` | Resource not found |
| `409` | Conflict (e.g. pipeline already running) |
| `422` | Validation error — check request body/params |
| `500` | Internal server error |

---

## 12. Frontend Integration Guide

### Setting Up Auth (Recommended Pattern)

```js
// auth.js
const API_BASE = 'http://localhost:8000/api/v1';

export async function login(email, password) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',  // enables cookie
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error('Login failed');
  const data = await res.json();
  // Save token for Bearer auth fallback
  localStorage.setItem('access_token', data.access_token);
  return data; // { access_token, user: { id, email, role, ... } }
}

export function getAuthHeaders() {
  const token = localStorage.getItem('access_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function logout() {
  localStorage.removeItem('access_token');
  // Cookie is HttpOnly so clear it server-side if needed,
  // or just navigate to /login (cookie expires with max-age)
}
```

### Role-Based Routing
```js
// After login, check role to determine which UI to show:
if (user.role === 'admin') {
  // Show admin dashboard: alerts list with review actions, sources settings
} else if (user.role === 'subscriber') {
  // Show subscriber feed: only published alerts via /client/alerts
}
```

### Admin Dashboard — Recommended Data Flow
```
1. Login → POST /api/v1/auth/login
2. Load dashboard → GET /api/v1/alerts?is_relevant=true&limit=50
3. Open alert → GET /api/v1/alerts/{id}
4. Review alert → POST /api/v1/alerts/{id}/review
5. View sources → GET /api/v1/sources
6. Edit source → PATCH /api/v1/sources/{id}
7. View stats → GET /api/v1/stats
```

### Subscriber App — Recommended Data Flow
```
1. Login → POST /api/v1/auth/login
2. Load feed → GET /api/v1/client/alerts?limit=20
3. Filter by risk → GET /api/v1/client/alerts?risk_level=high
4. Open alert → GET /api/v1/client/alerts/{id}
5. Filter by category → GET /api/v1/client/alerts?category=Cybercrime
```

### Pagination
```js
// Page 1: offset=0, Page 2: offset=50, Page 3: offset=100
async function loadAlerts(page = 1, limit = 50) {
  const offset = (page - 1) * limit;
  const res = await fetch(
    `/api/v1/client/alerts?limit=${limit}&offset=${offset}`,
    { headers: getAuthHeaders() }
  );
  return res.json();
}
```

### Risk Level Color Mapping (Suggested)
```js
const RISK_COLORS = {
  high:   '#DC2626', // red
  medium: '#D97706', // amber
  low:    '#2563EB', // blue
};

const RISK_LABELS = {
  high:   'High Risk',
  medium: 'Medium Risk',
  low:    'Low Risk',
};
```

### Categories Reference
The following `primary_category` values are used in the system:
- `Investment Fraud`
- `Cybercrime`
- `Consumer Scam`
- `Money Laundering`
- `Cryptocurrency Fraud`

---

## Appendix: Key Field Glossary

| Field | Type | Description |
|-------|------|-------------|
| `signal_score_total` | `int` (1–25) | Composite risk score from AI + heuristics |
| `relevance_score` | `float` (0.0–1.0) | `signal_score_total / 25` for frontend display |
| `risk_level` | `string` | `low` ≤8, `medium` 9–15, `high` ≥16 |
| `is_relevant` | `bool` | AI determined this alert is actionable |
| `is_published` | `bool` | Admin approved and published to subscriber feed |
| `primary_category` | `string` | Main fraud category |
| `secondary_category` | `string\|null` | Secondary category if applicable |
| `entities` | `string[]` | Named entities extracted by AI (subscriber view) |
| `entities_json` | `object\|null` | Raw AI entity output `{"names": [...]}` (admin view) |
| `matched_keywords` | `string[]` | Keywords that triggered this alert |
| `source_count` | `int` | How many sources reported the same event |
| `score_source_credibility` | `int` (1–5) | Credibility of originating source |
| `score_financial_impact` | `int` (1–5) | Estimated financial damage score |
| `score_victim_scale` | `int` (1–5) | Number/scale of victims |
| `score_cross_source` | `int` (1–5) | How many sources corroborate |
| `score_trend_acceleration` | `int` (1–5) | Rate of increase in reports |
