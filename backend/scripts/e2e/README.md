# Production E2E harness

Authenticated end-to-end checks for the HiddenAlerts API, built to be pointed at
production during the controlled deployment.

**Read-only by default.** Only `collector_stage.py` can change anything, and only
when eight independent gates are satisfied at once. Everything else issues GETs
plus the two POST logins needed to obtain tokens.

---

## Setup

```bash
cp backend/scripts/e2e/.env.e2e.example /secure/path/e2e.env
chmod 600 /secure/path/e2e.env
$EDITOR /secure/path/e2e.env          # fill in real values
```

Keep the filled-in file **outside the repository**. The harness reads the
environment first, then the file you name with `--env-file`. It never reads the
application's own `.env` or `.env.production`, and refuses if you point it at one.

All commands run from `backend/`:

```bash
cd /opt/hiddenalerts/backend
```

## Environment variables

| Variable | Required | Notes |
|---|---|---|
| `E2E_API_BASE_URL` | yes | HTTPS and on the allowed-host list when targeting production |
| `E2E_TARGET_ENV` | no | `production` (default) enables the strict guards |
| `ADMIN_EMAIL` | yes | aliases: `E2E_ADMIN_EMAIL`, `E2E_ADMIN_USERNAME` |
| `ADMIN_PASSWORD` | yes | alias: `E2E_ADMIN_PASSWORD` |
| `TEST_SUBSCRIBER_EMAIL` | yes | must have an **active** subscription; alias `E2E_SUBSCRIBER_EMAIL` |
| `TEST_SUBSCRIBER_PASSWORD` | yes | alias: `E2E_SUBSCRIBER_PASSWORD` |
| `SUPABASE_PROJECT_URL` | yes | alias: `SUPABASE_URL` |
| `SUPABASE_PUBLISHABLE_KEY` | yes | **publishable/anon key.** A service-role key is detected and refused. Alias: `SUPABASE_ANON_KEY` |
| `TEST_INACTIVE_SUBSCRIBER_EMAIL` / `_PASSWORD` | no | enables the "lapsed subscription → 403" check; skipped when unset |
| `E2E_ALLOWED_HOSTS` | no | comma-separated override of the production allowlist |
| `E2E_REQUEST_TIMEOUT_SECONDS` | no | default 30 |
| `E2E_POLL_INTERVAL_SECONDS` | no | default 5 |
| `E2E_RUN_TIMEOUT_SECONDS` | no | default 900 |
| `E2E_REPORT_DIR` | no | default `<backend>/reports`, resolved from the package location — the same directory whether you run from `backend/` or the repo root |

Missing variables are reported **by name only** — values are never printed.

## Authentication

### Admin — Internal JWT

`POST /api/v1/auth/login` with a **JSON** body `{"email": …, "password": …}`.
Not OAuth2 form data, not `username`. The response carries `access_token`,
`token_type`, `expires_in` and the user object.

A token is accepted **only after it authorizes a real admin request**. HTTP 200
at login proves nothing: a valid non-admin also gets 200, and only fails at the
`require_admin` dependency with 403. The harness distinguishes:

| Outcome | Meaning |
|---|---|
| 401 at login | invalid credentials |
| 200 at login, 403 at verification | valid identity, **not an admin** |
| 401 at verification | token rejected — expired, malformed, wrong secret |
| 404 at verification | endpoint not deployed — **not** an auth failure |

Verification uses `/api/v1/sources` (present in the current release) before
deployment, and `/api/v1/admin/system/health-summary` after (`--post-deploy`).

### Subscriber — Supabase

Password grant: `POST {SUPABASE_PROJECT_URL}/auth/v1/token?grant_type=password`
with the publishable key as the `apikey` header. Verified against
`GET /api/v1/subscriber/alerts`, which requires both a valid Supabase identity
and an active subscription:

| Outcome | Meaning |
|---|---|
| 400/401 at the grant | invalid subscriber credentials |
| 401 at verification | backend rejected the token (issuer/audience/JWKS) |
| **403** `active_subscription_required` | valid identity, **inactive subscription** |
| 200 | active subscriber |

Service-role credentials, admin user creation, magic links and password resets
are never used.

## Token handling

- Tokens exist **only in process memory**. Nothing is written to disk or cached.
- The refresh token from the Supabase grant is deliberately never retained.
- Default output and reports carry a SHA-256 **fingerprint** only — plus kind,
  token type, expiry and the verified endpoint/status. No token substring of any
  length appears anywhere.
- Reports are scrubbed, then the serialized bytes are re-scanned; a report that
  still contains a JWT, database URL, auth header or IP address is **refused**,
  not written.
