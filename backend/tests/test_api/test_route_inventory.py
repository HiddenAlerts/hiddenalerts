"""Route inventory, interface-area guards and the Slice 3B.2P contract proof.

Every route belongs to exactly one interface area, and each area has its own
authentication model:

``admin_api``      administrative surface (Internal JWT)
``subscriber_api`` paid-content surface (Supabase token + active subscription)
``client_api``     retained transitional internal surface (Internal JWT)
``public_api``     the unauthenticated Landing feed, ``GET /api/alerts``
``billing``        checkout / status / portal / sync, plus the Stripe webhook
``infrastructure`` uptime and documentation endpoints

**Cleanup state.** Slice 3B.2P removed the legacy Jinja dashboard and the four
unused Public compatibility routes: 12 OpenAPI paths, 13 operations. There is no
``legacy_jinja`` area any more, and the public surface is a single route.

``REMOVED_PATHS`` / ``REMOVED_OPERATIONS`` are **regression guards, not
interface classifications** — they describe forbidden legacy surface. The branch
that still recognises ``/login`` and ``/dashboard`` exists purely so accidental
reintroduction fails loudly; it does not mean those routes are supported.

The contract proof diffs the live OpenAPI against a **tracked** fixture,
``tests/fixtures/api_surface_before_cleanup_20260806.json``. It deliberately does
not read ``reports/``: that directory is gitignored, so a clean checkout would
make the proof skip — passing the build while proving nothing. A missing or
malformed fixture is a failure, never a skip.

These tests assert **route registration and authentication**, which are facts
about the code. They say nothing about whether an interface is *operationally
used* — that is a product fact, recorded in the audit reports.
"""
import ast
import json
import inspect
import pathlib
import textwrap

import pytest
from fastapi.routing import APIRoute
from starlette.routing import Mount

from app.main import app

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]


def _mounted_routes() -> dict[tuple[str, str], APIRoute]:
    """Every (method, full path) the app actually serves.

    FastAPI 0.139 nests included routers behind ``_IncludedRouter``, so
    ``app.routes`` alone shows only six top-level entries — the real paths have
    to be resolved through each router's include context.
    """
    found: dict[tuple[str, str], APIRoute] = {}

    def walk(router, prefix=""):
        for route in getattr(router, "routes", []) or []:
            if type(route).__name__ == "_IncludedRouter":
                ctx = getattr(route, "include_context", None)
                inner = getattr(route, "original_router", None)
                if inner is not None:
                    walk(inner, prefix + (getattr(ctx, "prefix", "") or ""))
                continue
            path = prefix + (getattr(route, "path", "") or "")
            for method in (getattr(route, "methods", None) or set()) - {"HEAD", "OPTIONS"}:
                found[(method, path)] = route

    walk(app.router)
    return found


ROUTES = _mounted_routes()

#: FastAPI's own documentation routes. They are part of ``ROUTES`` (the
#: ``infrastructure`` area below classifies them) but were never in the OpenAPI
#: document, so the baseline diffs must exclude them to compare like with like.
DOC_ROUTE_PATHS = frozenset({"/docs", "/docs/oauth2-redirect", "/openapi.json", "/redoc"})

API_ROUTES = {
    (method, path) for method, path in ROUTES if path not in DOC_ROUTE_PATHS
}
PATHS = {path for _, path in ROUTES}


def _auth_deps(method: str, path: str) -> set[str]:
    route = ROUTES[(method, path)]
    return {
        d.call.__name__
        for d in route.dependant.dependencies
        if getattr(d, "call", None)
    }


# ===========================================================================
# Inventory resolution
# ===========================================================================


def test_inventory_resolves_nested_router_prefixes():
    """A naive walk of app.routes finds six entries; the real count is far higher."""
    assert len(app.routes) < 30, "top-level routes are the mount points only"
    assert len(ROUTES) > 50, f"resolved only {len(ROUTES)} routes"

    # Every OpenAPI path must be reachable through the resolved inventory.
    assert set(app.openapi()["paths"]) <= PATHS


