# HiddenAlerts API Contract V2

> ## ⚠️ Superseded in part by developments done on 6 August 2026
>
> This document describes the M3-era contract. The following sections are
> **historical implementation,** and now return **404**:
>
> | Retired | Current replacement |
> |---|---|
> | `GET /api/alerts/top` | `GET /api/v1/subscriber/alerts/top` |
> | `GET /api/alerts/{id}` | `GET /api/v1/subscriber/alerts/{alert_id}` |
> | `GET /api/alerts/stats` | `GET /api/v1/subscriber/alerts/stats` |
> | `GET /api/search/alerts` | `GET /api/v1/subscriber/search/alerts` |
> | Server-rendered dashboard at `/dashboard`, `/login`, `/logout` | React Admin UI over the Internal-JWT Admin APIs |
>
> **`GET /api/alerts` is retained** as the Landing Page feed, but its contract
> changed on 08 August 2026 — it is now a **marketing teaser**, not a public
> intelligence API. See §0.1 below. Admin, Subscriber, Client, Billing,
> category-metadata, Source Health and Intelligence Brief APIs are all retained.
> Shared Internal JWT authentication is unchanged. Client APIs were **not** removed.
>
> **`GET /api/v1/subscriber/alerts/top`** gained a transparent historical
> fallback and two response fields on the same date. See §0.2 below.
>
> For the current surface see `README.md` and the live OpenAPI at
> `https://api.hiddenalerts.com/docs`.
>
> ## ⚠️ Superseded further on 18 August 2026 — `risk_band` is now the ONLY risk filter on the active Admin and Subscriber Alerts APIs
>
> A production bug was fixed: the Subscriber API used to **recompute** a risk
> band from `signal_score_total` at read time, while the Admin API read the
> **stored** `processed_alerts.risk_band` column — the two disagreed on which
> alerts were "Critical" / "High" for any row where the stored band was still
> `NULL`. That is fixed. **`processed_alerts.risk_band` is now the sole
> canonical source for band/badge purposes on both the Admin and Subscriber
> APIs, always. Nothing recomputes a band from score at read time, anywhere.**
>
> This section of the document (and every section below that touches
> risk/score/band) has been rewritten accordingly. In particular, throughout
> this document below §0, wherever you see historical text describing
> `risk_level` bands (`low`/`medium`/`high` from a score) as something the
> server "re-derives on every read" or as a **filter parameter**, that
> description is now **wrong** and describes the bug that was just fixed — it
> is left in place only inside sections already marked **retired/404** above,
> as a historical record of what the old, no-longer-reachable routes used to
> do. Current, live endpoints are documented fresh, below.
>
> **The final contract, no transition window:**
> - Both `GET /api/v1/alerts` (Admin) and `GET /api/v1/subscriber/alerts`
>   (Subscriber) accept **one** risk filter: `risk_band`, an enum of exactly
>   `critical` | `high` | `medium` | `below_60`. Typed in OpenAPI — Swagger
>   renders it as a dropdown.
> - There is **no** `risk_level` filter on either endpoint, no
>   `risk_level`→`risk_band` translation, no `low`→`below_60` alias, no
>   dual-parameter compatibility mode, no fallback for an outdated frontend.
>   This is final — do not send `risk_level` as a filter to either endpoint.
> - `risk_level` still appears on some response bodies as a **display-only**
>   legacy field (and as `adjusted_risk_level` on the manual-review request
>   body) — it is never authoritative for badges, filtering, or eligibility.
>   See the rewritten "Risk Band & Risk Level" section right below the Table
>   of Contents.
> - The unrelated `GET /api/v1/events` route has its own separate `risk_level`
>   query param — a different feature entirely, not part of this contract, not
>   to be conflated with alert risk_band/risk_level.
> - The retained hidden /api/v1/client/alerts endpoint still has its legacy
>   risk_level filter. For low, medium and high it filters using the legacy
>   score-derived display bands from signal_score_total. It is not part of the
>   current frontend contract and must not be used as a model for the Admin or
>   Subscriber APIs.

**Last updated:** 18 August 2026  
**Version:** 0.3.1  
**Base URL:** `http://localhost:8000` (local dev)  /  `https://api.hiddenalerts.com` (production — the API host;
the marketing site at `https://hiddenalerts.com` is a separate frontend, not the REST API)  
**Interactive docs (Swagger UI):** `https://api.hiddenalerts.com/docs`  
**API Prefix:** Most versioned application APIs live under `/api/v1`. The public Landing Page teaser is GET /api/alerts.

**Backend contact:** Adnan

## Overview

- **Admin surface** — Ken and internal admins. Full access to all alerts, review workflow, and the Intelligence Brief
  CMS. Served by the React Admin UI over the Internal-JWT Admin APIs, which require an Internal JWT (cookie or
  Bearer) **and** `role == "admin"` (`require_admin`) — a valid Internal JWT for a non-admin account gets 403.
  This became uniform across the whole Admin surface with the Pre-Launch Admin Authorization Hardening slice
  (18 August 2026); see §3's auth note and §10's route inventory for the exact per-route guard. The
  server-rendered `/dashboard` was retired by 06 August 2026 and there is no server-rendered UI anymore — do not
  reference "the dashboard" as a real current surface.
- **Subscriber surface** — Paying end users. Curated, **published-only** alerts and Intelligence Briefs through
  `GET /api/v1/subscriber/*`. Requires a Supabase JWT **and** an active subscription (`require_active_subscription`)
  on every content route except `/me` and `/access`, which only need a valid Supabase token.
- **Public feed** — `GET /api/alerts`, unauthenticated. A **marketing teaser** for the Landing Page (max 3 items, a
  narrow field set) — not a general public intelligence API. See §0.1.

Admin and Subscriber use **different token systems** (Internal JWT vs. Supabase JWT) — they are not interchangeable,
unlike an earlier draft of this document implied.

---

## Table of Contents