- The HTTP client keeps **no cookie jar**. The login endpoint sets a session
  cookie and `get_current_user` reads cookies *before* the `Authorization`
  header — a persistent jar would make the "no token → 401" checks pass while
  proving nothing.

## Commands

### Check a token

Each command loads **only the credentials it will send**:

```bash
# Needs the target + ADMIN_EMAIL/ADMIN_PASSWORD. No Supabase values required.
python -m scripts.e2e.auth_tokens --kind admin      --check --env-file /secure/path/e2e.env

# Needs the target + TEST_SUBSCRIBER_* and SUPABASE_*. No admin values required.
python -m scripts.e2e.auth_tokens --kind subscriber --check --env-file /secure/path/e2e.env
```

| Command | Admin credentials | Subscriber credentials |
|---|---|---|
| `auth_tokens --kind admin` | required | not loaded |
| `auth_tokens --kind subscriber` | not loaded | required |
| `production_smoke` | required | required |
| `collector_stage` | required | not loaded |

Production target validation runs in every mode.

`--print-token` exists for local debugging only. It prints a warning, is
**refused against a production target**, and the production runner never needs it.

### Read-only smoke

```bash
# Before deployment — endpoints from the pending release report as skipped
python -m scripts.e2e.production_smoke --env-file /secure/path/e2e.env

# After deployment — those endpoints are REQUIRED; a 404 fails the run
python -m scripts.e2e.production_smoke --env-file /secure/path/e2e.env --post-deploy
```

These endpoints are optional before deployment and **mandatory** with
`--post-deploy`, so a green post-deploy run cannot coexist with a release that
never landed:

```
GET /api/v1/admin/sources/health
GET /api/v1/admin/sources/{id}/health
GET /api/v1/admin/system/health-summary
GET /api/v1/admin/alerts/categories
GET /api/v1/subscriber/alerts/top
GET /api/v1/subscriber/alerts/categories
```

Everything else — the public landing feed, subscriber alerts/stats/search, both
Client routes, and the retained Jinja protection checks — is mandatory in **both**
modes.

**Two endpoints exist in both releases but behave differently**, so presence
alone cannot tell them apart and their *assertions* are mode-gated too:

| Endpoint | Pre-deploy | Post-deploy |
|---|---|---|
| `GET /api/v1/sources/{id}/runs` | legacy counters (`items_fetched`, `items_new`, `items_duplicate`) | split counters required and the identity must balance (migrations 0012/0013) |
| `GET /api/v1/subscriber/alerts/top` | legacy all-time selection: Medium allowed, platform publication date | weekly contract: Critical/High only, `published_at` mirrors `source_published_at` |

Running with `--post-deploy` against the old release will therefore fail on both,
correctly. Run **without** the flag until the release has landed.

Coverage also includes a **category round-trip**: a value returned by the
metadata endpoint is passed straight back as `?category=` to the corresponding
listing, proving the vocabulary the API advertises is one its filters accept. An
empty result is a pass — the check is that the value is accepted and that any
rows returned match it.

### Collector stage

Dry-run is the default and issues **no trigger**:

```bash
python -m scripts.e2e.collector_stage \
  --source-id 1 --expected-source-name "SEC Press Releases" \
  --env-file /secure/path/e2e.env
```

**Source names must be exact.** Matching is a normalized equality test, not a
substring: `"SEC"` will not authorize a run against `"SEC Press Releases"`. Only
surrounding whitespace and letter case are normalized.

Execution needs a **fresh, machine-produced preview report** — generate it
immediately beforehand, because it expires after 15 minutes:

```bash
# 1. Read-only preview for this one source (writes JSON + Markdown)
python -m app.tools.source_recovery_preview \
  --source-id 1 --mode listing \
  --output-json /tmp/preview_sec.json \
  --output-markdown /tmp/preview_sec.md

# 2. Execute, within 15 minutes of that preview
python -m scripts.e2e.collector_stage \
  --source-id 1 \
  --expected-source-name "SEC Press Releases" \
  --max-unseen 10 \
  --max-new-raw-items 10 \
  --preview-report /tmp/preview_sec.json \
  --ai-confirmation AI_PROCESSING_DISABLED_CONFIRMED \
  --execute \
  --confirmation DEPLOYED_SCHEDULER_PAUSED \
  --env-file /secure/path/e2e.env
```

`--preview-unseen` is **display-only for dry runs** and is rejected outright with
`--execute`: a hand-typed volume cannot authorize a trigger, because a typo in it
is invisible whereas a stale or mismatched report is not.

