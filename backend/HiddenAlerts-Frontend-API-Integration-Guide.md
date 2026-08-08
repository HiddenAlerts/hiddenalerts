# HiddenAlerts — Frontend API Integration Guide

Covers only the endpoints introduced or changed in the collector-health / backend-cleanup
phase (branch `dev-collector-health-backend-cleanup`, deployed 2026-08-08). Everything not
listed here is unchanged.

Generated against the live OpenAPI contract; every field below exists in the deployed
schemas.

---

## Setup

Base URL is unchanged:

```
NEXT_PUBLIC_API_BASE_URL = https://api.hiddenalerts.com/api
```

Frontend-relative paths stay as they are today — `/alerts` for the public feed,
`/v1/subscriber/...` and `/v1/admin/...` for the rest.

### Auth

| Scope | Header | Notes |
|---|---|---|
| Public | none | `/alerts` only |
| Subscriber | `Authorization: Bearer <supabase access token>` | also requires an active subscription; returns 403 `active_subscription_required` otherwise |
| Admin | `Authorization: Bearer <internal JWT>` | from `POST /v1/auth/login` |

Note: the OpenAPI document does not currently declare `securitySchemes` — auth is enforced
by route dependencies, so Swagger UI will not show padlocks or an "Authorize" button. The
behaviour is correct; only the spec annotation is missing. Send the headers as above.

---

## New endpoints

### Alert categories

```
GET /v1/subscriber/alerts/categories      subscriber
GET /v1/admin/alerts/categories           admin
```

Canonical category list with counts. Both return the same shape; the subscriber version
counts published alerts only, the admin version counts all processed alerts. All six
categories are always returned, including zero-count ones, in a stable order — so a filter
dropdown built from this will not reorder between requests.

```json
{
  "categories": [
    { "value": "Investment Fraud", "label": "Investment Fraud", "count": 34 },
    { "value": "Cybercrime", "label": "Cybercrime", "count": 21 }
  ],
  "total": 6
}
```

`value` is the exact string to pass to the `category` filter on `GET /v1/subscriber/alerts`.

**Frontend action:** optional. Category dropdowns are currently hard-coded; switching them
to this endpoint removes the risk of drift when the taxonomy changes. Not required for any
existing page to work.

### Source Health

```
GET /v1/admin/sources/health               admin
GET /v1/admin/sources/{source_id}/health   admin
GET /v1/admin/system/health-summary        admin
```

Read-only observability for the collectors: per-source state and a system rollup. Nothing
here triggers a collection or changes configuration.

Per-source items carry `state` (`healthy` / `warning` / `error` / `disabled`),
`reason_code`, `last_run_at`, `last_run_status`, `last_success_at`, `consecutive_failed_runs`,
`items_new_24h/7d/30d`, `items_skipped_invalid_24h`, `items_skipped_external_24h/7d` and
`last_error_message`.

The system summary:

```json
{
  "sources_total": 10,
  "by_state": { "healthy": 9, "warning": 1, "error": 0, "disabled": 0 },
  "sources_needing_attention": [
    { "source_id": 6, "name": "FBI News Blog RSS", "state": "warning", "reason_code": "no_upstream_content" }
  ],
  "scheduler_running": true,
  "scheduler_interval_hours": 6.0,
  "last_collection_cycle_at": "2026-08-08T18:48:07Z",
  "items_new_24h": 1,
  "raw_items_total": 1358,
  "processed_alerts_total": 1358,
  "published_alerts_total": 144,
  "alembic_revision": "0013"
}
```

Worth knowing when you build the UI: `items_skipped_external` is deliberately separate from
`items_skipped_invalid`. External skips are a policy outcome (an FBI feed item pointing at
justice.gov is excluded on purpose), not a failure, so a busy FBI source reads as "running
fine, mostly not ours" rather than broken.

**Frontend action:** none required for existing pages. These exist for a future Admin
monitoring screen, which does not exist yet.

---

## Changed endpoints

### `GET /v1/subscriber/alerts/top` — Top Alerts This Week

Primary rule (unchanged): published Critical/High alerts whose HiddenAlerts `published_at`
falls in the rolling last 7 days, ordered Critical first, then score descending, then
`published_at` descending. Maximum 3. Historical bulk publications are excluded.

**New:** when the primary rule returns *zero* alerts, the widget falls back to the latest
qualifying Critical/High alerts regardless of age, ordered by `published_at` descending, and
says so. One or two current alerts are returned as-is — the list is never padded with older
material.

Two response fields were added. Both are additive with non-fallback defaults, so ignoring
them keeps today's behaviour.

Normal:

```json
{ "alerts": [ /* ... */ ], "is_fallback": false, "message": null }
```

Fallback:

```json
{
  "alerts": [ /* ... */ ],
  "is_fallback": true,
  "message": "No new Critical or High alerts have been published during the past seven days. The latest published intelligence is shown below."
}
```