def test_inventory_covers_each_audited_area():
    for path in (
        "/api/alerts",
        "/api/v1/subscriber/alerts", "/api/v1/subscriber/alerts/top",
        "/api/v1/admin/sources/health", "/api/v1/sources/{source_id}/runs",
        "/api/v1/client/alerts", "/api/v1/health",
    ):
        assert path in PATHS, path


# ===========================================================================
# Confirmed client journeys — must remain registered
# ===========================================================================


def test_landing_page_alerts_route_remains():
    """`GET /api/alerts` — 202 requests in the retained window, Ken-confirmed."""
    assert ("GET", "/api/alerts") in ROUTES
    assert _auth_deps("GET", "/api/alerts") == {"get_db"}, "stays public"


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/v1/subscriber/alerts"),
    ("GET", "/api/v1/subscriber/alerts/{alert_id}"),
    ("GET", "/api/v1/subscriber/alerts/stats"),
    ("GET", "/api/v1/subscriber/search/alerts"),
])
def test_alerts_page_routes_remain_subscription_protected(method, path):
    """The Alerts Page migrated to the subscriber API; all four carry traffic."""
    assert (method, path) in ROUTES
    assert "require_active_subscription" in _auth_deps(method, path)


def test_subscriber_top_alerts_remains_and_is_protected():
    assert ("GET", "/api/v1/subscriber/alerts/top") in ROUTES
    assert "require_active_subscription" in _auth_deps("GET", "/api/v1/subscriber/alerts/top")
    route = ROUTES[("GET", "/api/v1/subscriber/alerts/top")]
    # The widget has its own wrapper so it can report whether the historical
    # fallback engaged; the paginated feed keeps its exact shape. The item schema
    # still extends the public one, so no previously promised field was lost.
    assert route.response_model.__name__ == "SubscriberTopAlertsResponse"
    from app.schemas.alert import (
        PublicAlertRead,
        SubscriberAlertRead,
        SubscriberAlertsResponse,
        SubscriberTopAlertsResponse,
    )

    assert issubclass(SubscriberAlertRead, PublicAlertRead)
    assert set(PublicAlertRead.model_fields) <= set(SubscriberAlertRead.model_fields)
    assert set(SubscriberTopAlertsResponse.model_fields) == {
        "alerts", "is_fallback", "message",
    }
    assert set(SubscriberAlertsResponse.model_fields) == {"alerts"}


@pytest.mark.parametrize("path", [
    "/api/v1/admin/sources/health",
    "/api/v1/admin/sources/{source_id}/health",
    "/api/v1/admin/system/health-summary",
])
def test_source_health_routes_remain_admin_only(path):
    assert ("GET", path) in ROUTES
    assert "require_admin" in _auth_deps("GET", path)


def test_uptime_health_endpoint_remains_public():
    assert ("GET", "/api/v1/health") in ROUTES
    assert "require_admin" not in _auth_deps("GET", "/api/v1/health")


# ===========================================================================
# Retained legacy — insufficient evidence to remove
# ===========================================================================


# ===========================================================================
# Shared helpers required by retained routes
# ===========================================================================


def test_shared_public_mappers_remain_operational():
    """Subscriber routes depend on these; they cannot be removed with a route."""
    from app.api import public_alerts, search, subscriber

    assert callable(public_alerts._to_public_read)
    assert callable(public_alerts._to_public_detail)
    assert callable(public_alerts.to_subscriber_alert_read)
    assert callable(search.search_alerts_impl)

    # Each is genuinely reached from a subscriber handler. Top Alerts uses the
    # same shared list-item mapper as the paginated feed — no second, subtly
    # different mapper exists (see app/api/public_alerts.py::to_subscriber_alert_read).
    assert "to_subscriber_alert_read" in inspect.getsource(subscriber.subscriber_top_alerts)
    assert "_to_public_detail" in inspect.getsource(subscriber.subscriber_alert_detail)
    assert "search_alerts_impl" in inspect.getsource(subscriber.subscriber_search_alerts)


