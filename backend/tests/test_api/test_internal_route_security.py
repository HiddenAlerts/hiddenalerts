"""Auth coverage for the internal source-admin, raw-item and statistics routes.

These routes expose full source configuration, the ingested article corpus and
internal pipeline counts, and one of them starts outbound collection. They are
admin-only; ``/api/v1/health`` stays public for deployment probes.
"""
import uuid

import pytest
from fastapi.routing import APIRoute

from app.api.health import router as health_router
from app.api.raw_items import router as raw_items_router
from app.api.sources import router as sources_router
from app.auth import create_access_token, hash_password, require_admin
from app.main import app
from app.models.source import Source
from app.models.user import User
from app.services import collection_guard

# (method, path) for every admin-only internal route, with concrete ids.
PROTECTED_ROUTES = [
    ("GET", "/api/v1/sources"),
    ("GET", "/api/v1/sources/1"),
    ("PATCH", "/api/v1/sources/1"),
    ("GET", "/api/v1/sources/1/runs"),
    ("POST", "/api/v1/sources/1/trigger"),
    ("GET", "/api/v1/raw-items"),
    ("GET", "/api/v1/raw-items/1"),
    ("GET", "/api/v1/stats"),
]

# Path templates as registered on the app, for the dependency-graph assertions.
PROTECTED_PATH_TEMPLATES = {
    ("GET", "/api/v1/sources"),
    ("GET", "/api/v1/sources/{source_id}"),
    ("PATCH", "/api/v1/sources/{source_id}"),
    ("GET", "/api/v1/sources/{source_id}/runs"),
    ("POST", "/api/v1/sources/{source_id}/trigger"),
    ("GET", "/api/v1/raw-items"),
    ("GET", "/api/v1/raw-items/{item_id}"),
    ("GET", "/api/v1/stats"),
}

_PATCH_BODY = {"notes": "audit note"}