0. [**Public Feed — Current Frontend MVP Endpoints**](#0-public-feed--current-frontend-mvp-endpoints)
    - [Risk Band (canonical) & Risk Level (legacy display)](#risk-band-canonical--risk-level-legacy-display-updated-18-august-2026)
    - [GET /api/alerts *(marketing teaser)*](#01-get-apialerts--public-marketing-teaser)
    - [GET /api/v1/subscriber/alerts/top *(primary + fallback)*](#02-get-apiv1subscriberalertstop--top-alerts-this-week)
    - [Retired public endpoints *(404, historical)*](#03-retired-public-endpoints)
1. [Internal JWT Authentication Overview](#1-authentication-overview)
2. [Auth Endpoints](#2-auth-endpoints)
3. [Alerts — Admin](#3-alerts--admin)
4. [Alerts — Subscriber](#4-alerts--subscriber)
5. [Events *(hidden/internal)*](#5-events-hidden-internal)
6. [Sources (Admin Settings) *(hidden/internal)*](#6-sources-admin-settings-hidden-internal)
7. [Raw Items & Stats *(hidden/internal)*](#7-raw-items--stats-hidden-internal)
8. [Health Check *(hidden/internal)*](#8-health-check-hidden-internal)
9. [HTML Dashboard Routes](#9-html-dashboard-routes-server-rendered)
10. [Full Route Inventory & Roles/Access Matrix](#10-full-route-inventory--rolesaccess-matrix)
11. [Error Responses](#11-error-responses)
12. [Integration Guide](#12-frontend-integration-guide)

---

## 0. Public Feed

> **Hasnain: current frontend endpoints, current-first.** None of the four routes in the old "MVP phase" table below
> are what you should be integrating today — three are 404 and the fourth changed shape. Use this instead:
>
> | Surface | Endpoint | Auth |
> |---|---|---|
> | Public Landing teaser | `GET /api/alerts` | None — max 3 narrow teaser items, §0.1 |
> | Subscriber alerts feed | `GET /api/v1/subscriber/alerts` | Supabase JWT + active subscription, §4.1 |
> | Subscriber alert detail | `GET /api/v1/subscriber/alerts/{alert_id}` | Supabase JWT + active subscription, §4.2 |
> | Subscriber Top Alerts | `GET /api/v1/subscriber/alerts/top` | Supabase JWT + active subscription, §0.2 / §4.5 |
> | Subscriber stats | `GET /api/v1/subscriber/alerts/stats` | Supabase JWT + active subscription, §4.3 |
> | Subscriber search | `GET /api/v1/subscriber/search/alerts` | Supabase JWT + active subscription, §4.6 |
> | Admin review (internal tooling, not the paid frontend) | `GET /api/v1/alerts`, `POST /api/v1/alerts/{alert_id}/review` | Internal JWT + `role == "admin"` (`require_admin`) — see §3 |
>
> `GET /api/alerts` is **not** a general paginated feed — it's a narrow, unauthenticated marketing teaser (max 3
> items) for the Landing Page only. Do not build the paid Alerts Page against it. See §0.3 for what the old
> four-endpoint table used to point at and why those routes 404 now.

Base URL: `http://localhost:8000` (local) / `https://api.hiddenalerts.com` (production — the API host, distinct from
the marketing site at `https://hiddenalerts.com`). Public teaser example: `https://api.hiddenalerts.com/api/alerts`.

---

### Risk Band (canonical) & Risk Level (legacy display) — updated 18 August 2026

**`risk_band` is the single source of truth for badges, filtering, and eligibility on every active, documented
Alerts surface** — Admin Alerts (§3), Subscriber Alerts (§4), Subscriber Top Alerts, and the public Landing teaser
(§0.1). It is a stored column, `processed_alerts.risk_band`, with exactly four values:

| Band        | Score (0–100) | Internal 5–25 sum |
|-------------|---------------|--------------------|
| `critical`  | 80 – 100      | ≥ 20               |
| `high`      | 70 – 79       | 18 – 19            |
| `medium`    | 60 – 69       | 15 – 17            |
| `below_60`  | < 60 (or unset) | ≤ 14 / `NULL`    |

- **Never recomputed from `signal_score_total` at read time, on any endpoint.** The band is materialized once, at
  write time only — pipeline scoring, a manual admin review action, or the one-time legacy-row normalization tool —
  and every read path (Admin list/detail, Subscriber list/detail/top/stats) reports that stored value verbatim,
  including `null` for a row the normalization tool hasn't reached yet. A `null` band is reported as `null`, never
  guessed from the score.
- This is the fix for a real bug: the Subscriber API used to recompute a band from score at query time while the
  Admin API read the stored column, so the two surfaces could disagree on which alerts were Critical/High for any row
  whose stored band was `NULL`. That inconsistency is gone — both APIs now read the exact same stored value.
- **Both `GET /api/v1/alerts` (Admin) and `GET /api/v1/subscriber/alerts` (Subscriber) accept exactly one risk
  filter, `risk_band`**, typed as an enum of the four values above (OpenAPI renders it as a Swagger dropdown). There
  is no `risk_level` filter on either endpoint — do not send one, and do not attempt a `low`→`below_60` or
  `high`→`high` "compatibility" translation on the frontend; there is no transition window, this is the final contract.
- **Auto-publish policy:** `critical` and `high` bands auto-publish; `medium` goes to manual admin review; `below_60` is excluded from publication.

**`risk_level` still exists, display-only.** It's a legacy `low`/`medium`/`high` value retained on some response
models purely for backward display compatibility (and as `adjusted_risk_level` on the manual-review request body —
see §3.3). It is **not** authoritative for any badge, filter, or eligibility decision — treat it as a secondary,
cosmetic field if your UI still references it, and prefer `risk_band` for anything that drives logic. Where
`risk_level` is returned, it is still derived from `signal_score_total` for **display purposes on the Admin surface
only** (so an admin reviewer sees a live score-consistent value even for a pre-normalization row) — this has no
bearing on badges/filtering on the **active Admin and Subscriber Alerts APIs**, which are `risk_band`-only. (The
hidden, transitional Client API is a documented exception — see directly below.)

> The unrelated `GET /api/v1/events` route (hidden/internal, §5) has its own separate `risk_level` query param — a
> different feature, different field, not part of this contract. Don't conflate the two.
>
> **Exception, do not build against this:** the hidden, transitional `GET /api/v1/client/alerts` (§10 — no known
> frontend consumer, `include_in_schema=False`) still has its own separate, untouched `risk_level` list filter
> (`_score_filter_for_risk_level` in `app/api/client_alerts.py`). For `low`/`medium`/`high` it is **score-derived**
> from `signal_score_total` (the same internal 5–25 thresholds as the old M3 bands) — **not** a match against the
> stored `risk_level` column; any other value falls back to a literal `risk_level` column comparison, which matches
> nothing for the three documented values. It predates this contract and was intentionally left alone — it is not
> part of the Admin/Subscriber `risk_band` contract above and must not be used as a model for either. Use
> `GET /api/v1/subscriber/alerts` instead.

**Three distinct timestamps, never aliased** — this recurs on every alert-bearing endpoint below:

| Field | Meaning | What filters/sorts on it |
|---|---|---|
| `published_at` | When **HiddenAlerts itself** published the alert. | Canonical Published ordering sorts on this. `published_from`/`published_to` filter this. |
| `source_published_at` | The original source article's own publish date (from the raw item / RSS). | `source_published_from`/`source_published_to` filter this. Never substituted for `published_at`. |
| `processed_at` | When HiddenAlerts processed/ingested the item. | Admin's `start_date`/`end_date` (aliases `since`/`end_date`) filter this — an Admin-**operational** filter, not the same thing as `published_from`/`published_to`. |

**Canonical Published ordering** (Admin's `is_published=true` view **and** the Subscriber feed — identical):
`published_at DESC NULLS LAST, processed_at DESC, id DESC`. The trailing `id DESC` is a deterministic tie-breaker for
rows sharing identical timestamps.

**Admin operational ordering** (`GET /api/v1/alerts`, when not viewing the Published subset):
- `is_published=false` or a specific `publish_decision` given → `processed_at DESC, id DESC`.
- Neither filter given ("All Status") → `COALESCE(published_at, processed_at) DESC, processed_at DESC, id DESC`, so a
  brand-new Draft/Review item isn't buried behind months of Published history.

---

### 0.1 GET /api/alerts — Public Marketing Teaser

> **Changed 08 August 2026.** This route is a **marketing teaser for the Landing
> Page, not a public intelligence API.** It returns at most **3** alerts and only
> teaser-level fields. Complete alert intelligence — scores, source attribution,
> credibility, entities, evidence, analysis and review state — remains
> **subscriber-authenticated** under `/api/v1/subscriber/*`.

**Selection, ordering and display** all use `ProcessedAlert.published_at`
(HiddenAlerts publication time) descending, then id — the teaser is a freshness
signal about what *we* published, so the card date and the ranking are the same
value and cannot disagree. The original article date is not exposed here; the
subscriber feed keeps that distinction. Maximum 3, enforced server-side.

```json
{
  "alerts": [
    {
      "title": "SEC Charges Investment Firm with $4.2M Fraud",
      "risk_band": "critical",
      "category": "Investment Fraud",
      "published_at": "2026-04-22T10:30:01Z",
      "summary": "The SEC charged a New York-based firm with defrauding investors. The complaint alleges losses exceeding $4.2 million across 300 accounts.…"
    }
  ]
}
```

### Field Reference

| Field          | Type             | Description                                                                                     |
|----------------|------------------|-------------------------------------------------------------------------------------------------|
| `title`        | `string\|null`   | Article / press-release title                                                                    |
| `risk_band`    | `string\|null`   | Canonical V1 band — `"critical"` or `"high"`. This is the public presentation field.             |
| `category`             | `string\|null`   | Fraud category                                                                                   |
| `published_at`         | `datetime\|null` | ISO 8601 UTC — **HiddenAlerts publication time. This is the card date**, and the same value used to select and order the teaser. Never null for a published alert. |
| `summary`              | `string\|null`   | Preview of the stored summary: at most 2 sentences and **at most 320 characters including the `…`**, appended only when text was removed |

### Deliberately withheld

`id`, `signal_score`, `risk_level` (legacy), `source_name`, `source_url`,
`source_published_at` (the original article date — shown on subscriber surfaces,
not on the public card), credibility, entities, evidence, risk explanation, full
analysis, review state and every publication internal. These are available to
authenticated subscribers only.

### Optional Query Parameters

| Param   | Type | Example       | Description                                                                     |
|---------|------|---------------|---------------------------------------------------------------------------------|
| `limit` | int  | `?limit=2`    | Accepted for compatibility. Can only **lower** the count — a request for 10, 100 or 500 still returns at most 3. |

`risk_level`, `category`, `source` and `offset` are no longer meaningful for a
3-item teaser and are not part of the contract.

### Quick Test

```bash
# Landing teaser — at most 3 Critical/High alerts
curl http://localhost:8000/api/alerts

# The cap is server-side: this still returns at most 3
curl "http://localhost:8000/api/alerts?limit=100"
```

---

### 0.2 GET /api/v1/subscriber/alerts/top — Top Alerts This Week

Requires an active subscription. Returns at most **3** alerts.

**Primary rule:** published alerts whose **stored** `risk_band` column is `critical` or `high` — never recomputed
from score — and whose HiddenAlerts `published_at` falls in the rolling last **7 days**, ordered Critical before
High, then score descending, then `published_at` descending, then id. Historical bulk publications
(`candidate_backfill`, `system_migration`) are excluded. Historical (pre-7-day) alerts are excluded from this primary
result set — they only ever appear via the fallback below.

**Fallback:** engages **only when the primary rule returns zero alerts**. One or two current alerts are returned
exactly as found — the widget is **never padded** to fill 3, because presenting an older alert alongside this week's
would misrepresent it as equally current. When the 7-day window is completely empty, the latest qualifying (stored
`risk_band` `critical`/`high`) alerts are returned instead, ordered by `published_at` descending, with
`is_fallback: true` and an explanatory `message`.

All other eligibility rules are identical in both paths; the fallback widens only the date range.

Items are mapped through the exact same field mapper the paginated Subscriber feed (§4.1) uses — `published_at`,
`source_published_at`, and `processed_at` follow the identical three-timestamp contract as the list; `published_at`
is never overwritten with `source_published_at` here (a previous version of this widget had that bug; it is fixed).

**Current-data response:**

```json
{
  "alerts": [ { "id": 1312, "title": "…", "risk_band": "critical", "risk_level": "high", "signal_score": 80, "category": "Investment Fraud", "source_name": "FBI National Press Releases", "source_url": "https://www.fbi.gov/…", "source_published_at": "2026-04-06T11:33:00Z", "published_at": "2026-04-06T11:33:00Z", "processed_at": "2026-04-06T11:40:12Z", "summary": "…" } ],
  "is_fallback": false,
  "message": null
}
```

**Historical-fallback response:**

```json
{
  "alerts": [ { "id": 1084, "title": "…", "risk_band": "high", "…": "…" } ],
  "is_fallback": true,
  "message": "No new Critical or High alerts have been published during the past seven days. The latest published intelligence is shown below."
}
```

| Field         | Type            | Description                                                                     |
|---------------|-----------------|---------------------------------------------------------------------------------|
| `alerts`      | `array`         | Subscriber alert items (§4.1 shape) — `risk_band` is the canonical badge field; `risk_level` is legacy display-only and NOT what gated eligibility for this widget |
| `is_fallback` | `bool`          | `true` when the items came from outside the rolling 7-day window                 |
| `message`     | `string\|null`  | Explanatory text to display; `null` unless `is_fallback` is `true`               |

Both metadata fields are **additive** and default to the non-fallback values, so a
client that ignores them sees the payload it always did. If no qualifying alert
exists at all, `alerts` is empty and `is_fallback` is `false` — an empty widget
never claims intelligence is shown.

**Frontend requirement:** when `is_fallback` is `true`, display `message` above
the list. Otherwise show no notice. Alert rendering is otherwise unchanged.


### Notes for Hasnain

- Results are sorted newest-published first.
- If `"alerts": []`, no alerts have been published yet — the admin reviews and publishes them.
- Do NOT use `/api/v1/alerts` or `/api/v1/client/alerts` for this phase — those require auth.
- This teaser does not expose `risk_level` at all (see "Deliberately withheld" above) — only `risk_band`
  (`"critical"` or `"high"`, since the teaser only selects strong alerts). There is **no filter parameter** on this
  endpoint for risk at all — see "Optional Query Parameters" above.
- `signal_score` is the **0–100 frontend score** — render it directly on the badge / progress bar. The 5-factor internal
  sum (5–25) is normalized server-side and never exposed in API responses.
- Category values: `Investment Fraud`, `Cybercrime`, `Consumer Scam`, `Money Laundering`, `Cryptocurrency Fraud`,
  `Other`.
  `Other` is a real value — when shown, render it as a low-emphasis label (don't promote it to a primary fraud-type
  badge).
- **`published_at` and `source_published_at` are both real, displayable dates with distinct meanings — do not
  substitute one for the other, and do not treat `published_at` as merely an internal sort key:**
  - `published_at` = **Published by HiddenAlerts** — when HiddenAlerts itself published the alert. This is also
    what canonical Published ordering sorts on (`published_at DESC NULLS LAST, processed_at DESC, id DESC`), so
    the field that orders the feed and the field you'd label "Published by HiddenAlerts" are the same one.
  - `source_published_at` = **Original Source Date** — the original article/press-release date, per the source.
  - `processed_at` = when HiddenAlerts processed the source item (a backend timestamp — useful for a fuller detail
    view, not usually the headline date on a card).
  - Which one to feature on a card is a product/UX choice, not a backend constraint — either is a legitimate,
    intentional display date. Whichever is shown, label it accurately (e.g. "Published by HiddenAlerts" vs.
    "Original Source Date") rather than presenting one as if it were the other or leaving it unlabeled.

---

### 0.3 Retired Public Endpoints

> **404 today.** These existed under the old M3-era public contract and were removed by 06 August 2026 (Slice
> 3B.2P). Full historical documentation — request/response shapes, worked examples — is not repeated here; it is
> preserved in Git history (this file's state before 06 August 2026) if it's ever needed for archaeology. What
> Hasnain needs is just the replacement:

| Retired route | Returns today | Current replacement |
|---|---|---|
| `GET /api/alerts/{id}` | 404 | `GET /api/v1/subscriber/alerts/{alert_id}` (§4.2) — Supabase JWT + active subscription |
| `GET /api/alerts/top` | 404 | `GET /api/v1/subscriber/alerts/top` (§0.2 / §4.5) — Supabase JWT + active subscription |
| `GET /api/alerts/stats` | 404 | `GET /api/v1/subscriber/alerts/stats` (§4.3) — Supabase JWT + active subscription |
| `GET /api/search/alerts` | 404 | `GET /api/v1/subscriber/search/alerts` (§4.6) — Supabase JWT + active subscription |

Every replacement above requires a Supabase JWT and an active subscription — none of these are unauthenticated
successors to the old public routes. If your integration still calls any left-hand route, it is broken today, not
merely deprecated.

---


## 1. Internal JWT Authentication Overview

The Internal Admin/account API uses the HiddenAlerts JWT described below.
The paid Subscriber API uses the separate Supabase JWT system documented
in Section 4. The two token systems are not interchangeable.

### How Auth Works

The API uses **JWT Bearer tokens**. On successful login, a token is returned in the JSON body **and** set as an
`HttpOnly` cookie named `access_token`.

Frontend can authenticate requests in **two ways** (pick one per request):

| Method       | Header/Cookie                   | Example             |
|--------------|---------------------------------|---------------------|
| Bearer token | `Authorization: Bearer <token>` | API clients, mobile |
| Cookie       | `Cookie: access_token=<token>`  | Web browsers        |

### Token Lifetime

- **30 days** (`expires_in` is returned in seconds from login response)
- No refresh token endpoint currently — re-login when expired

### Roles

| Role         | Access                                  |
|--------------|-----------------------------------------|
| `admin`      | All endpoints                           |
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
| Code | Reason | |------|--------| | `401` | Invalid email or password |

**Cookie set on success:**

```
Set-Cookie: access_token=<token>; HttpOnly; SameSite=Lax; Max-Age=2592000
```

**Usage example:**

```js
const res = await fetch('/api/v1/auth/login', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    credentials: 'include', // sends/receives cookies
    body: JSON.stringify({email, password})
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
| Code | Reason | |------|--------| | `401` | Not authenticated or token expired |

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
| Code | Reason | |------|--------| | `400` | Current password is incorrect | | `401` | Not authenticated | | `422` |
`new_password` shorter than 8 characters |

> **Note:** Password reset (forgot password) via email is not yet implemented. This endpoint only works for
> authenticated users who know their current password.

---

## 3. Alerts — Admin

These endpoints return **all** alerts (published and unpublished) and are intended for the admin review workflow —
the React Admin UI, not any server-rendered page.

**Auth required:** Internal JWT (cookie or Bearer) **and** `role == "admin"` (`require_admin`) — the same guard
every other Admin management surface uses (`/api/v1/admin/*`, Sources, Raw Items, Stats, Source Health, the
Intelligence Brief CMS). Applies to `GET /api/v1/alerts`, `GET /api/v1/alerts/{alert_id}`,
`POST /api/v1/alerts/{alert_id}/review`, and — hidden from Swagger but still live, see §5/§7 — the manual
processing trigger `POST /api/v1/alerts/process` and the Event routes `GET /api/v1/events*`.

- **401** — missing, invalid, or expired Internal JWT.
- **403** — a valid Internal JWT for an authenticated account whose role is not `admin`.
- **200** (or the route's normal success status) — a valid Internal JWT for an `admin` account, exactly the
  existing query/response behavior.

This was hardened from an any-authenticated-Internal-JWT-user guard (`get_current_user`, no role check) to
`require_admin` by the Pre-Launch Admin Authorization Hardening slice (18 August 2026), closing the one
inconsistency against the rest of the Admin surface. No path, method, query parameter, request body, or response
field changed — the only consumer-visible difference is that a non-admin Internal account that previously
succeeded now correctly gets 403. `GET /api/v1/auth/me` and `POST /api/v1/auth/change-password` are the one
legitimate exception left on the older `get_current_user` guard — they are account/identity operations available
to any authenticated Internal JWT user, not Admin management operations, and were deliberately left unchanged.

### 3.1 List Alerts

```
GET /api/v1/alerts
```

**Query Parameters** (all optional):

| Param | Type | Description |
|---|---|---|
| `category` | string | Filter by `primary_category` (exact match) |
| `source_id` | int | Filter by source ID |
| `source` | string | Partial, case-insensitive source name search |
| `keyword` | string | Matches title OR `matched_keywords` (case-insensitive) |
| `start_date` (alias of internal `since`) | datetime | Admin-**operational** filter on `processed_at` (when we processed the item) — not the same as `published_from` |
| `end_date` | datetime | Also filters `processed_at` |
| `published_from` / `published_to` | datetime | Alerts HiddenAlerts published on/after / on/before this instant (`published_at`) |
| `source_published_from` / `source_published_to` | datetime | Alerts whose source article was published on/after / on/before this instant (`source_published_at`) |
| `is_relevant` | bool | `true` / `false` |
| `is_published` | bool | `true` / `false` — `true` uses the same canonical Published predicate as the Subscriber feed |
| `publish_decision` | string | `auto_publish` \| `review` \| `exclude` \| `hold` |
| `pending_review_reason` | string | V1 pending-review reason enum |
| `risk_band` | enum | **The only risk filter.** `critical` \| `high` \| `medium` \| `below_60`. Typed in OpenAPI — Swagger renders a dropdown. Always the stored column; never recomputed from `signal_score_total`. There is no `risk_level` filter. |
| `is_excluded` | bool | Filter excluded alerts |
| `is_manual_hold` | bool | Filter manually-held alerts |
| `published_by_rule` | bool | Filter auto-policy-published alerts |
| `publication_state_source` | string | `auto_policy` \| `manual_admin` \| `candidate_backfill` \| `system_migration` |
| `limit` | int | Default `50`, max `500` |
| `offset` | int | Default `0` |

An invalid `publish_decision` / `pending_review_reason` / `publication_state_source` value gets a `422` with the
allowed set in the error detail. An invalid `risk_band` is rejected by FastAPI's enum validation before the handler
runs.

**Ordering** (no `sort` param — always one of these three, chosen by which filters are present):
- `is_published=true` → **canonical Published ordering**, identical to the Subscriber feed:
  `published_at DESC NULLS LAST, processed_at DESC, id DESC`.
- `is_published=false` or a specific `publish_decision` given → `processed_at DESC, id DESC`.
- Neither given ("All Status") → `COALESCE(published_at, processed_at) DESC, processed_at DESC, id DESC`.

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
    "signal_score_total": 72,
    "relevance_score": 0.72,
    "matched_keywords": ["elder fraud", "wire transfer"],
    "is_relevant": true,
    "processed_at": "2026-04-22T14:00:00Z",
    "source_published_at": "2026-04-20T09:00:00Z",
    "is_published": false,
    "published_at": null,
    "risk_band": "high",
    "publish_decision": "review",
    "publish_decision_reason": "medium_band_manual_review",
    "pending_review_reason": "medium_band",
    "is_excluded": false,
    "excluded_reason": null,
    "is_manual_hold": false,
    "published_by_rule": null,
    "publishing_policy_version": "v1",
    "publication_state_source": "auto_policy",
    "publication_state_updated_at": "2026-04-22T14:00:05Z"
  }
]
```

**Field Reference:**

| Field | Description |
|---|---|
| `risk_band` | **Canonical.** Straight off the stored `processed_alerts.risk_band` column, verbatim — `null` means the row hasn't been normalized yet, never guessed from score. This is what review-queue filtering and Critical/High/Medium badges are driven by. |
| `risk_level` | Legacy, **display-only**. On this endpoint it's re-derived from `signal_score_total` at read time purely so an admin reviewer always sees a score-consistent value even for a pre-normalization row — this has **no** effect on badges/filtering/eligibility, which are `risk_band`-only. Do not treat this field as authoritative for anything. |
| `signal_score_total` | Risk score on the 0–100 frontend scale, normalized server-side from the internal 5-factor sum (DB column stays 5–25 internally). |
| `relevance_score` | Legacy ratio (`internal_sum / 25`, 0.0–1.0). Not for risk badge/level logic — prefer `signal_score_total` / `risk_band`. |
| `publish_decision`, `publish_decision_reason`, `pending_review_reason`, `is_excluded`, `excluded_reason`, `is_manual_hold`, `published_by_rule`, `publishing_policy_version`, `publication_state_source`, `publication_state_updated_at` | V1 publication-state fields, admin-only visibility, mirroring the `processed_alerts` columns so a review queue can see *why* an alert is in its current state without opening the detail page. |
| `is_published` | Whether the alert is currently published to the Subscriber feed |
| `is_relevant` | Whether AI determined the alert is relevant |

---

### 3.2 Get Alert Detail (Admin)

```
GET /api/v1/alerts/{alert_id}
```

**Response `200 OK`** — Everything from §3.1 plus AI output, score breakdown, event linkage, and a deterministic
`risk_explanation` object:

```json
{
  "id": 42,
  "raw_item_id": 101,
  "title": "FBI warns of rising elder fraud losses...",
  "source_name": "FBI Press Releases",
  "item_url": "https://www.fbi.gov/news/...",
  "risk_level": "high",
  "risk_band": "high",
  "primary_category": "Consumer Scam",
  "secondary_category": "Wire Fraud",
  "signal_score_total": 72,
  "relevance_score": 0.72,
  "matched_keywords": ["elder fraud", "wire transfer"],
  "is_relevant": true,
  "processed_at": "2026-04-22T14:00:00Z",
  "source_published_at": "2026-04-20T09:00:00Z",
  "is_published": false,
  "published_at": null,
  "publish_decision": "review",
  "pending_review_reason": "medium_band",
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
  "review_status": "approved",
  "published_by_user_id": null,
  "risk_explanation": {
    "score_total": 18,
    "score_100": 72,
    "risk_level": "high",
    "risk_band": "high",
    "factors": {
      "source_credibility": 5,
      "financial_impact": 5,
      "victim_scale": 4,
      "cross_source": 3,
      "trend_acceleration": 1
    },
    "publication_decision": "review",
    "publication_reason": "medium_band_manual_review",
    "pending_review_reason": "medium_band",
    "source": "FBI Press Releases",
    "source_credibility": 5
  }
}
```

`risk_explanation.risk_band` is the stored column reported verbatim (never guessed from `score_100`); `null` means
not-yet-normalized, not "unqualified." `risk_explanation.risk_level` is still score-derived here too — it's part of
the same display-only explanation, not an eligibility signal.

**Errors:**
| Code | Reason |
|---|---|
| `404` | Alert not found |

---

### 3.3 Submit Alert Review (Admin)

```
POST /api/v1/alerts/{alert_id}/review
```

Admin review action. Approving a relevant alert publishes it (and reconciles its V1 publication state — sets
`risk_band` from the stored score, `publish_decision=auto_publish`, `publication_state_source=manual_admin`, etc.).
Marking `false_positive` unpublishes and excludes it.

**Request body — `AlertReviewCreate`:**

```json
{
  "review_status": "approved",
  "edited_summary": "Optional — override AI summary",
  "adjusted_risk_level": "high"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `review_status` | enum | yes | `approved` \| `false_positive` \| `edited`. `approved` publishes the alert if `is_relevant=true` and not already published. `false_positive` marks it not relevant and unpublishes/excludes it. `edited` saves edits without touching publication state. |
| `edited_summary` | string \| null | no | Replacement summary, applied for any decision when present. |
| `adjusted_risk_level` | enum \| null | no | `low` \| `medium` \| `high` \| `critical`. Case-insensitive, stored lower-cased. **Overrides the alert's legacy `risk_level` field only** — display metadata for the reviewer, not a `risk_band` write and not what drives the Critical/High badge. Do not describe this field as controlling publication badges. |

**Response `200 OK` — `AlertReviewRead`:**

```json
{
  "id": 15,
  "alert_id": 42,
  "user_id": 1,
  "review_status": "approved",
  "edited_summary": null,
  "adjusted_risk_level": "high",
  "reviewed_at": "2026-04-22T14:30:00Z"
}
```

**Errors:**
| Code | Reason |
|---|---|
| `404` | Alert not found |
| `422` | Invalid `review_status` or `adjusted_risk_level` value |

---

### 3.4 Trigger Pipeline (Admin) — hidden from Swagger

```
POST /api/v1/alerts/process
```

`include_in_schema=False` — still fully live and admin-authenticated at runtime, just not shown in the Swagger UI.
Operational/internal; not something Hasnain should wire into the frontend. Manually triggers the AI processing
pipeline for unprocessed raw items, in the background.

**Response `202 Accepted`:**

```json
{ "message": "Alert processing started", "status": "accepted" }
```

**Errors:**
| Code | Reason |
|---|---|
| `409` | Pipeline already running |

---

## 4. Alerts — Subscriber

`GET /api/v1/subscriber/*` — the real subscriber alert surface. Only ever returns **published** alerts. Requires a
**Supabase JWT** (different token system from Admin's Internal JWT) plus, on every route in this section, an
**active subscription** (`require_active_subscription`).

> Do not confuse this with `GET /api/v1/client/alerts*` — a separate, hidden-from-Swagger, transitional internal API
> with no known frontend consumer. It is not documented further here; `GET /api/v1/subscriber/alerts*` below is the
> path to integrate against.

> **Risk fields:** `signal_score_total` / `signal_score` are already normalized to the 0–100 frontend scale.
> `risk_band` (`critical`/`high`/`medium`/`below_60`) is the canonical, stored-column badge/filter field — never
> recomputed from score. `risk_level` (legacy `low`/`medium`/`high`) is present on some items purely for backward
> display compatibility; it is not authoritative and there is no `risk_level` filter on this API.

### 4.1 List Published Alerts

```
GET /api/v1/subscriber/alerts
```

**Query Parameters** (all optional):

| Param | Type | Description |
|---|---|---|
| `risk_band` | enum | `critical` \| `high` \| `medium` \| `below_60`. The same canonical parameter Admin accepts. Typed enum in OpenAPI. **No `risk_level` filter exists.** |
| `category` | string | Exact match |
| `source` | string | Partial source name search |
| `published_from` / `published_to` | datetime | Filters `published_at` |
| `source_published_from` / `source_published_to` | datetime | Filters `source_published_at` |
| `limit` | int | Default `50`, max `500` |
| `offset` | int | Default `0` |

**No default freshness window** — omitting every filter returns the full historical Published inventory, not just
recent alerts.

**Ordering:** canonical Published ordering, identical to Admin's `is_published=true` view:
`published_at DESC NULLS LAST, processed_at DESC, id DESC`.

**Response `200 OK`:**

```json
{
  "alerts": [
    {
      "id": 42,
      "title": "FBI warns of rising elder fraud losses...",
      "summary": "The FBI reports a significant increase...",
      "category": "Consumer Scam",
      "risk_level": "high",
      "signal_score": 72,
      "source_name": "FBI Press Releases",
      "source_url": "https://www.fbi.gov/news/...",
      "source_published_at": "2026-04-20T09:00:00Z",
      "published_at": "2026-04-22T14:35:00Z",
      "risk_band": "high",
      "processed_at": "2026-04-22T14:00:00Z"
    }
  ]
}
```

`risk_band` is the Critical/High/Medium badge field. `risk_level` is legacy display-only. All three timestamps
(`published_at`, `source_published_at`, `processed_at`) are present and never aliased to one another (see the
three-timestamp table near the top of this document).

---

### 4.2 Get Published Alert Detail

```
GET /api/v1/subscriber/alerts/{alert_id}
```

Returns `404` if the alert doesn't exist or isn't published.

**Response `200 OK`:**

```json
{
  "id": 42,
  "title": "FBI warns of rising elder fraud losses...",
  "summary": "The FBI reports a significant increase...",
  "category": "Consumer Scam",
  "risk_level": "high",
  "signal_score": 72,
  "source_name": "FBI Press Releases",
  "source_url": "https://www.fbi.gov/news/...",
  "source_published_at": "2026-04-20T09:00:00Z",
  "published_at": "2026-04-22T14:35:00Z",
  "secondary_category": "Wire Fraud",
  "entities": ["FBI", "Western Union", "AARP"],
  "risk_band": "high",
  "risk_explanation": {
    "score": 72,
    "risk_band": "high",
    "risk_level": "high",
    "confidence": "High",
    "factors": {"source_credibility": 5, "financial_impact": 5, "victim_scale": 4, "cross_source": 3, "trend_acceleration": 1},
    "factor_labels": {"source_credibility": "High", "financial_impact": "High", "victim_scale": "Medium", "cross_source": "Medium", "trend_acceleration": "Low"},
    "primary_exposure": ["Elderly consumers"],
    "reason_for_score": ["Reported by a highly credible source.", "Significant estimated financial impact."]
  }
}
```

`entities` is a flat `string[]` (unwrapped from the internal `{"names": [...]}` format). `risk_explanation` contains
**no** internal V1 moderation fields (`publish_decision`, `pending_review_reason`, `publication_state_source`,
`is_excluded`, …) — it's curated for subscriber display. `risk_explanation.risk_band` is the canonical badge value;
`risk_explanation.risk_level` is legacy display only.

**Errors:**
| Code | Reason |
|---|---|
| `404` | Alert not found or not published |

---

### 4.3 Alert Stats

```
GET /api/v1/subscriber/alerts/stats
```

**Response `200 OK`:**

```json
{
  "total_alerts": 142,
  "critical_count": 9,
  "high_count": 23,
  "medium_count": 47,
  "low_count": 63,
  "category_breakdown": [
    {"category": "Investment Fraud", "count": 40},
    {"category": "Cybercrime", "count": 31}
  ]
}
```

The four count buckets are grouped **directly on the stored `risk_band` column** — `critical_count` = `risk_band ==
"critical"`, `high_count` = `"high"`, `medium_count` = `"medium"`, `low_count` = `"below_60"` — exactly the same
column the list filter and Admin API use. **Never recomputed from `signal_score_total`.** Because banding is a
one-time write-time operation, a published row whose `risk_band` is still `null` (pre-normalization legacy data)
falls into none of the four buckets, so their sum can be less than `total_alerts` — that's accurate uncertainty
about un-normalized legacy rows, not a bug.

---

### 4.4 Categories

```
GET /api/v1/subscriber/alerts/categories
```

Always returns all six canonical categories, in canonical order, including any with a count of `0` — safe to build a
stable filter dropdown from. `value` is the exact string to pass to `category` on §4.1.

```json
{
  "categories": [
    {"value": "Investment Fraud", "count": 40},
    {"value": "Cybercrime", "count": 31},
    {"value": "Consumer Scam", "count": 28},
    {"value": "Money Laundering", "count": 19},
    {"value": "Cryptocurrency Fraud", "count": 15},
    {"value": "Other", "count": 9}
  ],
  "total": 142
}
```

---

### 4.5 Top Alerts

```
GET /api/v1/subscriber/alerts/top
```

See §0.2 above for the full contract (7-day `published_at` window, stored-`risk_band`-gated eligibility, no padding,
historical fallback, identical field mapper to §4.1).

---

### 4.6 Search

```
GET /api/v1/subscriber/search/alerts
```

Free-text search across **published** alerts only, backed by `app/api/search.py`. Powered by PostgreSQL `ILIKE` —
no fuzzy/typo/semantic search, no Elasticsearch, no vector DB. Case-insensitive; multi-word `q` is a literal phrase,
not tokenized.

**Query Parameters:**

| Param | Type | Required | Default | Behavior |
|---|---|---|---|---|
| `q` | string | yes | — | Trimmed; empty/whitespace → `422`. |
| `min_score` | int | no | `0` | Normalized 0–100 minimum `signal_score`. Values outside 0–100 are clamped. **There is no `risk_band` filter on search** — `min_score` is the only risk-related knob this endpoint has. |
| `limit` | int | no | `50` | Cap on the top-level `alerts` list, max `100` (clamped above, rejected `422` below 1). |
| `group_limit` | int | no | `20` | Cap on alerts inside each group, max `50` (same clamp/reject rules). |

**Matching:** case-insensitive `ILIKE %q%` on `RawItem.title`, `ProcessedAlert.summary`, `Source.name`, and
`cast(entities_json AS TEXT)` (candidate filter only — `matched_entity` always comes from the parsed entity list,
never raw JSON text).

**Grouping (entity-first, mixed):** alerts whose parsed entities contain `q` produce one `group_type="entity"` group
per distinct matched entity; alerts matching only via title/summary/source collect into a single
`group_type="keyword"` fallback group (never dropped). An alert with multiple matching entities appears in every
relevant entity group, so `sum(groups[*].alertCount)` can exceed `total_alerts` (which counts unique alerts).

**Ranking** (groups and the flat list): `signal_score` DESC, then effective recency DESC
(`source_published_at` ?? `published_at` ?? `processed_at`).

**Response shape** — identical to the retired `GET /api/search/alerts` documented in §0.5 below (same
`SearchResponse` envelope: `query`, `normalized_query`, `total_alerts`, `group_count`, `groups[]`, `alerts[]`); only
the route and its auth changed, not the behavior. Each alert item carries `risk_level` (legacy, display-only,
derived from `signal_score`) — search results do **not** carry `risk_band` at all; there is no `risk_band` field or
filter anywhere in the search response or query parameters. Auth: Supabase JWT + active subscription, same as every
other route in this section.

**Quick Test:**

```bash
curl -G "http://localhost:8000/api/v1/subscriber/search/alerts" \
  --data-urlencode "q=Dimitriy" \
  --data-urlencode "min_score=0" \
  -H "Authorization: Bearer <SUPABASE_JWT>"
```

---

## 5. Events (hidden/internal)

> **Hidden from Swagger** (`include_in_schema=False`). Still fully live and callable, just not shown in the docs UI —
> operational/internal, not something Hasnain should integrate against.
>
> **Note the separate `risk_level`:** this route's `risk_level` query param and response field belong to the
> `Event` model — an entirely different feature from alert `risk_band`/`risk_level` documented in §3/§4 above. Do not
> conflate the two; nothing here contradicts the canonical alert risk_band contract because it isn't the same field.

Events group related alerts about the same fraud incident across multiple sources.

**Auth required:** Internal JWT + `role == "admin"` (`require_admin`) — hardened alongside the rest of the Alert
surface (Pre-Launch Admin Authorization Hardening, 18 August 2026). `EventDetail.linked_alerts` carries the same
internal alert data the Admin Alerts detail route does, so this is the same guard as §3, not the older
any-authenticated-user guard.

### 5.1 List Events

```
GET /api/v1/events
```

**Query Parameters:**
| Param | Type | Description | |-------|------|-------------| | `category` | string | Filter by event category | |
`risk_level` | string | Filter: `low`, `medium`, `high` | | `limit` | int | Default `50`, max `200` | | `offset` | int |
Default `0` |

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
      "signal_score_total": 72,
      "is_published": true,
      "processed_at": "2026-04-22T14:00:00Z"
    }
  ]
}
```

**Errors:**
| Code | Reason | |------|--------| | `404` | Event not found |

---

## 6. Sources (Admin Settings) (hidden/internal)

> **Hidden from Swagger** (`include_in_schema=False`). Still fully live and callable — operational/internal, not
> something Hasnain should integrate against. (The Admin-facing source-health surface Hasnain *should* use is
> documented Swagger-visible: `GET /api/v1/admin/sources/health` and `GET /api/v1/admin/sources/{source_id}/health`
> — not covered in this legacy section, see the live OpenAPI / `README.md` for those.)

Manage the scraping sources.

Auth required: Internal JWT with role == "admin" via require_admin.
These routes are hidden from Swagger but remain mounted for operational use.

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
    "keywords": [
      "fraud",
      "scam",
      "cybercrime"
    ],
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

## 7. Raw Items & Stats (hidden/internal)

> **Hidden from Swagger** (`include_in_schema=False`), including `GET /api/v1/stats` below. Still fully live and
> callable — operational/internal, not something Hasnain should integrate against.

Internal pipeline data — useful for admin debugging.

### 7.1 List Raw Items

```
GET /api/v1/raw-items
```

**Query Parameters:**
| Param | Type | Description | |-------|------|-------------| | `source_id` | int | Filter by source | |`is_duplicate` |
bool | `true` / `false` | | `since` | datetime | ISO 8601 — items fetched after | | `limit` | int | Default `50`, max
`500` | | `offset` | int | Default `0` |

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

Internal Admin JWT required.
The route is hidden from Swagger but remains mounted for operational use. Returns aggregate pipeline statistics.

**Response `200 OK`:**

```json
{
  "total_raw_items": 2847,
  "unique_items": 2103,
  "total_sources": 10,
  "active_sources": 10,
  "items_per_source": [
    {
      "source": "FBI Press Releases",
      "item_count": 312
    },
    {
      "source": "FTC Consumer Alerts",
      "item_count": 287
    }
  ]
}
```

---

## 8. Health Check (hidden/internal)

> **Hidden from Swagger** (`include_in_schema=False`). Still fully live and callable — infra probe, not something
> Hasnain should integrate against. (The Admin-facing operational health surface Hasnain *should* use is
> Swagger-visible: `GET /api/v1/admin/system/health-summary`.)

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

## 9. Legacy HTML Dashboard Routes — Retired

> **Historical implementation, retired by Slice 3B.2P on 6 August 2026.**
> The server-rendered Jinja dashboard and its authentication pages were removed.
> These paths are no longer mounted and return HTTP 404.
>
> HiddenAlerts now uses the React Admin UI with the retained Internal-JWT JSON
> APIs under `/api/v1/*`.

| Method | Historical Path                 | Current Status                                  |
|--------|---------------------------------|-------------------------------------------------|
| `GET`  | `/login`                        | Retired — 404                                   |
| `POST` | `/login`                        | Retired — 404                                   |
| `GET`  | `/logout`                       | Retired — 404                                   |
| `GET`  | `/dashboard`                    | Retired — 404                                   |
| `GET`  | `/dashboard/alerts/{id}`        | Retired — 404                                   |
| `POST` | `/dashboard/alerts/{id}/review` | Retired — use `POST /api/v1/alerts/{id}/review` |
| `GET`  | `/dashboard/events`             | Retired — 404                                   |
| `GET`  | `/dashboard/events/{id}`        | Retired — 404                                   |
| `GET`  | `/dashboard/monitoring`         | Retired — use the Admin Source Health APIs      |

---

## 10. Full Route Inventory & Roles/Access Matrix

Rewritten 18 August 2026 from the live `app.openapi()` output plus `app/main.py`'s router mounts — 55 routes total, 34
documented (Swagger-visible) paths. **Admin and Subscriber use different token systems** — Internal JWT vs. Supabase
JWT — they are not interchangeable, unlike the old admin/subscriber/no-auth matrix below implied.

### Documented (Swagger-visible)

| Endpoint | Auth |
|---|---|
| `GET /api/alerts` | None — public marketing teaser (§0.1) |
| `GET /api/v1/alerts`, `GET /api/v1/alerts/{alert_id}`, `POST /api/v1/alerts/{alert_id}/review` | JWT cookie or Bearer, **`role == "admin"` required** (`require_admin`) — a non-admin authenticated user gets 403, not 401. §3. (The manual processing trigger `POST /api/v1/alerts/process` uses the same guard but is hidden from Swagger — see the Hidden section below.) |
| `GET /api/v1/admin/alerts/categories`, `GET /api/v1/admin/sources/health`, `GET /api/v1/admin/sources/{source_id}/health`, `GET /api/v1/admin/system/health-summary` | Same guard as the row above (`require_admin`) |
| `POST/GET /api/v1/admin/intelligence-briefs`, `GET/PUT /api/v1/admin/intelligence-briefs/{brief_id}`, plus `/archive`, `/feature`, `/unfeature`, `/publish`, `/featured-image` (POST+DELETE) | Same guard as the row above (`require_admin`) — Admin Intelligence Brief CMS, out of scope for this document; see Swagger |
| `GET /api/v1/subscriber/access`, `GET /api/v1/subscriber/me` | Supabase JWT only |
| `GET /api/v1/subscriber/alerts`, `/alerts/categories`, `/alerts/stats`, `/alerts/top`, `/alerts/{alert_id}`, `/search/alerts` | Supabase JWT + active subscription — §4 |
| `GET /api/v1/subscriber/intelligence-briefs`, `/intelligence-briefs/featured`, `/intelligence-briefs/{slug}` | Supabase JWT + active subscription — out of scope for this document; see Swagger |
| `POST /api/v1/auth/login` | None (credentials in body) |
| `POST /api/v1/auth/change-password`, `GET /api/v1/auth/me` | JWT cookie or Bearer |
| `POST /api/v1/billing/checkout`, `/portal`, `GET /api/v1/billing/status`, `POST /api/v1/billing/sync` | Supabase JWT — out of scope for this document; see Swagger |
| `POST /api/v1/stripe/webhook` | Stripe signature verification, not JWT |

### Hidden from Swagger (`include_in_schema=False`) — still live, operational/internal only

Not for frontend integration. Listed for developer awareness, not as things Hasnain should call:

`GET /api/v1/client/alerts`, `GET /api/v1/client/alerts/{alert_id}` (retained transitional API, no known frontend
consumer — do **not** use as the subscriber path; `GET /api/v1/subscriber/alerts` is the real one) ·
`GET /api/v1/events`, `GET /api/v1/events/{event_id}` (§5) · `GET /api/v1/health` (§8) · `GET/PATCH /api/v1/sources`,
`GET /api/v1/sources/{source_id}`, `GET /api/v1/sources/{source_id}/runs`, `POST /api/v1/sources/{source_id}/trigger`
(§6) · `GET /api/v1/raw-items`, `GET /api/v1/raw-items/{item_id}`, `GET /api/v1/stats` (§7) · `POST
/api/v1/alerts/process` (§3.4, manual pipeline trigger, 202).

### Legacy access matrix (kept for the endpoints it still describes correctly)

| Endpoint | `admin` (Internal JWT) | `subscriber` (Supabase JWT) | No Auth |
|---|---|---|---|
| `POST /api/v1/auth/login` | ✅ | ✅ | ✅ |
| `GET /api/v1/auth/me` | ✅ | ✅ | ❌ 401 |
| `POST /api/v1/auth/change-password` | ✅ | ✅ | ❌ 401 |
| `GET /api/alerts` | ✅ | ✅ | ✅ |
| ~~`GET /api/alerts/top`~~ | — | — | *retired, 404* |
| ~~`GET /api/alerts/{id}`~~ | — | — | *retired, 404* |
| ~~`GET /api/alerts/stats`~~ | — | — | *retired, 404* |
| ~~`GET /api/search/alerts`~~ | — | — | *retired, 404* |
| `GET /api/v1/alerts`, `GET /api/v1/alerts/{id}`, `POST /api/v1/alerts/{id}/review` | ✅ role=admin only — a role=subscriber Internal JWT gets 403, not ✅ | ❌ 401 (different token system) | ❌ 401 |
| `GET /api/v1/subscriber/*` (alerts, top, stats, categories, search, me, access) | ❌ 401 (different token system) | ✅ (+ active subscription on content routes) | ❌ 401 |

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
      "loc": [
        "body",
        "new_password"
      ],
      "msg": "String should have at least 8 characters",
      "input": "abc"
    }
  ]
}
```

**Common HTTP status codes:**
| Code | Meaning | |------|---------| | `200` | Success | | `202` | Accepted (background task started) | | `400` | Bad
request (e.g. wrong current password) | | `401` | Unauthenticated — missing or expired token | | `403` | Forbidden —
authenticated but insufficient role | | `404` | Resource not found | | `409` | Conflict (e.g. pipeline already
running) | | `422` | Validation error — check request body/params | | `500` | Internal server error |

---

## 12. Frontend Integration Guide

### Setting Up Auth (Recommended Pattern)

```js
// auth.js — Admin surface (Internal JWT). Subscriber surface uses a separate
// Supabase JWT obtained through Supabase auth, not this endpoint.
const API_BASE = 'http://localhost:8000/api/v1';

export async function login(email, password) {
    const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        credentials: 'include',  // enables cookie
        body: JSON.stringify({email, password}),
    });
    if (!res.ok) throw new Error('Login failed');
    const data = await res.json();
    localStorage.setItem('access_token', data.access_token);
    return data; // { access_token, user: { id, email, role, ... } }
}

export function getAuthHeaders() {
    const token = localStorage.getItem('access_token');
    return token ? {Authorization: `Bearer ${token}`} : {};
}
```

### Admin — Recommended Data Flow

```
1. Login                 → POST /api/v1/auth/login
2. Load review queue     → GET /api/v1/alerts?publish_decision=review&limit=50
3. Load published/critical → GET /api/v1/alerts?is_published=true&risk_band=critical
4. Open alert             → GET /api/v1/alerts/{id}
5. Review alert            → POST /api/v1/alerts/{id}/review
```

There is no server-rendered dashboard, no `/dashboard/*` route, and no source-management flow Hasnain needs to wire
— `GET/PATCH /api/v1/sources*` are hidden/internal (§6).

### Subscriber — Recommended Data Flow

```
1. Authenticate via Supabase, obtain the Supabase JWT
2. Check access         → GET /api/v1/subscriber/access
3. Load feed             → GET /api/v1/subscriber/alerts?limit=20
4. Filter by risk          → GET /api/v1/subscriber/alerts?risk_band=high
5. Open alert              → GET /api/v1/subscriber/alerts/{id}
6. Filter by category      → GET /api/v1/subscriber/alerts?category=Cybercrime
7. Search                  → GET /api/v1/subscriber/search/alerts?q=...
```

`GET /api/v1/client/alerts*` is **not** part of this flow — it's a hidden/internal transitional route with no known
consumer (§4 banner).

### Pagination

```js
// Page 1: offset=0, Page 2: offset=50, Page 3: offset=100
async function loadAlerts(page = 1, limit = 50) {
    const offset = (page - 1) * limit;
    const res = await fetch(
        `/api/v1/subscriber/alerts?limit=${limit}&offset=${offset}`,
        {headers: getAuthHeaders()}
    );
    return res.json();
}
```

### Risk Band Color Mapping (Suggested)

`risk_band` is the field to key badge color off of — not `risk_level`. There is no `risk_level` filter to send on
either the Admin or Subscriber alerts endpoint; this is final, not a transition period.

```js
const RISK_BAND_COLORS = {
    critical: '#991B1B', // dark red
    high: '#DC2626',     // red
    medium: '#D97706',   // amber
    below_60: '#6B7280', // gray — excluded from publication, shown only in Admin review views
};

const RISK_BAND_LABELS = {
    critical: 'Critical',
    high: 'High',
    medium: 'Medium',
    below_60: 'Below 60',
};
```

### Categories Reference

The canonical `category` / `primary_category` values (also servable dynamically from
`GET /api/v1/subscriber/alerts/categories`, §4.4, or `GET /api/v1/admin/alerts/categories`):

- `Investment Fraud`
- `Cybercrime`
- `Consumer Scam`
- `Money Laundering`
- `Cryptocurrency Fraud`
- `Other`

### Copy-Pasteable curl Examples

Replace `<INTERNAL_JWT>` / `<SUPABASE_JWT>` with a real token; these are placeholders, not real credentials.

**Admin — Published Critical alerts:**

```bash
curl "http://localhost:8000/api/v1/alerts?is_published=true&risk_band=critical" \
  -H "Authorization: Bearer <INTERNAL_JWT>"
```

**Admin — Review queue:**

```bash
curl "http://localhost:8000/api/v1/alerts?publish_decision=review" \
  -H "Authorization: Bearer <INTERNAL_JWT>"
```

**Admin — Submit a review action** (approve, with an optional summary edit and legacy display-only
`adjusted_risk_level` — see §3.3 for why this does not drive the Critical/High badge):

```bash
curl -X POST "http://localhost:8000/api/v1/alerts/42/review" \
  -H "Authorization: Bearer <INTERNAL_JWT>" \
  -H "Content-Type: application/json" \
  -d '{
        "review_status": "approved",
        "edited_summary": null,
        "adjusted_risk_level": "high"
      }'
```

**Subscriber — High-risk alerts:**

```bash
curl "http://localhost:8000/api/v1/subscriber/alerts?risk_band=high" \
  -H "Authorization: Bearer <SUPABASE_JWT>"
```

**Subscriber — filtered by source and date range:**

```bash
curl -G "http://localhost:8000/api/v1/subscriber/alerts" \
  --data-urlencode "source=FBI" \
  --data-urlencode "published_from=2026-08-01T00:00:00Z" \
  --data-urlencode "published_to=2026-08-18T00:00:00Z" \
  -H "Authorization: Bearer <SUPABASE_JWT>"
```

**Subscriber — Top Alerts widget:**

```bash
curl "http://localhost:8000/api/v1/subscriber/alerts/top" \
  -H "Authorization: Bearer <SUPABASE_JWT>"
```

---

## Appendix: Key Field Glossary

| Field | Type | Description |
|---|---|---|
| `risk_band` | `string\|null` (`critical`\|`high`\|`medium`\|`below_60`) | **Canonical.** Straight off the stored `processed_alerts.risk_band` column. Never recomputed from score at read time on any endpoint. The only field that should drive badge color, filtering, or eligibility logic. `null` means the row hasn't been normalized yet. |
| `risk_level` | `string\|null` (legacy `low`\|`medium`\|`high`, sometimes `critical` in review payloads) | **Display-only.** Retained on some response models for backward compatibility. Not filterable on the Admin or Subscriber alerts APIs (there is no `risk_level` query param on either), and not authoritative for badges — use `risk_band` instead. On Admin responses it's re-derived from score at read time purely for reviewer display; that has no effect on publication/badge behavior. |
| `signal_score_total` / `signal_score` / `score` | `int` (0–100) | Risk score on a 0–100 scale. Normalized server-side from the 5-factor internal sum (DB column stays 5–25 internally). Use for any UI score display. |
| `relevance_score` | `float` (0.0–1.0) | Legacy ratio derived from the internal sum. Prefer `signal_score_total` (0–100). |
| `published_at` | `datetime\|null` | When **HiddenAlerts itself** published the alert. Canonical Published ordering sorts on this; `published_from`/`published_to` filter it. Never aliased to the other two timestamps below. |
| `source_published_at` | `datetime\|null` | The original source article's own publish date. `source_published_from`/`source_published_to` filter it. Never substituted for `published_at`. |
| `processed_at` | `datetime\|null` | When HiddenAlerts processed/ingested the item. Admin's `start_date`/`end_date` (`since`) filter it — an operational filter, distinct from the two above. |
| `is_relevant` | `bool` | AI determined this alert is actionable |
| `is_published` | `bool` | Admin approved and published to the subscriber feed |
| `publish_decision`, `pending_review_reason`, `is_excluded`, `is_manual_hold`, `published_by_rule`, `publication_state_source` | various | V1 publication-state fields, Admin-only visibility — see §3.1 |
| `primary_category` / `category` | `string` | Main fraud category — one of the six canonical values (§12 Categories Reference) |
| `secondary_category` / `subcategory` | `string\|null` | Secondary category if applicable |
| `entities` | `string[]` | Named entities extracted by AI (subscriber/public view) |
| `entities_json` | `object\|null` | Raw AI entity output `{"names": [...]}` (admin view only) |
| `matched_keywords` | `string[]` | Keywords that triggered this alert |
| `score_source_credibility`, `score_financial_impact`, `score_victim_scale`, `score_cross_source`, `score_trend_acceleration` | `int` (1–5) | Per-factor score breakdown, admin/risk-explanation only |