# ===========================================================================
# Removed in this slice
# ===========================================================================


def test_dead_risk_level_helper_is_gone():
    from app.api import public_alerts

    assert not hasattr(public_alerts, "_title_case_level")


def test_admin_alerts_list_no_longer_documents_risk_level_as_a_filter():
    """risk_band is the sole canonical V1 filter on both Admin and Subscriber
    now — risk_level was removed as a competing Admin list parameter (its
    score-range filtering helper, `_score_filter_for_risk_level`, is gone
    along with it), so it must not appear in the live OpenAPI parameter list
    for GET /api/v1/alerts."""
    from app.api import alerts as alerts_module
    from app.main import app

    assert not hasattr(alerts_module, "_score_filter_for_risk_level")

    spec = app.openapi()
    params = spec["paths"]["/api/v1/alerts"]["get"]["parameters"]
    names = {p["name"] for p in params}
    assert "risk_level" not in names
    assert "risk_band" in names


def test_subscriber_alerts_documents_risk_band_not_risk_level():
    from app.main import app

    spec = app.openapi()
    params = spec["paths"]["/api/v1/subscriber/alerts"]["get"]["parameters"]
    names = {p["name"] for p in params}
    assert "risk_level" not in names
    assert "risk_band" in names


def test_no_new_public_route_was_introduced():
    """Every unauthenticated route is one the audit already knew about."""
    guarded = {
        "require_admin", "require_active_subscription", "get_current_user",
        "get_current_active_user", "get_current_subscriber",
        "require_subscriber_or_admin",
    }
    public = {
        path for (method, path), route in ROUTES.items()
        if method == "GET" and path.startswith("/api")
        and isinstance(route, APIRoute)
        and not (guarded & {
            d.call.__name__ for d in route.dependant.dependencies
            if getattr(d, "call", None)
        })
    }
    # After Slice 3B.2P the only unauthenticated content route is the Landing
    # feed; the Stripe webhook is signature-verified rather than dependency-guarded.
    assert public == {"/api/alerts", "/api/v1/health"}


# ===========================================================================
# Interface-area authentication boundaries
# ===========================================================================
#
# Each area's guard is asserted by its *actual* dependency name, not by the
# product-level label. Where the two differ the report records both.

#: product "Admin API (internal JWT)" → require_admin → get_current_active_user
ADMIN_GUARD = "require_admin"
#: product "Subscriber API (Supabase + active subscription)"
SUBSCRIBER_GUARDS = {"require_active_subscription", "get_current_subscriber"}
#: product "Client API (internal JWT)" → require_subscriber_or_admin
CLIENT_GUARD = "require_subscriber_or_admin"


def _api_routes():
    return {
        (method, path): route
        for (method, path), route in ROUTES.items()
        if isinstance(route, APIRoute)
    }


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/v1/sources"),
    ("GET", "/api/v1/sources/{source_id}"),
    ("PATCH", "/api/v1/sources/{source_id}"),
    ("GET", "/api/v1/sources/{source_id}/runs"),
    ("POST", "/api/v1/sources/{source_id}/trigger"),
    ("GET", "/api/v1/raw-items"),
    ("GET", "/api/v1/stats"),
    ("GET", "/api/v1/admin/alerts/categories"),
    ("GET", "/api/v1/admin/intelligence-briefs"),
])
def test_admin_api_routes_keep_the_admin_guard(method, path):
    """Target administrative surface — retained, never a cleanup candidate."""
    assert (method, path) in ROUTES
    assert ADMIN_GUARD in _auth_deps(method, path)


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/v1/subscriber/alerts"),
    ("GET", "/api/v1/subscriber/alerts/top"),
    ("GET", "/api/v1/subscriber/alerts/stats"),
    ("GET", "/api/v1/subscriber/alerts/{alert_id}"),
    ("GET", "/api/v1/subscriber/search/alerts"),
    ("GET", "/api/v1/subscriber/intelligence-briefs"),
])
def test_subscriber_api_routes_require_an_active_subscription(method, path):
    assert (method, path) in ROUTES
    assert "require_active_subscription" in _auth_deps(method, path)


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/v1/subscriber/me"),
    ("GET", "/api/v1/subscriber/access"),
])
def test_subscriber_identity_routes_need_a_token_but_not_a_subscription(method, path):
    """Deliberate: a signed-in user without a subscription can still be told so."""
    deps = _auth_deps(method, path)
    assert SUBSCRIBER_GUARDS & deps
    assert "require_active_subscription" not in deps


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/v1/client/alerts"),
    ("GET", "/api/v1/client/alerts/{alert_id}"),
])
def test_client_api_routes_keep_their_internal_guard(method, path):
    """A distinct transitional area — not Public, not Subscriber."""
    assert (method, path) in ROUTES
    assert CLIENT_GUARD in _auth_deps(method, path)
    # Never reachable anonymously, and never behind the Supabase model.
    assert not (SUBSCRIBER_GUARDS & _auth_deps(method, path))