async def _make_user(db_session, role: str = "admin", is_active: bool = True) -> User:
    user = User(
        email=f"{role}_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password("pw"),
        is_active=is_active,
        role=role,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


def _auth(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"}


async def _make_source(db_session, **overrides) -> Source:
    fields = {
        "name": f"Test Source {uuid.uuid4().hex[:6]}",
        "base_url": "https://example.test/news",
        "source_type": "rss",
        "rss_url": "https://example.test/feed.xml",
        "adapter_class": "krebs.KrebsAdapter",
        "is_active": True,
        **overrides,
    }
    source = Source(**fields)
    db_session.add(source)
    await db_session.commit()
    await db_session.refresh(source)
    return source


async def _request(client, method: str, path: str, **kwargs):
    if method == "PATCH":
        kwargs.setdefault("json", _PATCH_BODY)
    return await client.request(method, path, **kwargs)


@pytest.fixture(autouse=True)
def clear_collection_guard():
    """Keep the module-level claim set from leaking between tests."""
    collection_guard._active_source_runs.clear()
    yield
    collection_guard._active_source_runs.clear()


@pytest.fixture
def no_op_collection(monkeypatch):
    """Replace the real collector so trigger tests never touch the network.

    Records the source ids it was called with so tests can assert the background
    task did (or did not) run.
    """
    calls: list[int] = []

    async def _fake_trigger(source_id: int) -> None:
        calls.append(source_id)

    monkeypatch.setattr(
        "app.scheduler.jobs.trigger_source_by_id", _fake_trigger, raising=True
    )
    return calls


# ---------------------------------------------------------------------------
# Unauthenticated / non-admin rejection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("method,path", PROTECTED_ROUTES)
@pytest.mark.asyncio
async def test_unauthenticated_is_rejected(client, method, path):
    resp = await _request(client, method, path)
    assert resp.status_code == 401


@pytest.mark.parametrize("method,path", PROTECTED_ROUTES)
@pytest.mark.asyncio
async def test_invalid_token_is_rejected(client, method, path):
    resp = await _request(
        client, method, path, headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert resp.status_code == 401


@pytest.mark.parametrize("method,path", PROTECTED_ROUTES)
@pytest.mark.asyncio
async def test_subscriber_is_forbidden(client, db_session, method, path):
    subscriber = await _make_user(db_session, role="subscriber")
    resp = await _request(client, method, path, headers=_auth(subscriber))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_rejection_happens_before_any_data_is_returned(client):
    """A rejected raw-item request must not leak article content in the body."""
    resp = await client.get("/api/v1/raw-items")
    assert resp.status_code == 401
    assert "raw_text" not in resp.text


@pytest.mark.asyncio
async def test_deactivated_admin_is_rejected(client, db_session):
    """A valid token for a deactivated admin grants no access."""
    admin = await _make_user(db_session, is_active=False)
    resp = await client.get("/api/v1/sources", headers=_auth(admin))
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Admin access
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_list_sources(client, db_session):
    admin = await _make_user(db_session)
    await _make_source(db_session)
    resp = await client.get("/api/v1/sources", headers=_auth(admin))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_admin_can_get_source_detail(client, db_session):
    admin = await _make_user(db_session)
    source = await _make_source(db_session)
    resp = await client.get(f"/api/v1/sources/{source.id}", headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.json()["id"] == source.id


@pytest.mark.asyncio
async def test_admin_gets_404_for_unknown_source(client, db_session):
    admin = await _make_user(db_session)
    resp = await client.get("/api/v1/sources/99999", headers=_auth(admin))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_can_patch_source(client, db_session):
    admin = await _make_user(db_session)
    source = await _make_source(db_session, is_active=True)
    resp = await client.patch(
        f"/api/v1/sources/{source.id}",
        json={"is_active": False, "notes": "paused for maintenance"},
        headers=_auth(admin),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_active"] is False
    assert body["notes"] == "paused for maintenance"


@pytest.mark.asyncio
async def test_admin_can_read_source_runs(client, db_session):
    admin = await _make_user(db_session)
    source = await _make_source(db_session)
    resp = await client.get(f"/api/v1/sources/{source.id}/runs", headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_admin_can_list_raw_items(client, db_session):
    admin = await _make_user(db_session)
    resp = await client.get("/api/v1/raw-items", headers=_auth(admin))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_admin_gets_404_for_unknown_raw_item(client, db_session):
    admin = await _make_user(db_session)
    resp = await client.get("/api/v1/raw-items/99999", headers=_auth(admin))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_can_read_stats(client, db_session):
    admin = await _make_user(db_session)
    resp = await client.get("/api/v1/stats", headers=_auth(admin))
    assert resp.status_code == 200
    assert "total_raw_items" in resp.json()


# ---------------------------------------------------------------------------
# Manual trigger — auth, concurrency guard, background-task isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_trigger_collection(client, db_session, no_op_collection):
    admin = await _make_user(db_session)
    source = await _make_source(db_session)
    resp = await client.post(
        f"/api/v1/sources/{source.id}/trigger", headers=_auth(admin)
    )
    assert resp.status_code == 202
    assert resp.json()["source_id"] == source.id
    assert no_op_collection == [source.id]


@pytest.mark.asyncio
async def test_unauthenticated_trigger_starts_no_collection(
    client, db_session, no_op_collection
):
    """Rejection happens before any collection work is scheduled or claimed."""
    source = await _make_source(db_session)

    resp = await client.post(f"/api/v1/sources/{source.id}/trigger")

    assert resp.status_code == 401
    assert no_op_collection == []
    assert not collection_guard.is_source_collecting(source.id)


@pytest.mark.asyncio
async def test_subscriber_trigger_starts_no_collection(
    client, db_session, no_op_collection
):
    """A non-admin token cannot schedule or claim a collection run either."""
    subscriber = await _make_user(db_session, role="subscriber")
    source = await _make_source(db_session)

    resp = await client.post(
        f"/api/v1/sources/{source.id}/trigger", headers=_auth(subscriber)
    )

    assert resp.status_code == 403
    assert no_op_collection == []
    assert not collection_guard.is_source_collecting(source.id)


@pytest.mark.asyncio
async def test_trigger_404_for_unknown_source_does_not_claim_slot(
    client, db_session, no_op_collection
):
    admin = await _make_user(db_session)
    resp = await client.post("/api/v1/sources/99999/trigger", headers=_auth(admin))
    assert resp.status_code == 404
    assert no_op_collection == []
    assert not collection_guard.is_source_collecting(99999)


@pytest.mark.asyncio
async def test_trigger_conflicts_while_a_run_is_in_flight(
    client, db_session, no_op_collection
):
    admin = await _make_user(db_session)
    source = await _make_source(db_session)

    assert await collection_guard.claim_source_run(source.id) is True

    resp = await client.post(
        f"/api/v1/sources/{source.id}/trigger", headers=_auth(admin)
    )
    assert resp.status_code == 409
    assert "already in progress" in resp.json()["detail"]
    # No second background task was scheduled.
    assert no_op_collection == []


@pytest.mark.asyncio
async def test_trigger_conflict_is_scoped_to_one_source(
    client, db_session, no_op_collection
):
    admin = await _make_user(db_session)
    busy = await _make_source(db_session)
    idle = await _make_source(db_session)

    await collection_guard.claim_source_run(busy.id)

    resp = await client.post(f"/api/v1/sources/{idle.id}/trigger", headers=_auth(admin))
    assert resp.status_code == 202
    assert no_op_collection == [idle.id]


@pytest.mark.asyncio
async def test_slot_is_released_after_a_successful_run(
    client, db_session, no_op_collection
):
    admin = await _make_user(db_session)
    source = await _make_source(db_session)

    first = await client.post(
        f"/api/v1/sources/{source.id}/trigger", headers=_auth(admin)
    )
    assert first.status_code == 202
    assert not collection_guard.is_source_collecting(source.id)

    second = await client.post(
        f"/api/v1/sources/{source.id}/trigger", headers=_auth(admin)
    )
    assert second.status_code == 202
    assert no_op_collection == [source.id, source.id]


@pytest.mark.asyncio
async def test_slot_is_released_when_collection_fails(client, db_session, monkeypatch):
    admin = await _make_user(db_session)
    source = await _make_source(db_session)

    async def _boom(source_id: int) -> None:
        raise RuntimeError("upstream unreachable")

    monkeypatch.setattr("app.scheduler.jobs.trigger_source_by_id", _boom, raising=True)

    resp = await client.post(
        f"/api/v1/sources/{source.id}/trigger", headers=_auth(admin)
    )
    assert resp.status_code == 202
    assert not collection_guard.is_source_collecting(source.id)


# ---------------------------------------------------------------------------
# Guard primitive
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_guard_claim_is_exclusive_then_reusable():
    assert await collection_guard.claim_source_run(7) is True
    assert await collection_guard.claim_source_run(7) is False
    assert collection_guard.is_source_collecting(7) is True

    await collection_guard.release_source_run(7)
    assert collection_guard.is_source_collecting(7) is False
    assert await collection_guard.claim_source_run(7) is True


@pytest.mark.asyncio
async def test_guard_release_is_idempotent():
    await collection_guard.claim_source_run(9)
    await collection_guard.release_source_run(9)
    await collection_guard.release_source_run(9)
    assert collection_guard.is_source_collecting(9) is False


# ---------------------------------------------------------------------------
# Route surface — dependency graph, and what must stay public
# ---------------------------------------------------------------------------


def _flatten_dependencies(dependant):
    for sub in dependant.dependencies:
        yield sub
        yield from _flatten_dependencies(sub)


def _requires_admin(route: APIRoute) -> bool:
    return any(d.call is require_admin for d in _flatten_dependencies(route.dependant))


@pytest.mark.parametrize(
    "router",
    [sources_router, raw_items_router],
    ids=["sources", "raw-items"],
)
def test_every_route_in_internal_router_requires_admin(router):
    """Catches a new route being added to these modules without admin auth."""
    routes = [r for r in router.routes if isinstance(r, APIRoute)]
    assert routes
    unprotected = [
        f"{sorted(r.methods)} {r.path}" for r in routes if not _requires_admin(r)
    ]
    assert not unprotected, f"routes missing require_admin: {unprotected}"


def test_all_expected_routes_are_still_registered():
    """The secured paths keep their public URLs — no path or method drift."""
    paths = app.openapi()["paths"]
    for method, path in sorted(PROTECTED_PATH_TEMPLATES):
        assert path in paths, f"{path} disappeared from the API surface"
        assert method.lower() in paths[path], f"{method} {path} is no longer registered"


@pytest.mark.asyncio
async def test_health_stays_public(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert "status" in resp.json()


def test_health_route_has_no_admin_dependency():
    routes = [r for r in health_router.routes if isinstance(r, APIRoute)]
    assert routes
    assert not any(_requires_admin(r) for r in routes)
