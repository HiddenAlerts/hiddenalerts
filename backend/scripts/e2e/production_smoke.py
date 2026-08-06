"""Read-only production smoke runner.

Issues only GET requests, plus the two POST logins needed to obtain tokens. It
has no code path that can mutate anything: there is no trigger call, no publish,
no scheduler control.

Endpoints belonging to the pending release are optional **only** before
deployment: a 404 is reported as *not yet deployed*. With ``--post-deploy`` the
same endpoints are required and a 404 fails the run, so a green post-deploy
result cannot coexist with a release that never landed.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any

import httpx

from scripts.e2e import api_assertions as checks
from scripts.e2e.auth_tokens import (
    ADMIN_VERIFY_PATH,
    ADMIN_VERIFY_PATH_POST_DEPLOY,
    get_admin_access_token,
    get_subscriber_access_token,
)
from scripts.e2e.common import (
    AssertionFailure,
    AuthError,
    ConfigError,
    E2EConfig,
    Exit,
    ResultSet,
    load_config,
    make_client,
    parse_json,
    redact,
    request_with_retry,
    results_markdown,
    timestamp_slug,
    write_reports,
)

HEALTH_PATH = "/api/v1/health"
PUBLIC_ALERTS_PATH = "/api/alerts"
PUBLIC_TOP_PATH = "/api/alerts/top"
ADMIN_SOURCES_PATH = "/api/v1/sources"
ADMIN_SOURCE_HEALTH_PATH = "/api/v1/admin/sources/health"
ADMIN_SYSTEM_SUMMARY_PATH = "/api/v1/admin/system/health-summary"
ADMIN_CATEGORIES_PATH = "/api/v1/admin/alerts/categories"
SUBSCRIBER_ALERTS_PATH = "/api/v1/subscriber/alerts"
SUBSCRIBER_STATS_PATH = "/api/v1/subscriber/alerts/stats"
SUBSCRIBER_SEARCH_PATH = "/api/v1/subscriber/search/alerts"
SUBSCRIBER_TOP_PATH = "/api/v1/subscriber/alerts/top"
SUBSCRIBER_CATEGORIES_PATH = "/api/v1/subscriber/alerts/categories"
CLIENT_ALERTS_PATH = "/api/v1/client/alerts"
#: The second Client route, taken from the route inventory — not invented.
CLIENT_ALERT_DETAIL_PATH = "/api/v1/client/alerts/{alert_id}"
#: Admin listing that accepts an exact `category` filter (app/api/alerts.py).
ADMIN_ALERTS_PATH = "/api/v1/alerts"
SUBSCRIBER_ALERTS_PATH_FILTERED = "/api/v1/subscriber/alerts"
JINJA_DASHBOARD_PATH = "/dashboard"
JINJA_LOGIN_PATH = "/login"

#: Routes Slice 3B.2P removed. Before deployment production still serves them,
#: so their presence is merely recorded; with --post-deploy each must be a 404.
#: GET only — proving the removed POST routes is the route-inventory test's job,
#: not something to demonstrate by sending a write request at production.
REMOVED_JINJA_PATHS = ("/login", "/logout", "/dashboard",
                       "/dashboard/events", "/dashboard/monitoring")
REMOVED_PUBLIC_PATHS = ("/api/alerts/top", "/api/alerts/stats", "/api/search/alerts")

#: A token that is well-formed enough to reach the validator and be rejected.
MALFORMED_TOKEN = "not-a-jwt"


async def _get(
    client: httpx.AsyncClient, path: str, results: ResultSet, name: str, **kwargs: Any
) -> tuple[httpx.Response | None, float]:
    try:
        response, elapsed = await request_with_retry(client, "GET", path, **kwargs)
        return response, elapsed * 1000
    except AssertionFailure as exc:
        results.record(name, False, redact(str(exc)), endpoint=path)
        return None, 0.0


def _record_problems(
    results: ResultSet, name: str, problems: list[str], *, endpoint: str,
    status: int | None = None, latency: float | None = None,
) -> None:
    results.record(
        name, not problems, "; ".join(problems[:6]),
        endpoint=endpoint, status_code=status, latency_ms=latency,
    )


async def _probe_endpoint(
    client: httpx.AsyncClient, path: str, results: ResultSet, name: str,
    *, required: bool, **kwargs: Any,
) -> tuple[Any | None, httpx.Response | None]:
    """GET an endpoint, treating 404 according to whether it is required.

    `required=False` is only appropriate for an endpoint that genuinely ships in
    the pending release: before deployment it is absent, and reporting that as a
    failure would make the pre-deploy run permanently red. Once `--post-deploy`
    is passed, the same endpoint is required and a 404 is a failure — otherwise
    the run could pass while the release had not actually landed.
    """
    response, latency = await _get(client, path, results, name, **kwargs)
    if response is None:
        return None, None
    if response.status_code == 404 and not required:
        results.skip(name, f"{path} is not deployed in the current release")
        return None, response
    if response.status_code != 200:
        detail = (
            f"{path} returned 404 — required in post-deploy mode, so the release "
            f"has not landed"
            if response.status_code == 404
            else f"expected 200, got {response.status_code}"
        )
        results.record(name, False, detail, endpoint=path,
                       status_code=response.status_code, latency_ms=latency)
        return None, response
    return parse_json(response, name), response


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------


async def check_infrastructure(client: httpx.AsyncClient, results: ResultSet) -> None:
    response, latency = await _get(client, HEALTH_PATH, results, "health endpoint responds")
    if response is None:
        return
    results.record(
        "health endpoint responds", response.status_code == 200,
        f"expected 200, got {response.status_code}",
        endpoint=HEALTH_PATH, status_code=response.status_code, latency_ms=latency,
    )
    results.context["health_latency_ms"] = round(latency, 1)
    results.context["api_host"] = str(client.base_url.host)


async def check_public(client: httpx.AsyncClient, results: ResultSet) -> None:
    response, latency = await _get(client, PUBLIC_ALERTS_PATH, results, "public alerts feed")
    if response is None:
        return
    if response.status_code != 200:
        results.record("public alerts feed", False,
                       f"expected 200, got {response.status_code}",
                       endpoint=PUBLIC_ALERTS_PATH, status_code=response.status_code)
        return
    payload = parse_json(response, "public alerts")
    _record_problems(results, "public alerts feed", checks.check_public_alerts(payload),
                     endpoint=PUBLIC_ALERTS_PATH, status=200, latency=latency)

    # The public Top Alerts route was removed in Slice 3B.2P; §removed-surface
    # below asserts it is gone once the release has landed.


async def check_admin(
    client: httpx.AsyncClient, results: ResultSet, admin_header: dict[str, str],
    subscriber_header: dict[str, str], *, post_deploy: bool,
) -> None:
    """Admin surface. `post_deploy` promotes the pending-release endpoints to required."""
    sources, _ = await _probe_endpoint(
        client, ADMIN_SOURCES_PATH, results, "admin sources list",
        required=True, headers=admin_header,
    )
    source_ids: list[int] = []
    if isinstance(sources, list):
        source_ids = [s["id"] for s in sources if isinstance(s, dict) and "id" in s]
        results.context["configured_source_count"] = len(source_ids)
        results.record("admin sources list", True, endpoint=ADMIN_SOURCES_PATH,
                       status_code=200)

    health, _ = await _probe_endpoint(
        client, ADMIN_SOURCE_HEALTH_PATH, results, "source health list",
        required=post_deploy, headers=admin_header,
    )
    if health is not None:
        _record_problems(
            results, "source health list",
            checks.check_source_health_list(health, expected_source_ids=source_ids or None),
            endpoint=ADMIN_SOURCE_HEALTH_PATH, status=200,
        )

    if source_ids:
        first = source_ids[0]
        detail_path = f"/api/v1/admin/sources/{first}/health"
        detail, _ = await _probe_endpoint(
            client, detail_path, results, "source health detail",
            required=post_deploy, headers=admin_header,
        )
        if detail is not None:
            _record_problems(results, "source health detail",
                             checks.check_source_health_detail(detail),
                             endpoint=detail_path, status=200)

        runs_path = f"/api/v1/sources/{first}/runs"
        runs, _ = await _probe_endpoint(
            client, runs_path, results, "source run history",
            required=True, headers=admin_header,
        )
        if isinstance(runs, list) and runs and isinstance(runs[0], dict):
            _record_problems(
                results, "source run history",
                checks.check_run_log_counters(runs[0], require_split=post_deploy),
                endpoint=runs_path, status=200,
            )

    summary, _ = await _probe_endpoint(
        client, ADMIN_SYSTEM_SUMMARY_PATH, results, "system health summary",
        required=post_deploy, headers=admin_header,
    )
    if summary is not None:
        _record_problems(results, "system health summary",
                         checks.check_system_health_summary(summary),
                         endpoint=ADMIN_SYSTEM_SUMMARY_PATH, status=200)
        results.context["scheduler_running"] = summary.get("scheduler_running")

    categories, _ = await _probe_endpoint(
        client, ADMIN_CATEGORIES_PATH, results, "admin categories",
        required=post_deploy, headers=admin_header,
    )
    if categories is not None:
        problems = checks.check_categories(categories, scope="admin")
        missing = checks.missing_zero_count_categories(categories)
        if missing:
            problems.append(f"zero-count categories dropped: {missing}")
        _record_problems(results, "admin categories", problems,
                         endpoint=ADMIN_CATEGORIES_PATH, status=200)
        await _category_round_trip(
            client, results, categories, header=admin_header,
            path=ADMIN_ALERTS_PATH, row_field="primary_category", scope="admin",
        )

    # --- negative assertions -------------------------------------------------
    unauth, _ = await _get(client, ADMIN_SOURCES_PATH, results, "admin without token → 401")
    if unauth is not None:
        results.record("admin without token → 401", unauth.status_code == 401,
                       f"expected 401, got {unauth.status_code}",
                       endpoint=ADMIN_SOURCES_PATH, status_code=unauth.status_code)

    bad, _ = await _get(client, ADMIN_SOURCES_PATH, results, "admin with malformed token → 401",
                        headers={"Authorization": f"Bearer {MALFORMED_TOKEN}"})
    if bad is not None:
        results.record("admin with malformed token → 401", bad.status_code == 401,
                       f"expected 401, got {bad.status_code}",
                       endpoint=ADMIN_SOURCES_PATH, status_code=bad.status_code)

    if subscriber_header:
        cross, _ = await _get(client, ADMIN_SOURCES_PATH, results,
                              "subscriber token on admin API → 401/403",
                              headers=subscriber_header)
        if cross is not None:
            results.record(
                "subscriber token on admin API → 401/403",
                cross.status_code in (401, 403),
                f"expected 401 or 403, got {cross.status_code} — a Supabase token "
                f"must not authorize Internal JWT admin routes",
                endpoint=ADMIN_SOURCES_PATH, status_code=cross.status_code,
            )


async def _category_round_trip(
    client: httpx.AsyncClient, results: ResultSet, categories: Any, *,
    header: dict[str, str], path: str, row_field: str, scope: str,
) -> None:
    """Prove a value from the metadata endpoint is accepted by the real filter.

    Metadata that lists a category the filter rejects is worse than useless — the
    frontend would build a filter chip that returns 422. This takes one canonical
    value straight from the response and passes it back as `?category=`.

    An empty result is a **pass**: the contract is that the value is accepted and
    that whatever comes back matches, not that the category has any alerts.
    """
    entries = categories.get("categories") if isinstance(categories, dict) else None
    if not entries:
        results.skip(f"{scope} category round-trip", "no categories returned")
        return

    # Prefer a category that actually has rows, so the row check has something to
    # verify; fall back to the first canonical value.
    chosen = next((c for c in entries if isinstance(c, dict) and c.get("count")), entries[0])
    value = chosen.get("value")

    name = f"{scope} category round-trip"
    response, latency = await _get(client, path, results, name,
                                   headers=header, params={"category": value})
    if response is None:
        return
    if response.status_code != 200:
        results.record(name, False,
                       f"filter rejected the canonical value {value!r} "
                       f"(HTTP {response.status_code})",
                       endpoint=path, status_code=response.status_code)
        return

    payload = parse_json(response, name)
    rows = payload.get("alerts") if isinstance(payload, dict) else payload
    mismatched = []
    if isinstance(rows, list):
        mismatched = [
            r.get(row_field) for r in rows[:50]
            if isinstance(r, dict) and r.get(row_field) not in (None, value)
        ]
    detail = (
        f"rows returned with a different {row_field}: {mismatched[:3]}"
        if mismatched else f"{value!r} accepted; {len(rows or [])} row(s), all matching"
    )
    results.record(name, not mismatched, detail,
                   endpoint=path, status_code=200, latency_ms=latency)


async def check_subscriber(
    client: httpx.AsyncClient, results: ResultSet, header: dict[str, str],
    *, post_deploy: bool,
) -> None:
    # Alerts, stats and search already exist in the deployed release: required
    # in both modes.
    alerts, _ = await _probe_endpoint(
        client, SUBSCRIBER_ALERTS_PATH, results, "subscriber alerts",
        required=True, headers=header,
    )
    if alerts is not None:
        results.record("subscriber alerts", True, endpoint=SUBSCRIBER_ALERTS_PATH,
                       status_code=200)

    stats, _ = await _probe_endpoint(
        client, SUBSCRIBER_STATS_PATH, results, "subscriber stats",
        required=True, headers=header,
    )
    if isinstance(stats, dict):
        bad = [k for k, v in stats.items()
               if isinstance(v, int) and not isinstance(v, bool) and v < 0]
        _record_problems(results, "subscriber stats",
                         [f"negative counts: {bad}"] if bad else [],
                         endpoint=SUBSCRIBER_STATS_PATH, status=200)

    search, _ = await _probe_endpoint(
        client, SUBSCRIBER_SEARCH_PATH, results, "subscriber search",
        required=True, headers=header, params={"q": "fraud"},
    )
    if search is not None:
        results.record("subscriber search", True, endpoint=SUBSCRIBER_SEARCH_PATH,
                       status_code=200)

    top, _ = await _probe_endpoint(
        client, SUBSCRIBER_TOP_PATH, results, "subscriber top alerts",
        required=post_deploy, headers=header,
    )
    if top is not None:
        # The path exists in both releases; only the semantics differ.
        problems = checks.check_top_alerts(top, weekly_contract=post_deploy)
        count = len(top.get("alerts", []) if isinstance(top, dict) else top)
        results.context["top_alerts_returned"] = count
        _record_problems(results, "subscriber top alerts", problems,
                         endpoint=SUBSCRIBER_TOP_PATH, status=200)
        if count == 0:
            results.record("top alerts empty result accepted", True,
                           "empty is a valid weekly result, not a failure",
                           endpoint=SUBSCRIBER_TOP_PATH, status_code=200)

    categories, _ = await _probe_endpoint(
        client, SUBSCRIBER_CATEGORIES_PATH, results, "subscriber categories",
        required=post_deploy, headers=header,
    )
    if categories is not None:
        problems = checks.check_categories(categories, scope="subscriber")
        missing = checks.missing_zero_count_categories(categories)
        if missing:
            problems.append(f"zero-count categories dropped: {missing}")
        _record_problems(results, "subscriber categories", problems,
                         endpoint=SUBSCRIBER_CATEGORIES_PATH, status=200)
        await _category_round_trip(
            client, results, categories, header=header,
            path=SUBSCRIBER_ALERTS_PATH_FILTERED, row_field="category",
            scope="subscriber",
        )

    unauth, _ = await _get(client, SUBSCRIBER_ALERTS_PATH, results,
                           "subscriber without token → 401")
    if unauth is not None:
        results.record("subscriber without token → 401", unauth.status_code == 401,
                       f"expected 401, got {unauth.status_code}",
                       endpoint=SUBSCRIBER_ALERTS_PATH, status_code=unauth.status_code)


async def check_client_and_legacy(
    client: httpx.AsyncClient, results: ResultSet, admin_header: dict[str, str],
    *, post_deploy: bool,
) -> None:
    """Both Client routes, plus the surface Slice 3B.2P removed."""
    # --- Route 1: /api/v1/client/alerts -------------------------------------
    unauth, _ = await _get(client, CLIENT_ALERTS_PATH, results, "client list without token → 401")
    if unauth is not None:
        results.record("client list without token → 401", unauth.status_code == 401,
                       f"expected 401, got {unauth.status_code}",
                       endpoint=CLIENT_ALERTS_PATH, status_code=unauth.status_code)

    listing, latency = await _get(client, CLIENT_ALERTS_PATH, results,
                                  "client list with admin token → 200", headers=admin_header)
    first_id: int | None = None
    if listing is not None:
        ok = listing.status_code == 200
        results.record(
            "client list with admin token → 200", ok,
            f"expected 200 (require_subscriber_or_admin), got {listing.status_code}",
            endpoint=CLIENT_ALERTS_PATH, status_code=listing.status_code, latency_ms=latency,
        )
        if ok:
            rows = parse_json(listing, "client alerts")
            if isinstance(rows, list) and rows and isinstance(rows[0], dict):
                first_id = rows[0].get("id")
                results.record(
                    "client list schema", "id" in rows[0],
                    f"row keys: {sorted(rows[0])[:6]}",
                    endpoint=CLIENT_ALERTS_PATH, status_code=200,
                )

    # --- Route 2: /api/v1/client/alerts/{alert_id} --------------------------
    if first_id is None:
        results.skip("client detail routes", "no client alert available to address")
    else:
        detail_path = f"/api/v1/client/alerts/{first_id}"
        d_unauth, _ = await _get(client, detail_path, results,
                                 "client detail without token → 401")
        if d_unauth is not None:
            results.record("client detail without token → 401", d_unauth.status_code == 401,
                           f"expected 401, got {d_unauth.status_code}",
                           endpoint=CLIENT_ALERT_DETAIL_PATH,
                           status_code=d_unauth.status_code)

        d_auth, d_latency = await _get(client, detail_path, results,
                                       "client detail with admin token → 200",
                                       headers=admin_header)
        if d_auth is not None:
            ok = d_auth.status_code == 200
            results.record("client detail with admin token → 200", ok,
                           f"expected 200, got {d_auth.status_code}",
                           endpoint=CLIENT_ALERT_DETAIL_PATH,
                           status_code=d_auth.status_code, latency_ms=d_latency)
            if ok:
                body = parse_json(d_auth, "client alert detail")
                results.record("client detail schema", isinstance(body, dict) and "id" in body,
                               f"keys: {sorted(body)[:6] if isinstance(body, dict) else body}",
                               endpoint=CLIENT_ALERT_DETAIL_PATH, status_code=200)

    # --- Removed surface (Slice 3B.2P) --------------------------------------
    await check_removed_surface(client, results, post_deploy=post_deploy)


async def check_removed_surface(
    client: httpx.AsyncClient, results: ResultSet, *, post_deploy: bool
) -> None:
    """The legacy Jinja dashboard and the four unused Public routes.

    Before deployment production still runs the old release, so these paths are
    expected to answer and their presence is only recorded — a pre-deploy run
    must not go red because the removal has not shipped yet. With
    ``--post-deploy`` every one of them must be **404**.
    """
    for path in (*REMOVED_JINJA_PATHS, *REMOVED_PUBLIC_PATHS):
        name = f"removed: {path}"
        response, latency = await _get(client, path, results, name)
        if response is None:
            continue
        if post_deploy:
            results.record(
                name, response.status_code == 404,
                f"expected 404 after cleanup, got {response.status_code}",
                endpoint=path, status_code=response.status_code, latency_ms=latency,
            )
        else:
            results.skip(
                name,
                f"still present in the deployed release (HTTP {response.status_code}) "
                f"— removal ships with this deployment",
            )

    # The Landing feed is the one public route that must survive.
    retained, latency = await _get(client, PUBLIC_ALERTS_PATH, results,
                                   "retained: /api/alerts still 200")
    if retained is not None:
        results.record("retained: /api/alerts still 200", retained.status_code == 200,
                       f"expected 200, got {retained.status_code}",
                       endpoint=PUBLIC_ALERTS_PATH, status_code=retained.status_code,
                       latency_ms=latency)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


async def run_smoke(config: E2EConfig, *, post_deploy: bool) -> ResultSet:
    results = ResultSet("Production read-only smoke")
    results.context.update(config.public_summary())
    results.context["mode"] = "post-deploy" if post_deploy else "pre-deploy"

    client = make_client(config)
    try:
        await check_infrastructure(client, results)
        await check_public(client, results)

        verify_path = ADMIN_VERIFY_PATH_POST_DEPLOY if post_deploy else ADMIN_VERIFY_PATH
        admin_header: dict[str, str] = {}
        subscriber_header: dict[str, str] = {}

        # A transport failure reaching the backend is not an authentication
        # verdict, but it must not abort the run either: record one failed check
        # and carry on with the independent read-only sections.
        try:
            admin = await get_admin_access_token(config, client, verify_path=verify_path)
            admin_header = admin.header
            results.record("admin authentication verified", True,
                           endpoint=admin.verified_endpoint,
                           status_code=admin.verified_status)
            results.context["admin_token"] = admin.safe_summary()
        except (AuthError, AssertionFailure) as exc:
            results.record("admin authentication verified", False, redact(str(exc)))

        try:
            subscriber = await get_subscriber_access_token(config, client)
            subscriber_header = subscriber.header
            results.record("subscriber authentication verified", True,
                           endpoint=subscriber.verified_endpoint,
                           status_code=subscriber.verified_status)
            results.context["subscriber_token"] = subscriber.safe_summary()
        except (AuthError, AssertionFailure) as exc:
            results.record("subscriber authentication verified", False, redact(str(exc)))

        if config.has_inactive_subscriber:
            try:
                inactive = await get_subscriber_access_token(
                    config, client,
                    email=config.inactive_subscriber_email,
                    password=config.inactive_subscriber_password,
                    expect_active=False,
                )
                results.record(
                    "inactive subscription → 403", inactive.verified_status == 403,
                    f"expected 403 active_subscription_required, got "
                    f"{inactive.verified_status}",
                    endpoint=inactive.verified_endpoint,
                    status_code=inactive.verified_status,
                )
            except (AuthError, AssertionFailure) as exc:
                results.record("inactive subscription → 403", False, redact(str(exc)))
        else:
            results.skip("inactive subscription → 403",
                         "TEST_INACTIVE_SUBSCRIBER_* not configured")

        if admin_header:
            await check_admin(client, results, admin_header, subscriber_header,
                              post_deploy=post_deploy)
            await check_client_and_legacy(client, results, admin_header,
                                          post_deploy=post_deploy)
        if subscriber_header:
            await check_subscriber(client, results, subscriber_header,
                                   post_deploy=post_deploy)
    finally:
        await client.aclose()

    return results


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.e2e.production_smoke",
        description="Read-only production smoke test. Issues GETs and two logins only.",
    )
    parser.add_argument("--env-file", help="path to an env file outside the repository")
    parser.add_argument("--post-deploy", action="store_true",
                        help="assert endpoints from the pending release are present")
    parser.add_argument("--no-report", action="store_true", help="skip writing reports")
    return parser


async def _main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        config = load_config(args.env_file)
    except ConfigError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return int(Exit.CONFIG_ERROR)

    print(f"Read-only smoke against {config.api_base_url} ({config.target_env})\n")
    results = await run_smoke(config, post_deploy=args.post_deploy)

    print(
        f"\n{results.passed_count} passed · {len(results.failed)} failed "
        f"· {results.skipped_count} skipped"
    )

    if not args.no_report:
        stem = f"production_smoke_{timestamp_slug()}"
        try:
            json_path, md_path = write_reports(
                results.summary(),
                results_markdown(results, heading="Production read-only smoke"),
                report_dir=config.report_dir, stem=stem,
            )
            print(f"reports: {json_path}  {md_path}")
        except AssertionFailure as exc:
            print(f"report not written: {exc}", file=sys.stderr)
            return int(Exit.ASSERTION_FAILED)

    auth_failed = any(
        "authentication verified" in r.name and not r.passed for r in results.results
    )
    if auth_failed:
        return int(Exit.AUTH_FAILED)
    return int(results.exit_code())


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_main(argv))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