The report is rejected unless it is from `source_recovery_preview`, marked
read-only with an enforced read-only transaction, has unchanged row counts, was
taken at revision `0013`, is under 15 minutes old, has no errors, contains
exactly one record matching both the source id **and** the exact name, has an
accepted status, reports an integer `prospective_unseen` within `--max-unseen`,
and was **not** taken with a configuration overlay.

### AI must be confirmed disabled

A paused collection scheduler is **not** evidence that AI is off: the
`process_new_alerts` job runs on its own 30-minute interval and is gated by
`AI_PROCESSING_ENABLED`, not by whether `collect_all_sources` is registered.

If the API reports `ai_processing_enabled=false`, that settles it. Otherwise you
must check the deployed container yourself and pass the phrase:

```bash
docker exec hiddenalerts_app printenv AI_PROCESSING_ENABLED   # expect: false
  --ai-confirmation AI_PROCESSING_DISABLED_CONFIRMED
```

Execution is refused before the trigger POST if this is unresolved.

It refuses when: `--execute` is absent · the confirmation phrase is wrong · the
target is not a validated production host · `--max-unseen` or
`--max-new-raw-items` is missing · `--preview-report` is missing · the preview is
stale, malformed, from the wrong revision, not read-only, ambiguous, overlaid, or
does not match this source · `scheduler_running` is not `false` · **AI is not
confirmed disabled** · the migration revision is not `0013` · release identity is
unknown · the source id and name disagree · the source is disabled · Source
Health is unavailable.

**One source per invocation.** It never advances to the next; that is a human
decision made after reading the report.

Stages D and E need an extra acknowledgement:

```bash
  --stage D --stage-confirmation FBI_NATIONAL_VOLUME_ACKNOWLEDGED
  --stage E --stage-confirmation FBI_IN_THE_NEWS_LOW_YIELD_ACKNOWLEDGED
```

`--check-409` issues one immediate second trigger to prove claim protection
returns 409. Use it once, on one source.

### Stage plans

Source ids are resolved **by name** at runtime, never hardcoded.

| Stage | Sources | Note |
|---|---|---|
| A | SEC Press Releases, BleepingComputer | smallest real delta first |
| B | FTC RSS Feeds, DOJ Press Releases | validates the configuration changes |
| C | FinCEN, IC3, KrebsOnSecurity, FBI News Blog RSS | zero-backlog validation; expect 0 or few |
| D | FBI National Press Releases | 19-month backlog; extra confirmation |
| E | FBI in the News RSS | large low-yield backlog; extra confirmation |

Every source is triggered on its own invocation, including within a stage.

## Reports

Written to `E2E_REPORT_DIR` (default `backend/reports`, gitignored):

```
production_smoke_<timestamp>.json / .md
collector_stage_<source_id>_<timestamp>.json / .md
```

They contain endpoints, statuses, latencies, assertion results, source ids and
names, counts, health states, RunLog fields, sanitized errors and the release
identifier. They never contain passwords, tokens, refresh tokens, Supabase keys,
authorization headers, cookies, IP addresses, database URLs or environment dumps.

After an executed run the report also records the instance-total deltas —
`raw_items_total`, `processed_alerts_total`, `published_alerts_total`. With AI
confirmed disabled, `raw_items_total` must move by exactly `items_new` and the
other two must not move at all; anything else is a **stop condition** and exits
with code 6.

Collector reports state explicitly that `items_new` counts **RawItems, not
published alerts** — whether any becomes an alert is decided later by AI
processing and the publishing policy, neither of which this harness runs.

## Exit codes

| Code | Meaning |
|---:|---|
| 0 | all assertions passed |
| 1 | an assertion or API call failed |
| 2 | environment or configuration error |
| 3 | authentication failure |
| 4 | a production safety guard refused |
| 5 | a triggered run did not reach a terminal state in time |
| 6 | a stop condition fired |

## Supplying credentials

Adnan supplies credentials by writing them into a file outside the repository and
naming its path — **never by pasting values into chat**. The harness needs only
the path:

```bash
python -m scripts.e2e.production_smoke --env-file /secure/path/e2e.env
```

Claude runs the commands above with that path and reports fingerprints, statuses
and assertion outcomes. No credential value ever appears in a command line, a
log, a report or a message.

## After testing

1. Delete the env file: `shred -u /secure/path/e2e.env`.
2. Clear it from the shell: `unset HISTFILE` beforehand, or `history -c`.
3. **Rotate** the admin password and the test subscriber password.
4. Rotate the Supabase publishable key if it was newly issued for this exercise.
5. Confirm no report contains a fingerprint you would rather not retain —
   fingerprints are one-way, but rotation invalidates them anyway.

Access tokens are short-lived and held only in memory, so nothing survives the
process. Rotation covers the long-lived credentials that produced them.