def test_client_and_public_areas_do_not_overlap():
    client = {p for (_, p) in ROUTES if p.startswith("/api/v1/client")}
    public = {
        p for (m, p), route in _api_routes().items()
        if m == "GET" and p.startswith("/api")
        and not {
            d.call.__name__ for d in route.dependant.dependencies
            if getattr(d, "call", None)
        } & ({ADMIN_GUARD, CLIENT_GUARD} | SUBSCRIBER_GUARDS
             | {"get_current_user", "get_current_active_user"})
    }
    assert client and public
    assert client & public == set(), "client routes must never be unauthenticated"


def test_no_protected_content_is_served_by_a_public_route():
    """Subscriber-only areas must not appear under an unauthenticated path."""
    for (method, path), route in _api_routes().items():
        deps = {
            d.call.__name__ for d in route.dependant.dependencies
            if getattr(d, "call", None)
        }
        if "subscriber" in path or "client" in path or "admin" in path:
            assert deps - {"get_db"}, f"{method} {path} has no auth dependency"


def test_interface_areas_partition_every_api_route():
    """Each API route belongs to exactly one area — no route is unclassified."""
    def area(path: str, deps: set[str]) -> str:
        if path.startswith(("/dashboard", "/login", "/logout")):
            return "legacy_jinja"
        if path in ("/api/v1/health", "/docs", "/redoc", "/openapi.json"):
            return "infrastructure"
        if path.startswith("/api/v1/client"):
            return "client_api"
        if path.startswith("/api/v1/subscriber"):
            return "subscriber_api"
        if ADMIN_GUARD in deps or path.startswith("/api/v1/admin"):
            return "admin_api"
        if deps <= {"get_db"}:
            return "public_api"
        return "admin_api"  # remaining internal-JWT routes

    counts: dict[str, int] = {}
    for (method, path), route in ROUTES.items():
        deps = (
            {d.call.__name__ for d in route.dependant.dependencies
             if getattr(d, "call", None)}
            if isinstance(route, APIRoute) else set()
        )
        counts[area(path, deps)] = counts.get(area(path, deps), 0) + 1

    # Every area is represented, and nothing fell outside the taxonomy.
    assert set(counts) <= {
        "admin_api", "subscriber_api", "client_api",
        "public_api", "infrastructure",
    }
    for expected in ("admin_api", "subscriber_api",
                     "client_api", "public_api", "infrastructure"):
        assert counts.get(expected, 0) > 0, f"no routes classified as {expected}"
    assert sum(counts.values()) == len(ROUTES)


# ===========================================================================
# Slice 3B.2P contract proof
#
# The cleanup removed 13 operations across 12 OpenAPI paths. These tests pin
# that exact diff against the before-cleanup baseline so a future change cannot
# quietly drop a retained route, and so the removal cannot silently grow.
# ===========================================================================

