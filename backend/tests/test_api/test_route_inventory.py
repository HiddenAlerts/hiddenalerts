"""Route inventory and legacy-dependency guards (Slice 3B.2K).

This module pins what the 2026-08-02 audit *proved*, not what would be
convenient. Routes with confirmed callers or insufficient evidence are asserted
**present**; nothing is asserted absent unless it was actually removed.

Evidence behind each retention is recorded in
``reports/legacy_route_cleanup_slice3b2k_20260802.md``.
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
def test_jinja_dashboard_is_retained(path):
    """A real admin login on 26 Jul 2026 landed on /dashboard with HTTP 200.

    Source Health APIs replace the *monitoring* view, but the dashboard is still
    in use and its removal belongs to a later slice.
    """
    assert any(m for (m, p) in ROUTES if p == path), path


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
