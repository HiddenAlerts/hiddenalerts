"""Route inventory and interface-area guards (Slice 3B.2K).

Every route belongs to exactly one interface area, and each area has its own
authentication model and migration state:

``legacy_jinja``   inactive, intentionally retained until the Admin UI covers
                   the remaining monitoring and source-management actions
``admin_api``      target administrative surface (internal JWT)
``subscriber_api`` active paid-content surface (Supabase token + subscription)
``client_api``     transitional internal surface (internal JWT)
``public_api``     transitional unauthenticated surface
``infrastructure`` uptime and documentation endpoints

These tests assert **route registration and authentication**, which are facts
about the code. They deliberately say nothing about whether an interface is
*operationally used* — that is a product fact, recorded in
``reports/legacy_route_cleanup_slice3b2k_20260802.md``. A Jinja route being
registered is not evidence that anyone uses it.

Nothing is asserted absent unless it was actually removed.
"""
import ast
import inspect
import pathlib

import pytest
from fastapi.routing import APIRoute

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
    assert len(ROUTES) > 60, f"resolved only {len(ROUTES)} routes"

    # Every OpenAPI path must be reachable through the resolved inventory.
    assert set(app.openapi()["paths"]) <= PATHS


def test_inventory_covers_each_audited_area():
    for path in (
        "/api/alerts", "/api/alerts/top", "/api/search/alerts",
        "/api/v1/subscriber/alerts", "/api/v1/subscriber/alerts/top",
        "/api/v1/admin/sources/health", "/api/v1/sources/{source_id}/runs",
        "/dashboard/monitoring", "/api/v1/health",
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
    assert route.response_model.__name__ == "PublicAlertsResponse"


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


@pytest.mark.parametrize("path", [
    "/api/alerts/top",
    "/api/alerts/stats",
    "/api/alerts/{alert_id}",
    "/api/search/alerts",
])
def test_documented_public_routes_are_retained(path):
    """Zero traffic in 14 days is not proof for a *documented public* contract.

    Retention (19 Jul – 2 Aug) is shorter than the 30 days the removal gate
    prefers, and these paths ship in the tracked API contract with public curl
    examples. Retained pending Ken/Hasnain confirmation — see the slice report.
    """
    assert ("GET", path) in ROUTES, f"{path} must not be removed on current evidence"


@pytest.mark.parametrize("path", [
    "/dashboard", "/dashboard/monitoring", "/dashboard/events",
    "/dashboard/alerts/{alert_id}", "/login", "/logout",
])
def test_legacy_jinja_routes_remain_registered_during_migration(path):
    """Registered, not endorsed.

    The owner has confirmed the Jinja interface is **no longer operationally
    used**. It stays mounted only until the Admin UI covers the remaining
    monitoring and source-management actions; this asserts it has not been
    removed prematurely, and says nothing about usage.
    """
    assert any(m for (m, p) in ROUTES if p == path), path


def test_every_legacy_jinja_capability_has_an_api_replacement():
    """Backend parity is complete — the outstanding gap is Admin UI screens."""
    replacements = {
        ("GET", "/dashboard"): ("GET", "/api/v1/alerts"),
        ("GET", "/dashboard/alerts/{alert_id}"): ("GET", "/api/v1/alerts/{alert_id}"),
        ("POST", "/dashboard/alerts/{alert_id}/review"):
            ("POST", "/api/v1/alerts/{alert_id}/review"),
        ("GET", "/dashboard/events"): ("GET", "/api/v1/events"),
        ("GET", "/dashboard/events/{event_id}"): ("GET", "/api/v1/events/{event_id}"),
        ("GET", "/dashboard/monitoring"): ("GET", "/api/v1/admin/sources/health"),
        ("POST", "/login"): ("POST", "/api/v1/auth/login"),
    }
    for legacy, replacement in replacements.items():
        assert legacy in ROUTES, f"legacy route vanished: {legacy}"
        assert replacement in ROUTES, f"no API replacement for {legacy}"


def test_every_jinja_template_is_still_referenced():
    """No orphaned templates — removal of any page would leave one behind."""
    import re

    templates = pathlib.Path("app/templates")
    on_disk = {str(p.relative_to(templates)) for p in templates.rglob("*.html")}

    referenced: set[str] = set()
    for path in list(pathlib.Path("app").rglob("*.py")) + list(templates.rglob("*.html")):
        referenced |= set(re.findall(r'["\']([\w/]+\.html)["\']', path.read_text(errors="ignore")))

    assert on_disk - referenced == set(), "orphaned template(s)"


# ===========================================================================
# Shared helpers required by retained routes
# ===========================================================================


def test_shared_public_mappers_remain_operational():
    """Subscriber routes depend on these; they cannot be removed with a route."""
    from app.api import public_alerts, search, subscriber

    assert callable(public_alerts._to_public_read)
    assert callable(public_alerts._to_public_detail)
    assert callable(search.search_alerts_impl)

    # Each is genuinely reached from a subscriber handler.
    assert "_to_public_read" in inspect.getsource(subscriber._to_top_alert_read)
    assert "_to_public_detail" in inspect.getsource(subscriber.subscriber_alert_detail)
    assert "search_alerts_impl" in inspect.getsource(subscriber.subscriber_search_alerts)


def test_top_alerts_impl_has_exactly_one_remaining_caller():
    """Slice 3B.2J left the public route as its only caller — recorded, not removed."""
    from app.api import public_alerts

    source = inspect.getsource(public_alerts)
    calls = [
        node for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", "") == "top_alerts_impl"
    ]
    assert len(calls) == 1

    from app.api import subscriber

    assert "top_alerts_impl" not in inspect.getsource(subscriber)


# ===========================================================================
# Removed in this slice
# ===========================================================================


def test_dead_risk_level_helper_is_gone():
    from app.api import public_alerts

    assert not hasattr(public_alerts, "_title_case_level")


def test_dashboard_module_has_no_unused_user_import():
    from app.api import dashboard

    tree = ast.parse(inspect.getsource(dashboard))
    imported = {
        alias.asname or alias.name
        for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert "User" not in imported

    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert imported <= used | {"annotations"}, "no dead imports left behind"


def test_openapi_surface_is_unchanged_by_this_slice():
    """Only internals were removed, so the documented surface must be identical."""
    paths = set(app.openapi()["paths"])
    assert len(paths) == 59

    for path in ("/api/alerts", "/api/alerts/top", "/api/alerts/stats",
                 "/api/alerts/{alert_id}", "/api/search/alerts",
                 "/api/v1/subscriber/alerts/top",
                 "/api/v1/admin/sources/health",
                 "/api/v1/admin/sources/{source_id}/health",
                 "/api/v1/admin/system/health-summary"):
        assert path in paths, path


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
    assert public == {
        "/api/alerts", "/api/alerts/top", "/api/alerts/stats",
        "/api/alerts/{alert_id}", "/api/search/alerts", "/api/v1/health",
    }


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
        "legacy_jinja", "admin_api", "subscriber_api", "client_api",
        "public_api", "infrastructure",
    }
    for expected in ("legacy_jinja", "admin_api", "subscriber_api",
                     "client_api", "public_api", "infrastructure"):
        assert counts.get(expected, 0) > 0, f"no routes classified as {expected}"
    assert sum(counts.values()) == len(ROUTES)