#: 8 Jinja paths + 4 public paths = 12 removed OpenAPI paths.
REMOVED_JINJA_PATHS = frozenset({
    "/login", "/logout", "/dashboard",
    "/dashboard/alerts/{alert_id}", "/dashboard/alerts/{alert_id}/review",
    "/dashboard/events", "/dashboard/events/{event_id}", "/dashboard/monitoring",
})
REMOVED_PUBLIC_PATHS = frozenset({
    "/api/alerts/top", "/api/alerts/stats", "/api/alerts/{alert_id}",
    "/api/search/alerts",
})
REMOVED_PATHS = REMOVED_JINJA_PATHS | REMOVED_PUBLIC_PATHS

#: Slice 3B.2AJ — operational and currently unconsumed paths hidden from Swagger
#: with ``include_in_schema=False`` so /docs is the supported integration
#: reference. **Hidden is not removed**: every one of these still resolves, still
#: enforces its existing authentication, and is asserted present in ``ROUTES`` by
#: the interface-area tests above. 13 paths / 14 operations
#: (``/sources/{source_id}`` carries both GET and PATCH).
HIDDEN_FROM_SCHEMA_PATHS = frozenset({
    "/api/v1/health",
    "/api/v1/raw-items",
    "/api/v1/raw-items/{item_id}",
    "/api/v1/stats",
    "/api/v1/sources",
    "/api/v1/sources/{source_id}",
    "/api/v1/sources/{source_id}/runs",
    "/api/v1/sources/{source_id}/trigger",
    "/api/v1/alerts/process",
    "/api/v1/events",
    "/api/v1/events/{event_id}",
    "/api/v1/client/alerts",
    "/api/v1/client/alerts/{alert_id}",
})

#: 13 operations — /login previously served both GET and POST.
REMOVED_OPERATIONS = frozenset({
    ("GET", "/login"), ("POST", "/login"), ("GET", "/logout"),
    ("GET", "/dashboard"), ("GET", "/dashboard/alerts/{alert_id}"),
    ("POST", "/dashboard/alerts/{alert_id}/review"),
    ("GET", "/dashboard/events"), ("GET", "/dashboard/events/{event_id}"),
    ("GET", "/dashboard/monitoring"),
    ("GET", "/api/alerts/top"), ("GET", "/api/alerts/stats"),
    ("GET", "/api/alerts/{alert_id}"), ("GET", "/api/search/alerts"),
})

#: The backend package root, whether the tree is checked out at
#: /opt/hiddenalerts/backend or mounted elsewhere in a test container.
BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[2]

#: The pre-cleanup surface, **tracked in git** beside these tests.
#:
#: It deliberately does not live in ``reports/``: that directory is gitignored,
#: so a clean checkout has none of it and the contract proof would silently skip
#: — proving nothing exactly when it matters most. The fixture is sanitized to
#: path names and HTTP methods only.
BASELINE_FIXTURE = (
    BACKEND_ROOT / "tests/fixtures/api_surface_before_cleanup_20260806.json"
)


def _baseline():
    """Load the tracked pre-cleanup surface.

    Absence or malformed content is a **failure**, never a skip: the fixture is
    committed, so if it cannot be read something is genuinely wrong.
    """
    if not BASELINE_FIXTURE.exists():
        raise AssertionError(
            f"tracked contract fixture is missing: {BASELINE_FIXTURE}. "
            f"It is committed to git and must never be optional."
        )
    try:
        data = json.loads(BASELINE_FIXTURE.read_text())
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"contract fixture {BASELINE_FIXTURE} is not valid JSON: {exc}"
        ) from None

    for key in ("openapi_path_count", "openapi_operation_count", "paths"):
        if key not in data:
            raise AssertionError(f"contract fixture is missing {key!r}")
    if not isinstance(data["paths"], dict) or not data["paths"]:
        raise AssertionError("contract fixture has no usable 'paths' mapping")
    return data


