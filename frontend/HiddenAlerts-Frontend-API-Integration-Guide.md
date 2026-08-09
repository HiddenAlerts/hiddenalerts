# Guide for Collectors Health Monitoring APIs, Alert Categories and Top Alerts APIs Fixes

Only endpoints introduced or changed in the collector-health / backend-cleanup phase (deployed 2026-08-08).

---

## Setup

Base URL:

```
NEXT_PUBLIC_API_BASE_URL = https://api.hiddenalerts.com/api
```

Frontend-relative paths stay as they are today:

- `/alerts` for the public feed
- `/v1/subscriber/...` for authenticated subscriber requests
- `/v1/admin/...` for authenticated admin requests

### Auth

| Scope      | Header                                          | Notes                                                                                      |
|------------|-------------------------------------------------|--------------------------------------------------------------------------------------------|
| Public     | none                                            | `/alerts` only                                                                             |
| Subscriber | `Authorization: Bearer <supabase access token>` | also requires an active subscription; returns 403 `active_subscription_required` otherwise |
| Admin      | `Authorization: Bearer <internal JWT>`          | from `POST /v1/auth/login`                                                                 |

---

## New endpoints

### Alert categories

```
GET /v1/subscriber/alerts/categories      subscriber
GET /v1/admin/alerts/categories           admin
```

These endpoints return a Canonical category list with counts. Both return same shape; the subscriber version counts
published alerts only, admin version counts all processed alerts. All six categories are always returned, so a filter
dropdown built from this will not reorder between requests.

```json
{
  "categories": [
    {
      "value": "Investment Fraud",
      "label": "Investment Fraud",
      "count": 34
    },
    {
      "value": "Cybercrime",
      "label": "Cybercrime",
      "count": 21
    }
  ],
  "total": 6
}
```

`value` is the exact string to pass to the `category` filter on `GET /v1/subscriber/alerts`.

**Frontend action:** Category dropdowns are currently hard-coded; switching them to this endpoint removes the risk of
drift when the taxonomy changes. Not required for any existing page to work.

### Source Health (Admin and Probably a new Section on Admin Dashboard, please further discuss with Ken)

```
GET /v1/admin/sources/health               admin
GET /v1/admin/sources/{source_id}/health   admin
GET /v1/admin/system/health-summary        admin
```

Read-only observability for the collectors: per-source state and a system rollup. Nothing here triggers a collection or
changes configuration.

Per-source items carry `state` (`healthy` / `warning` / `error` / `disabled`),
`reason_code`, `last_run_at`, `last_run_status`, `last_success_at`, `consecutive_failed_runs`,
`items_new_24h/7d/30d`, `items_skipped_invalid_24h`, `items_skipped_external_24h/7d` and
`last_error_message`.

System summary:

```json
{
  "sources_total": 10,
  "by_state": {
    "healthy": 9,
    "warning": 1,
    "error": 0,
    "disabled": 0
  },
  "sources_needing_attention": [
    {
      "source_id": 6,
      "name": "FBI News Blog RSS",
      "state": "warning",
      "reason_code": "no_upstream_content"
    }
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

Worth knowing when you build the UI: `items_skipped_external` is deliberately separate from `items_skipped_invalid`.

**Frontend action:** Admin monitoring screen, again please discuss with Ken how he wants to display this.

I would recommend structuring it in three visual layers:

```
┌──────────────────────────────────────────────────────────────────────┐
│ Source Health                                                        │
│ Last refreshed: 09 Aug 2026, 01:15                                   │
│                                                                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐                 │
│  │ 10       │ │ 9        │ │ 1        │ │ 0        │                 │
│  │ Sources  │ │ Healthy  │ │ Warning  │ │ Error    │                 │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘                 │
│                                                                      │
│  System Status:  ● Operational                                       │
├──────────────────────────────────────────────────────────────────────┤
│ Source                 Status     Last Run       New   Issue         │
│                                                                      │
│ SEC                    ● Healthy   12 min ago      0    —            │
│ FTC                    ● Healthy   12 min ago      1    —            │
│ DOJ                    ● Healthy   11 min ago      0    —            │
│ FBI National           ● Healthy   10 min ago      0    —            │
│ FBI in the News        ● Healthy   10 min ago      0    —            │
│ FBI News Blog          ● Warning   10 min ago      0    No content   │
│ FinCEN                 ● Healthy    9 min ago      0    —            │
│ IC3                    ● Healthy    9 min ago      0    —            │
│ Krebs                  ● Healthy    8 min ago      0    —            │
│ BleepingComputer       ● Healthy    8 min ago      1    —            │
│                                                                      │
│                                            [View source details →]   │
└──────────────────────────────────────────────────────────────────────┘
```

#### 1. Top: System Health Summary

Use:

```
GET /v1/admin/system/health-summary
```

I would show four compact cards:

Total Sources | Healthy | Warning | Error

For example:

10 Sources 9 Healthy 1 Warning 0 Errors

Then underneath:

- System Operational

or, depending on the response:

- Attention Required
- Degraded

I would avoid a large chart here. For only ~10 sources, numbers and statuses are more useful than a pie chart.

If the API exposes scheduler/system information, we can also show a small secondary line:

```
Collection Scheduler: Running
Latest collection cycle: 18 minutes ago
```

#### 2. Main Section: Source Health Table

Use

```
GET /v1/admin/sources/health
```

I would recommend columns approximately like:

| Source        | Health  | Last Collection | New Items | Status / Issue      | Action |
|---------------|---------|----------------:|----------:|---------------------|--------|
| SEC           | Healthy |      12 min ago |         0 | —                   | View   |
| FTC           | Healthy |      12 min ago |         1 | —                   | View   |
| FBI National  | Healthy |      10 min ago |         0 | —                   | View   |
| FBI News Blog | Warning |      10 min ago |         0 | No upstream content | View   |
| DOJ           | Healthy |      11 min ago |         0 | —                   | View   |

Health should use simple badges:

- Healthy
- Warning
- Error
- Disabled

#### 3. Source Detail Drawer / Modal

When the Admin clicks a source row:

```
GET /v1/admin/sources/{source_id}/health
```

Rather than navigating to a completely different page, I would open a right-side drawer or modal.

Something like:

```
┌──────────────────────────────────────────────┐
│ FBI National                         [ × ]   │
│ ● Healthy                                    │
│                                              │
│ Collection                                   │
│ Last run             09 Aug, 00:52 UTC       │
│ Last successful run  09 Aug, 00:52 UTC       │
│ Source status         Active                 │
│                                              │
│ Latest Run                                   │
│ Status               Success                 │
│ Items fetched         300                    │
│ New items             0                      │
│ Duplicates            236                    │
│ External skipped      64                     │
│ Invalid skipped       0                      │
│                                              │
│ Health                                       │
│ Reason               —                       │
│                                              │
│ Activity — last 24h                          │
│ New articles          2                      │
│ Invalid items         0                      │
│ External destinations 128                    │
│                                              │
│ Last error            None                   │
└──────────────────────────────────────────────┘
```

This is where fields become useful. such as:

- latest run;
- latest run status;
- items_new;
- duplicate counts;
- items_skipped_invalid;
- items_skipped_external;
- reason code;
- active/disabled state;

The main table should stay simple. Technical telemetry belongs in the detail view.

#### Mapping the three APIs to the UI

```
/v1/admin/system/health-summary
             │
             └─────► Summary cards
                     System status
                     Healthy / Warning / Error counts


/v1/admin/sources/health
             │
             └─────► Source Health table
                     All sources
                     Health
                     Last run
                     activity
                     issue/reason


/v1/admin/sources/{source_id}/health
             │
             └─────► Source details drawer
                     Detailed latest-run telemetry
                     skip counts
                     reason/status
                     recent activity