Items are the standard subscriber alert shape and now include `risk_band`
(`critical` / `high` / `medium` / `below_60`) alongside the legacy `risk_level`.

`risk_band` is the canonical severity field. The legacy `risk_level` uses older thresholds
and can disagree — alert 1312 is `risk_band: "critical"` with `risk_level: "high"` and a
score of 80. Read `risk_band`; `risk_level` stays for compatibility.

**Frontend action:**
- render alerts as you do now;
- use `risk_band` for the severity badge;
- when `is_fallback` is `true`, show `message` above the list; otherwise show no notice.

### `GET /alerts` — public Landing Page teaser

This is now a marketing teaser, not a public intelligence feed. At most **3** of the most
recently published Critical/High alerts, with only these fields:

```json
{
  "alerts": [
    {
      "title": "Cryptocurrency and AI Scams Bilk Americans of Billions",
      "risk_band": "critical",
      "category": "Investment Fraud",
      "published_at": "2026-08-08T11:33:20Z",
      "summary": "The FBI's 2025 Internet Crime Report reveals that cyber-enabled crimes defrauded Americans of nearly $21 billion. Investment fraud was the primary driver…"
    }
  ]
}
```

`summary` is a preview of the stored summary — at most 2 sentences and 320 characters
including the trailing `…`, which appears only when text was actually cut.

`published_at` is the HiddenAlerts publication date, per Ken's confirmation. It is also the
sort key, so the card date and the ordering always agree.

Removed from the previous payload: `id`, `signal_score`, `risk_level`, `source_name`,
`source_url`, `source_published_at`, and every detail field. The `limit` parameter is still
accepted but can only lower the count — a request for 100 returns at most 3.

**Frontend action:**
- remove the score badge (`signal_score` is gone);
- use `risk_band` for the classification — `resolveAlertRiskBand` already prefers it;
- `source_published_at ?? published_at` still resolves correctly, so the card date needs no
  change;
- `summary` is now available if you want it on the card;
- the list key is already `` `${alert.title}-${i}` `` and does not need `id`.

### `PUT /v1/admin/intelligence-briefs/{id}` — Key Signals now persist

Not a new endpoint. Previously an edit that changed `key_signals` returned 200 and echoed
the previously stored value back, so the change looked saved but was not. Fixed.

The request field is unchanged — `key_signals` as a JSON array of strings:

```json
{ "key_signals": ["Signal one", "Signal two", "Signal three"] }
```

**Frontend action:** none. Keep sending `key_signals` exactly as you do now. Worth
re-testing an edit to confirm it sticks.

### Intelligence Brief publish workflow

```
PUT    /v1/admin/intelligence-briefs/{id}                  content
POST   /v1/admin/intelligence-briefs/{id}/featured-image   multipart, field name: file
DELETE /v1/admin/intelligence-briefs/{id}/featured-image   remove
POST   /v1/admin/intelligence-briefs/{id}/publish          lifecycle, no body
```

The order matters:

1. save content (`PUT`);
2. upload the image if one was selected (`POST .../featured-image`);
3. publish only after both have returned successfully.

`publish` takes no request body and changes only `status`, `published_at` and
`updated_by_user_id`. It does not carry content and cannot upload a locally selected image —
if the upload step was skipped or failed, publishing will not pick the file up later.

This is worth guarding in the UI: a thumbnail chosen in the editor is local browser state
until `POST .../featured-image` succeeds. The save mutation already surfaces
`imageWarning` when that call fails; making that failure blocking (or at least prominent)
before publish is enabled would prevent a brief going live without its image.

---

## Retired routes

Removed earlier in this phase; all return 404. The frontend audit found no remaining
consumer for any of them.

```
GET /api/alerts/top          →  GET /v1/subscriber/alerts/top
GET /api/alerts/stats        →  GET /v1/subscriber/alerts/stats
GET /api/alerts/{id}         →  GET /v1/subscriber/alerts/{id}
GET /api/search/alerts       →  GET /v1/subscriber/search/alerts
```

The server-rendered admin surface (`/login`, `/logout`, `/dashboard`, `/dashboard/events`,
`/dashboard/monitoring`) was removed with its templates and static assets. `/uploads` is
unaffected and still serves brief images.

---

## Checklist

- [ ] Dashboard Top Alerts reads `is_fallback` and displays `message` when true
- [ ] Dashboard severity badge reads `risk_band`
- [ ] Landing Page removes the score badge (`signal_score` no longer returned)
- [ ] Landing Page renders `summary`
- [ ] Landing Page tolerates the reduced teaser payload (no `id`, `source_url`, `source_name`)
- [ ] Brief editor: confirm a `key_signals` edit persists after the fix
- [ ] Brief publish is blocked (or clearly warned) until content save and image upload succeed
- [ ] Optional: category dropdowns switch from hard-coded values to the category APIs
- [ ] Future: Admin Source Health screen uses the three health endpoints

Items already verified as needing no change: the landing card date (`source_published_at ??
published_at` still resolves), the landing list key, and the `key_signals` request format.