def test_removed_path_and_operation_counts_are_exactly_twelve_and_thirteen():
    """12 paths, 13 operations — the counts differ because /login had two methods."""
    assert len(REMOVED_PATHS) == 12
    assert len(REMOVED_OPERATIONS) == 13
    assert len(REMOVED_JINJA_PATHS) == 8
    assert {p for _, p in REMOVED_OPERATIONS} == REMOVED_PATHS


@pytest.mark.parametrize("path", sorted(REMOVED_PATHS))
def test_removed_paths_are_no_longer_mounted(path):
    assert path not in PATHS, f"{path} should have been removed by Slice 3B.2P"


@pytest.mark.parametrize("method,path", sorted(REMOVED_OPERATIONS))
def test_removed_operations_are_no_longer_mounted(method, path):
    assert (method, path) not in ROUTES


def test_service_diff_against_baseline_is_exactly_the_approved_removal():
    """Nothing beyond the approved 12 paths may leave the service, and nothing
    may appear.

    Diffed against the **mounted route inventory**, not OpenAPI. Slice 3B.2AJ
    hid 13 operational/unconsumed paths from Swagger with
    ``include_in_schema=False``; they still serve traffic, so measuring removal
    by the OpenAPI document would now report them as deleted when they are not.
    Registration is the fact this guard was written to protect.
    """
    baseline = _baseline()
    before = set(baseline["paths"])                  # path -> [METHOD, ...]
    after = {path for _, path in API_ROUTES}

    assert before - after == set(REMOVED_PATHS), (
        "unexpected path removal: "
        f"{sorted((before - after) - REMOVED_PATHS)}"
    )
    assert after - before == set(), f"unexpected new paths: {sorted(after - before)}"
    assert baseline["openapi_path_count"] == 59
    assert len(after) == 47


def test_openapi_hides_exactly_the_approved_internal_paths():
    """The Swagger surface is the mounted surface minus the 3B.2AJ hidden set."""
    mounted = {path for _, path in API_ROUTES}
    documented = set(app.openapi()["paths"])

    assert documented <= mounted, (
        f"OpenAPI documents unmounted paths: {sorted(documented - mounted)}"
    )
    assert mounted - documented == set(HIDDEN_FROM_SCHEMA_PATHS), (
        "hidden-path set drifted: "
        f"unexpectedly hidden {sorted((mounted - documented) - HIDDEN_FROM_SCHEMA_PATHS)}, "
        f"unexpectedly visible {sorted(HIDDEN_FROM_SCHEMA_PATHS - (mounted - documented))}"
    )
    assert len(documented) == 34


def test_retained_paths_keep_every_method_they_had():
    """No retained path may lose or gain an HTTP method.

    Measured against mounted routes for the same reason as the test above:
    hiding a route from Swagger must not read as losing a method.
    """
    baseline = _baseline()
    before_ops = {
        (method.upper(), path)
        for path, methods in baseline["paths"].items()
        for method in methods
    }
    after_ops = set(API_ROUTES)
    assert len(before_ops) == 64 and len(after_ops) == 51
    for method, path in before_ops:
        if path in REMOVED_PATHS:
            continue
        assert (method, path) in after_ops, f"retained {method} {path} disappeared"
    assert after_ops - before_ops == set()


def test_static_mount_removed_and_uploads_mount_retained():
    """The Brief media mount must survive the dashboard-asset cleanup."""
    mounts = {r.path for r in app.routes if isinstance(r, Mount)}
    assert "/static" not in mounts, "/static should have been removed with the Jinja CSS"
    assert "/uploads" in mounts, "/uploads serves live Intelligence Brief images"