```

---

## Changed endpoints

### `GET /v1/subscriber/alerts/top` — Top Alerts This Week

Primary rule (unchanged): published Critical/High alerts whose HiddenAlerts `published_at` falls in the rolling last 7
days, ordered Critical first, then score descending, then `published_at` descending. Maximum 3. Historical bulk
publications are excluded.

**New:** when the primary rule returns *zero* alerts, the widget falls back to the latest qualifying Critical/High
alerts regardless of age, ordered by `published_at` descending, and says so. One or two current alerts are returned
as-is — the list is never padded with older material.

Two response fields were added. Both are additive with non-fallback defaults, so ignoring them keeps today's behavior.

Normal:

```json
{
  "alerts": [
    /* ... */
  ],
  "is_fallback": false,
  "message": null
}
```

Fallback:

```json
{
  "alerts": [
    /* ... */
  ],
  "is_fallback": true,
  "message": "No new Critical or High alerts have been published during the past seven days. The latest published intelligence is shown below."
}
```

Items are the standard subscriber alert shape and now include `risk_band` (`critical` / `high` / `medium` / `below_60`)
alongside the legacy `risk_level`.

`risk_band` is the canonical severity field. Legacy `risk_level` uses older thresholds and can disagree — alert 1312 is
`risk_band: "critical"` with `risk_level: "high"` and a score of 80. Read `risk_band`; `risk_level` stays for
compatibility.

**Frontend action:**

- render alerts as you do now;
- use `risk_band` for the severity badge;
- when `is_fallback` is `true`, show `message` above the list; otherwise show no notice.

### `GET /alerts` — public Landing Page teaser

This is now a marketing teaser, not public intelligence feed. At most **3** of the most recently published Critical/High
alerts, with only these fields:

```json
{
  "alerts": [
    {
      "title": "Cryptocurrency and AI Scams Bilk Americans of Billions",
      "risk_band": "critical",
      "category": "Investment Fraud",
      "published_at": "2026-08-08T11:33:20Z",
      "summary": "The FBI's 2025 Internet Crime Report reveals that cyber-enabled crimes defrauded Americans…"
    }
  ]
}
```

`summary` is a preview of the stored summary — at most 2 sentences and 320 characters including the trailing `…`, which
appears only when text was actually cut.

`published_at` is the HiddenAlerts publication date, per Ken's confirmation. It is also the sort key, so the card date
and the ordering always agree.

Removed from previous payload: `id`, `signal_score`, `risk_level`, `source_name`, `source_url`, `source_published_at`,
and every detail field.

`limit` parameter is still accepted but can only lower the count — a request for 100 returns at most 3.

**Frontend action:**

- remove the score badge (`signal_score` is gone);
- use `risk_band` for the classification — `resolveAlertRiskBand` already prefers it;
- `source_published_at ?? published_at` still resolves correctly, so the card date needs no change;
- `summary` is now available if you want it on the card;
- the list key is already `` `${alert.title}-${i}` `` and does not need `id`.

### `PUT /v1/admin/intelligence-briefs/{id}` — Key Signals now persist

Not a new endpoint. Previously an edit that changed `key_signals` returned 200 and echoed the previously stored value
back, so the change looked saved but was not. Fixed.

The request field is unchanged — `key_signals` as a JSON array of strings:

```json
{
  "key_signals": [
    "Signal one",
    "Signal two",
    "Signal three"
  ]
}
```

**Frontend action:**. Keep sending `key_signals` exactly as you do now. Worth re-testing an edit to confirm it sticks.

### Intelligence Brief publish workflow

```
PUT    /v1/admin/intelligence-briefs/{id}                  content
POST   /v1/admin/intelligence-briefs/{id}/featured-image   multipart, field name: file
DELETE /v1/admin/intelligence-briefs/{id}/featured-image   remove
POST   /v1/admin/intelligence-briefs/{id}/publish          lifecycle, no body
```

Order matters:

1. save content (`PUT`);
2. upload the image if one was selected (`POST .../featured-image`);
3. publish only after both have returned successfully.

`publish` takes no request body and changes only `status`, `published_at` and `updated_by_user_id`. It does not carry
content and cannot upload a locally selected image — if the upload step was skipped or failed, publishing will not pick
the file up later.

This is worth guarding in UI: thumbnail chosen in editor is local browser state until `POST /featured-image` succeeds.
The save mutation already surfaces `imageWarning` when that call fails; making that failure blocking (or at least
prominent) before publish is enabled would prevent a brief going live without its image.

---

## Retired routes

Removed earlier in this phase; all return 404. Please ensure that your frontend not using any of these.

```
GET /api/alerts/top          →  GET /v1/subscriber/alerts/top
GET /api/alerts/stats        →  GET /v1/subscriber/alerts/stats
GET /api/alerts/{id}         →  GET /v1/subscriber/alerts/{id}
GET /api/search/alerts       →  GET /v1/subscriber/search/alerts
```

Server-rendered admin surface (`/login`, `/logout`, `/dashboard`, `/dashboard/events`, `/dashboard/monitoring`) was
removed with its templates and static assets. `/uploads` is unaffected and still serves brief images.