def test_frontend_confirmed_routes_all_survive():
    """Every endpoint Hasnain confirmed, plus the three the audit discovered."""
    required = [
        ("GET", "/api/alerts"),
        ("GET", "/api/v1/subscriber/me"), ("GET", "/api/v1/subscriber/access"),
        ("GET", "/api/v1/subscriber/alerts"),
        ("GET", "/api/v1/subscriber/alerts/{alert_id}"),
        ("GET", "/api/v1/subscriber/alerts/top"),
        ("GET", "/api/v1/subscriber/alerts/stats"),
        ("GET", "/api/v1/subscriber/search/alerts"),
        ("GET", "/api/v1/subscriber/intelligence-briefs"),
        ("GET", "/api/v1/subscriber/intelligence-briefs/featured"),
        ("GET", "/api/v1/subscriber/intelligence-briefs/{slug}"),
        ("POST", "/api/v1/billing/checkout"), ("GET", "/api/v1/billing/status"),
        ("POST", "/api/v1/billing/portal"), ("POST", "/api/v1/billing/sync"),
        ("POST", "/api/v1/auth/login"), ("GET", "/api/v1/auth/me"),
        ("POST", "/api/v1/auth/change-password"),
        ("GET", "/api/v1/alerts"), ("GET", "/api/v1/alerts/{alert_id}"),
        ("POST", "/api/v1/alerts/{alert_id}/review"),
        ("GET", "/api/v1/admin/intelligence-briefs"),
        ("POST", "/api/v1/admin/intelligence-briefs"),
        ("GET", "/api/v1/admin/intelligence-briefs/{brief_id}"),
        ("PUT", "/api/v1/admin/intelligence-briefs/{brief_id}"),
        ("POST", "/api/v1/admin/intelligence-briefs/{brief_id}/publish"),
        ("POST", "/api/v1/admin/intelligence-briefs/{brief_id}/archive"),
        ("POST", "/api/v1/admin/intelligence-briefs/{brief_id}/feature"),
        ("POST", "/api/v1/admin/intelligence-briefs/{brief_id}/unfeature"),
        ("POST", "/api/v1/admin/intelligence-briefs/{brief_id}/featured-image"),
        ("DELETE", "/api/v1/admin/intelligence-briefs/{brief_id}/featured-image"),
    ]
    missing = [f"{m} {p}" for m, p in required if (m, p) not in ROUTES]
    assert not missing, f"frontend-confirmed routes lost: {missing}"


def test_intentional_new_apis_and_client_apis_survive():
    """Unconsumed does not mean unused — these are deliberate deliverables."""
    required = [
        ("GET", "/api/v1/subscriber/alerts/categories"),
        ("GET", "/api/v1/admin/alerts/categories"),
        ("GET", "/api/v1/admin/sources/health"),
        ("GET", "/api/v1/admin/sources/{source_id}/health"),
        ("GET", "/api/v1/admin/system/health-summary"),
        ("GET", "/api/v1/sources"), ("GET", "/api/v1/sources/{source_id}"),
        ("PATCH", "/api/v1/sources/{source_id}"),
        ("GET", "/api/v1/sources/{source_id}/runs"),
        ("POST", "/api/v1/sources/{source_id}/trigger"),
        ("GET", "/api/v1/raw-items"), ("GET", "/api/v1/stats"),
        # Client APIs are retained transitional — explicitly not in this cleanup.
        ("GET", "/api/v1/client/alerts"),
        ("GET", "/api/v1/client/alerts/{alert_id}"),
    ]
    missing = [f"{m} {p}" for m, p in required if (m, p) not in ROUTES]
    assert not missing, f"intentionally retained routes lost: {missing}"


# ===========================================================================
# Intelligence Brief media survives the dashboard-asset cleanup (Slice 3B.2P §17)
# ===========================================================================


def test_uploads_mount_configuration_is_unchanged():
    """`/uploads` keeps its path and its configured directory."""
    from app.config import settings

    uploads = [
        r for r in app.routes if isinstance(r, Mount) and r.path == "/uploads"
    ]
    assert len(uploads) == 1, "the Brief media mount must remain, exactly once"
    assert uploads[0].name == "uploads"
    assert str(uploads[0].app.directory).endswith(settings.upload_dir.rstrip("/"))


def test_brief_image_urls_stay_under_the_uploads_prefix():
    """Generated featured-image URLs are unaffected by deleting app/static."""
    from app.services import intelligence_brief_images as images

    assert images._URL_PREFIX == "/uploads"
    assert str(images._IMAGE_SUBDIR) == "intelligence-briefs"


def test_app_static_directory_is_gone_and_uploads_directory_is_not():
    """The Jinja asset tree was deleted; the media directory was not."""
    assert not (BACKEND_ROOT / "app/static").exists()
    assert not (BACKEND_ROOT / "app/templates").exists()
    # /uploads is created at startup, so the mount is what matters here.
    assert "/uploads" in {r.path for r in app.routes if isinstance(r, Mount)}


def test_contract_fixture_is_tracked_and_independent_of_reports():
    """The proof must hold in a clean checkout, where reports/ does not exist.

    `reports/` is gitignored. A contract test that reads from there skips on a
    fresh clone and in CI — silently passing the build while proving nothing.
    """
    assert BASELINE_FIXTURE.exists(), "the fixture must be committed, not generated"
    assert "reports" not in BASELINE_FIXTURE.parts
    assert BASELINE_FIXTURE.parent.name == "fixtures"

    # Inspect the loader's own AST — a substring scan would match this test's
    # assertions and the loader's docstring rather than real behaviour.
    loader_tree = ast.parse(textwrap.dedent(inspect.getsource(_baseline)))

    called = {
        node.func.attr
        for node in ast.walk(loader_tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "skip" not in called, (
        "a missing or malformed fixture must fail, never skip"
    )

    literals = {
        node.value
        for node in ast.walk(loader_tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert not any("reports" in s for s in literals if "gitignored" not in s), (
        "the contract loader must not read the gitignored reports directory"
    )

    names = {node.id for node in ast.walk(loader_tree) if isinstance(node, ast.Name)}
    assert "BASELINE_FIXTURE" in names


def test_contract_fixture_holds_only_sanitized_surface_data():
    """Path names and methods only — no environment, servers or credentials."""
    raw = BASELINE_FIXTURE.read_text()
    lowered = raw.lower()
    for forbidden in ("http://", "https://", "servers", "secret", "token",
                      "generated_at", "database_url"):
        assert forbidden not in lowered, f"fixture leaks {forbidden!r}"

    data = json.loads(raw)
    assert set(data["paths"]) and all(
        isinstance(methods, list) and all(isinstance(m, str) for m in methods)
        for methods in data["paths"].values()
    )
    # The only 'password' occurrence is the change-password *route path*.
    assert [p for p in data["paths"] if "password" in p] == [
        "/api/v1/auth/change-password"
    ]


def test_contract_fixture_counts_are_self_consistent():
    data = _baseline()
    assert data["openapi_path_count"] == len(data["paths"]) == 59
    assert data["openapi_operation_count"] == sum(
        len(m) for m in data["paths"].values()
    ) == 64
    # And the removal manifest is a strict subset of what existed before.
    assert set(REMOVED_PATHS) <= set(data["paths"])


def test_missing_or_malformed_fixture_fails_rather_than_skips(tmp_path, monkeypatch):
    """A broken fixture must stop the build, not quietly disappear from it."""
    import tests.test_api.test_route_inventory as module

    monkeypatch.setattr(module, "BASELINE_FIXTURE", tmp_path / "absent.json")
    with pytest.raises(AssertionError, match="missing"):
        module._baseline()

    broken = tmp_path / "broken.json"
    broken.write_text("{not json")
    monkeypatch.setattr(module, "BASELINE_FIXTURE", broken)
    with pytest.raises(AssertionError, match="not valid JSON"):
        module._baseline()

    incomplete = tmp_path / "incomplete.json"
    incomplete.write_text(json.dumps({"paths": {}}))
    monkeypatch.setattr(module, "BASELINE_FIXTURE", incomplete)
    with pytest.raises(AssertionError, match="missing 'openapi_path_count'"):
        module._baseline()
