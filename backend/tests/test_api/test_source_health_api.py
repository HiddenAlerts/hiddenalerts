"""The three admin-only Source Health endpoints.

Read-only observability: nothing here collects, mutates or remediates.
"""
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import delete

from app.auth import create_access_token, hash_password
from app.main import app
from app.models.processed_alert import ProcessedAlert
from app.models.raw_item import RawItem
from app.models.run_log import RunLog
from app.models.source import Source
from app.models.user import User

LIST_URL = "/api/v1/admin/sources/health"
SUMMARY_URL = "/api/v1/admin/system/health-summary"


def _detail_url(source_id: int) -> str:
    return f"/api/v1/admin/sources/{source_id}/health"


async def _make_user(db_session, role="admin") -> User:
    user = User(
        email=f"{role}-{uuid.uuid4().hex[:8]}@health.test",
        password_hash=hash_password("pw"), role=role, is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


def _auth(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"}


@pytest.fixture
async def health_fixture(db_session):
    """A small estate: one healthy, one failing, one disabled, one valid-empty."""
    created: list[int] = []

    async def _source(name, is_active=True):
        src = Source(
            name=name, base_url="https://health.test", source_type="rss",
            adapter_class="krebs.KrebsAdapter", is_active=is_active,
            credibility_score=4,
        )
        db_session.add(src)
        await db_session.commit()
        await db_session.refresh(src)
        created.append(src.id)
        return src

    now = datetime.utcnow()

    def _run(source, *, ago_hours, status="success", fetched=0, new=0,
             invalid=0, external=0, error=None):
        started = now - timedelta(hours=ago_hours)
        return RunLog(
            source_id=source.id, run_started_at=started,
            run_finished_at=started + timedelta(seconds=20), status=status,
            items_fetched=fetched, items_new=new, items_duplicate=0,
            items_skipped_url=0, items_skipped_content=0,
            items_skipped_invalid=invalid, items_skipped_external=external,
            error_message=error,
        )

    healthy = await _source("Alpha Healthy")
    failing = await _source("Beta Failing")
    empty = await _source("Gamma Valid Empty")
    disabled = await _source("Delta Disabled", is_active=False)

    db_session.add_all([
        _run(healthy, ago_hours=2, fetched=12, new=3, external=5),
        _run(healthy, ago_hours=8, fetched=10, new=2, external=4),
        _run(failing, ago_hours=1, status="failed", error="feed exploded"),
        _run(failing, ago_hours=7, status="failed", error="feed exploded earlier"),
        _run(empty, ago_hours=1, fetched=0, new=0),
        _run(empty, ago_hours=7, fetched=0, new=0),
        _run(empty, ago_hours=13, fetched=0, new=0),
        _run(disabled, ago_hours=3, fetched=5, new=1),
    ])

    item = RawItem(
        source_id=healthy.id, item_url="https://health.test/a", title="A",
        published_at=now - timedelta(hours=3), raw_text="text", raw_html="",
        content_hash=f"c{uuid.uuid4().hex[:10]}", url_hash=f"u{uuid.uuid4().hex[:10]}",
        is_duplicate=False, fetched_at=now - timedelta(hours=2),
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)

    db_session.add(ProcessedAlert(
        raw_item_id=item.id, is_relevant=True, is_published=True,
        published_at=now - timedelta(hours=1),
    ))
    await db_session.commit()

    yield {"healthy": healthy, "failing": failing, "empty": empty,
           "disabled": disabled, "ids": created}

    await db_session.rollback()
    rows = (await db_session.execute(
        RawItem.__table__.select().where(RawItem.source_id.in_(created))
    )).all()
    await db_session.execute(delete(ProcessedAlert).where(
        ProcessedAlert.raw_item_id.in_([r.id for r in rows] or [-1])
    ))
    await db_session.execute(delete(RawItem).where(RawItem.source_id.in_(created)))
    await db_session.execute(delete(RunLog).where(RunLog.source_id.in_(created)))
    await db_session.execute(delete(Source).where(Source.id.in_(created)))
    await db_session.commit()


# ===========================================================================
# Authorization
# ===========================================================================


@pytest.mark.parametrize("url", [LIST_URL, SUMMARY_URL, "/api/v1/admin/sources/1/health"])
@pytest.mark.asyncio
async def test_unauthenticated_is_401(client, url):
    assert (await client.get(url)).status_code == 401


@pytest.mark.parametrize("url", [LIST_URL, SUMMARY_URL, "/api/v1/admin/sources/1/health"])
@pytest.mark.asyncio
async def test_non_admin_is_403(client, db_session, url):
    viewer = await _make_user(db_session, role="viewer")
    assert (await client.get(url, headers=_auth(viewer))).status_code == 403


@pytest.mark.asyncio
async def test_admin_is_200(client, db_session, health_fixture):
    admin = await _make_user(db_session)
    for url in (LIST_URL, SUMMARY_URL, _detail_url(health_fixture["healthy"].id)):
        assert (await client.get(url, headers=_auth(admin))).status_code == 200, url


def test_no_new_public_route_is_introduced():
    from app.api.source_health import router

    for route in router.routes:
        dependencies = str(route.dependant.dependencies)
        assert "require_admin" in dependencies or any(
            "require_admin" in str(d.call) for d in route.dependant.dependencies
        ), route.path


def test_every_health_route_is_read_only():
    from app.api.source_health import router

    for route in router.routes:
        assert set(route.methods) == {"GET"}, route.path


def test_existing_runs_route_authorization_is_unchanged():
    from tests.test_api.test_internal_route_security import PROTECTED_ROUTES

    assert ("GET", "/api/v1/sources/1/runs") in PROTECTED_ROUTES


# ===========================================================================
# List endpoint
# ===========================================================================


@pytest.mark.asyncio
async def test_list_returns_one_record_per_source(client, db_session, health_fixture):
    admin = await _make_user(db_session)
    body = (await client.get(LIST_URL, headers=_auth(admin))).json()

    returned = {r["source_id"] for r in body}
    assert set(health_fixture["ids"]) <= returned
    assert len(body) == len({r["source_id"] for r in body}), "no duplicates"


@pytest.mark.asyncio
async def test_list_orders_worst_state_first(client, db_session, health_fixture):
    admin = await _make_user(db_session)
    body = (await client.get(LIST_URL, headers=_auth(admin))).json()

    severity = {"error": 0, "warning": 1, "disabled": 2, "healthy": 3}
    ranks = [severity[r["state"]] for r in body]
    assert ranks == sorted(ranks), "states must be grouped worst first"

    ours = {r["source_id"]: r for r in body}
    assert ours[health_fixture["failing"].id]["state"] == "error"
    assert ours[health_fixture["empty"].id]["state"] == "warning"
    assert ours[health_fixture["disabled"].id]["state"] == "disabled"
    assert ours[health_fixture["healthy"].id]["state"] == "healthy"


@pytest.mark.asyncio
async def test_ordering_is_deterministic_across_calls(client, db_session, health_fixture):
    admin = await _make_user(db_session)
    first = (await client.get(LIST_URL, headers=_auth(admin))).json()
    second = (await client.get(LIST_URL, headers=_auth(admin))).json()

    assert [r["source_id"] for r in first] == [r["source_id"] for r in second]


@pytest.mark.asyncio
async def test_valid_empty_source_is_a_warning_not_an_error(
    client, db_session, health_fixture
):
    admin = await _make_user(db_session)
    body = (await client.get(LIST_URL, headers=_auth(admin))).json()
    record = next(r for r in body if r["source_id"] == health_fixture["empty"].id)

    assert record["state"] == "warning"
    assert record["reason_code"] == "no_upstream_content"
    assert record["consecutive_zero_fetch_runs"] == 3


@pytest.mark.asyncio
async def test_collector_failure_is_distinguishable_from_empty_upstream(
    client, db_session, health_fixture
):
    admin = await _make_user(db_session)
    body = {r["source_id"]: r for r in (await client.get(LIST_URL, headers=_auth(admin))).json()}

    failing = body[health_fixture["failing"].id]
    empty = body[health_fixture["empty"].id]

    assert failing["state"] == "error" and failing["reason_code"] == "repeated_failures"
    assert failing["last_error_message"] == "feed exploded"
    assert empty["state"] == "warning"


@pytest.mark.asyncio
async def test_external_telemetry_is_present_and_distinct(
    client, db_session, health_fixture
):
    admin = await _make_user(db_session)
    body = {r["source_id"]: r for r in (await client.get(LIST_URL, headers=_auth(admin))).json()}
    record = body[health_fixture["healthy"].id]

    assert record["latest_run_items_skipped_external"] == 5
    assert record["items_skipped_external_24h"] == 9
    assert record["items_skipped_external_7d"] == 9
    assert record["items_skipped_invalid_24h"] == 0
    assert record["state"] == "healthy", "external exclusions are not a defect"


@pytest.mark.asyncio
async def test_list_query_count_does_not_grow_with_sources(
    client, db_session, health_fixture
):
    """Guards the N+1 property: more sources must not mean more queries."""
    from sqlalchemy import event

    admin = await _make_user(db_session)
    statements: list[str] = []

    engine = db_session.bind.sync_engine

    def _record(conn, cursor, statement, params, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", _record)
    try:
        statements.clear()
        await client.get(LIST_URL, headers=_auth(admin))
        baseline = len(statements)

        extra = [
            Source(name=f"Extra {n}", base_url="https://health.test",
                   source_type="rss", adapter_class="krebs.KrebsAdapter",
                   is_active=True)
            for n in range(6)
        ]
        db_session.add_all(extra)
        await db_session.commit()

        statements.clear()
        await client.get(LIST_URL, headers=_auth(admin))
        with_more = len(statements)
    finally:
        event.remove(engine, "before_cursor_execute", _record)
        await db_session.execute(
            delete(Source).where(Source.id.in_([s.id for s in extra]))
        )
        await db_session.commit()

    assert with_more == baseline, (
        f"query count grew from {baseline} to {with_more} after adding 6 sources"
    )


@pytest.mark.asyncio
async def test_empty_database_returns_an_empty_list(client, db_session):
    """No sources at all is a valid answer, not an error."""
    from app.api import source_health

    async def _none(session):
        return []

    original = source_health.load_sources
    source_health.load_sources = _none
    try:
        admin = await _make_user(db_session)
        response = await client.get(LIST_URL, headers=_auth(admin))
    finally:
        source_health.load_sources = original

    assert response.status_code == 200
    assert response.json() == []


# ===========================================================================
# Detail endpoint
# ===========================================================================


@pytest.mark.asyncio
async def test_detail_returns_health_and_runs(client, db_session, health_fixture):
    admin = await _make_user(db_session)
    source = health_fixture["healthy"]
    body = (await client.get(_detail_url(source.id), headers=_auth(admin))).json()

    assert body["health"]["source_id"] == source.id
    assert body["health"]["state"] == "healthy"
    assert len(body["recent_runs"]) == 2


@pytest.mark.asyncio
async def test_detail_runs_are_newest_first(client, db_session, health_fixture):
    admin = await _make_user(db_session)
    body = (await client.get(
        _detail_url(health_fixture["healthy"].id), headers=_auth(admin)
    )).json()

    starts = [r["run_started_at"] for r in body["recent_runs"]]
    assert starts == sorted(starts, reverse=True)


@pytest.mark.asyncio
async def test_detail_runs_include_external_counter(client, db_session, health_fixture):
    admin = await _make_user(db_session)
    body = (await client.get(
        _detail_url(health_fixture["healthy"].id), headers=_auth(admin)
    )).json()

    latest = body["recent_runs"][0]
    assert latest["items_skipped_external"] == 5
    assert latest["items_skipped_invalid"] == 0


@pytest.mark.asyncio
async def test_detail_metrics_agree_with_the_list(client, db_session, health_fixture):
    admin = await _make_user(db_session)
    source = health_fixture["healthy"]

    listed = next(
        r for r in (await client.get(LIST_URL, headers=_auth(admin))).json()
        if r["source_id"] == source.id
    )
    detailed = (await client.get(
        _detail_url(source.id), headers=_auth(admin)
    )).json()["health"]

    for field in ("state", "reason_code", "items_new_24h", "items_skipped_external_24h",
                  "total_raw_items", "total_published_alerts",
                  "consecutive_failed_runs"):
        assert listed[field] == detailed[field], field


@pytest.mark.asyncio
async def test_unknown_source_is_404(client, db_session):
    admin = await _make_user(db_session)
    assert (await client.get(_detail_url(999999), headers=_auth(admin))).status_code == 404


@pytest.mark.asyncio
async def test_default_run_limit_is_twenty(client, db_session, health_fixture):
    admin = await _make_user(db_session)
    source = health_fixture["healthy"]
    now = datetime.utcnow()

    db_session.add_all([
        RunLog(source_id=source.id, run_started_at=now - timedelta(hours=20 + n),
               run_finished_at=now - timedelta(hours=20 + n), status="success",
               items_fetched=1, items_new=0, items_duplicate=0, items_skipped_url=1,
               items_skipped_content=0, items_skipped_invalid=0,
               items_skipped_external=0)
        for n in range(30)
    ])
    await db_session.commit()

    body = (await client.get(_detail_url(source.id), headers=_auth(admin))).json()
    assert len(body["recent_runs"]) == 20


@pytest.mark.parametrize("limit,expected_status", [
    (1, 200), (100, 200), (0, 422), (101, 422), (-5, 422),
])
@pytest.mark.asyncio
async def test_run_limit_validation(client, db_session, health_fixture, limit, expected_status):
    admin = await _make_user(db_session)
    response = await client.get(
        f"{_detail_url(health_fixture['healthy'].id)}?limit={limit}",
        headers=_auth(admin),
    )
    assert response.status_code == expected_status


# ===========================================================================
# System summary
# ===========================================================================


@pytest.mark.asyncio
async def test_by_state_sums_to_sources_total(client, db_session, health_fixture):
    admin = await _make_user(db_session)
    body = (await client.get(SUMMARY_URL, headers=_auth(admin))).json()

    assert sum(body["by_state"].values()) == body["sources_total"]
    assert set(body["by_state"]) == {"healthy", "warning", "error", "disabled"}


@pytest.mark.asyncio
async def test_attention_list_holds_only_error_and_warning(
    client, db_session, health_fixture
):
    admin = await _make_user(db_session)
    body = (await client.get(SUMMARY_URL, headers=_auth(admin))).json()
    attention = body["sources_needing_attention"]

    assert attention, "the fixture has an error and a warning source"
    assert all(entry["state"] in ("error", "warning") for entry in attention)
    assert all("reason_code" in entry and entry["reason_code"] for entry in attention)


@pytest.mark.asyncio
async def test_attention_list_orders_error_before_warning(
    client, db_session, health_fixture
):
    admin = await _make_user(db_session)
    body = (await client.get(SUMMARY_URL, headers=_auth(admin))).json()
    states = [entry["state"] for entry in body["sources_needing_attention"]]

    assert states == sorted(states, key=lambda s: 0 if s == "error" else 1)
    assert states[0] == "error"


@pytest.mark.asyncio
async def test_attention_list_is_capped(client, db_session, health_fixture):
    from app.services.source_health_service import DEFAULT_THRESHOLDS

    admin = await _make_user(db_session)
    body = (await client.get(SUMMARY_URL, headers=_auth(admin))).json()

    assert len(body["sources_needing_attention"]) <= DEFAULT_THRESHOLDS.max_attention_sources


@pytest.mark.asyncio
async def test_summary_uses_the_real_scheduler_contract(client, db_session, health_fixture):
    from app.config import settings
    from app.scheduler.jobs import scheduler

    admin = await _make_user(db_session)
    body = (await client.get(SUMMARY_URL, headers=_auth(admin))).json()

    assert body["scheduler_interval_hours"] == float(settings.scheduler_interval_hours)
    assert body["scheduler_running"] is bool(scheduler.running)


@pytest.mark.asyncio
async def test_summary_totals_and_revision(client, db_session, health_fixture):
    admin = await _make_user(db_session)
    body = (await client.get(SUMMARY_URL, headers=_auth(admin))).json()

    assert body["items_new_24h"] >= 6
    assert body["items_skipped_external_24h"] >= 9
    assert body["items_skipped_external_7d"] >= 9
    assert body["raw_items_total"] >= 1
    assert body["processed_alerts_total"] >= 1
    assert body["published_alerts_total"] >= 1
    assert body["published_last_7d"] >= 1
    assert body["last_collection_cycle_at"] is not None
    # The metadata-built test database has no alembic table; None is the honest answer.
    assert "alembic_revision" in body


@pytest.mark.asyncio
async def test_summary_on_an_empty_estate(client, db_session):
    from app.api import source_health

    async def _none(session):
        return []

    original = source_health.load_sources
    source_health.load_sources = _none
    try:
        admin = await _make_user(db_session)
        body = (await client.get(SUMMARY_URL, headers=_auth(admin))).json()
    finally:
        source_health.load_sources = original

    assert body["sources_total"] == 0
    assert sum(body["by_state"].values()) == 0
    assert body["sources_needing_attention"] == []


# ===========================================================================
# OpenAPI
# ===========================================================================


def test_openapi_documents_all_three_routes():
    paths = app.openapi()["paths"]

    for path in ("/api/v1/admin/sources/health",
                 "/api/v1/admin/sources/{source_id}/health",
                 "/api/v1/admin/system/health-summary"):
        assert path in paths, path
        assert set(paths[path]) == {"get"}, f"{path} must be read-only"


def test_openapi_schemas_expose_external_fields():
    schemas = app.openapi()["components"]["schemas"]

    health = schemas["SourceHealthRead"]["properties"]
    for name in ("state", "reason_code", "items_skipped_invalid_24h",
                 "items_skipped_external_24h", "items_skipped_external_7d",
                 "latest_run_items_skipped_external"):
        assert name in health, name

    summary = schemas["SystemHealthSummary"]["properties"]
    for name in ("sources_total", "by_state", "sources_needing_attention",
                 "scheduler_running", "scheduler_interval_hours",
                 "items_skipped_external_24h", "items_skipped_external_7d",
                 "alembic_revision"):
        assert name in summary, name


# ===========================================================================
# Query budget (3B.2I refinement)
# ===========================================================================


async def _count_queries(db_session, client, url, headers) -> int:
    """SQL statements executed while serving one request to ``url``."""
    from sqlalchemy import event

    statements: list[str] = []
    engine = db_session.bind.sync_engine

    def _record(conn, cursor, statement, params, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", _record)
    try:
        statements.clear()
        response = await client.get(url, headers=headers)
        assert response.status_code == 200, url
        return len(statements)
    finally:
        event.remove(engine, "before_cursor_execute", _record)


@pytest.mark.asyncio
async def test_measured_query_budget_per_endpoint(client, db_session, health_fixture):
    """Ceilings on end-to-end queries, so a regression cannot quietly inflate them.

    Ceilings rather than exact equality: one statement — the endpoint's own
    ``db.get(Source, ...)`` — is skipped when the row is already in the session
    identity map, which depends on the caller, not on this code. The property that
    matters is that the count never *grows*, and that is asserted directly by the
    two constancy tests below.
    """
    admin = await _make_user(db_session)
    headers = _auth(admin)

    # 1 admin-auth lookup + 1 source load + 4 bounded aggregation queries.
    assert await _count_queries(db_session, client, LIST_URL, headers) <= 6
    # + 1 run-history select, - the identity-map hit on db.get.
    assert await _count_queries(
        db_session, client, _detail_url(health_fixture["healthy"].id), headers
    ) <= 7
    # + 3 instance-wide totals + 1 Alembic revision.
    assert await _count_queries(db_session, client, SUMMARY_URL, headers) <= 10


@pytest.mark.asyncio
async def test_query_budget_is_unchanged_by_deep_run_history(
    client, db_session, health_fixture
):
    """All-history success/error fields must not cost an extra query."""
    admin = await _make_user(db_session)
    headers = _auth(admin)
    now = datetime.utcnow()

    before = await _count_queries(db_session, client, LIST_URL, headers)

    db_session.add_all([
        RunLog(source_id=health_fixture["healthy"].id,
               run_started_at=now - timedelta(hours=30 + n),
               run_finished_at=now - timedelta(hours=30 + n), status="success",
               items_fetched=1, items_new=0, items_duplicate=0, items_skipped_url=1,
               items_skipped_content=0, items_skipped_invalid=0,
               items_skipped_external=0)
        for n in range(40)
    ])
    await db_session.commit()

    after = await _count_queries(db_session, client, LIST_URL, headers)
    assert after == before, "40 extra runs must not cost another query"


@pytest.mark.asyncio
async def test_deep_history_keeps_list_and_detail_in_agreement(
    client, db_session, health_fixture
):
    """A success older than the recent window must read the same on both routes."""
    admin = await _make_user(db_session)
    source = health_fixture["failing"]
    now = datetime.utcnow()

    # Bury the one success under more than `recent_runs_considered` failures.
    db_session.add_all([
        RunLog(source_id=source.id, run_started_at=now - timedelta(hours=2 + n),
               run_finished_at=now - timedelta(hours=2 + n), status="failed",
               items_fetched=0, items_new=0, items_duplicate=0, items_skipped_url=0,
               items_skipped_content=0, items_skipped_invalid=0,
               items_skipped_external=0, error_message="buried boom")
        for n in range(25)
    ])
    db_session.add(RunLog(
        source_id=source.id, run_started_at=now - timedelta(days=30),
        run_finished_at=now - timedelta(days=30), status="success",
        items_fetched=4, items_new=2, items_duplicate=0, items_skipped_url=0,
        items_skipped_content=0, items_skipped_invalid=0, items_skipped_external=0,
    ))
    await db_session.commit()

    listed = next(
        r for r in (await client.get(LIST_URL, headers=_auth(admin))).json()
        if r["source_id"] == source.id
    )
    detailed = (await client.get(
        _detail_url(source.id), headers=_auth(admin)
    )).json()["health"]

    assert listed["last_success_at"] is not None
    assert listed["last_success_at"] == detailed["last_success_at"]
    assert listed["reason_code"] == detailed["reason_code"] == "repeated_failures"
    assert listed["last_error_message"] == detailed["last_error_message"]


# ---------------------------------------------------------------------------
# Request clock awareness (Slice 3B.2M)
# ---------------------------------------------------------------------------


def test_request_clock_is_aware_utc():
    """`_utc_now` must return an aware UTC instant, not a naive one.

    A naive clock here is what made every Source Health route 500 against
    PostgreSQL, whose TIMESTAMPTZ columns come back aware.
    """
    from app.api import source_health as api

    now = api._utc_now()
    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)


def test_routes_do_not_call_utcnow():
    """No route may reintroduce a naive clock."""
    import ast
    import inspect

    from app.api import source_health as api

    tree = ast.parse(inspect.getsource(api))
    naive_calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "utcnow"
    ]
    assert not naive_calls, "datetime.utcnow() reintroduced in source_health API"


def test_each_route_freezes_one_clock_per_request():
    """Each handler takes the clock once, so one response is measured once."""
    import ast
    import inspect

    from app.api import source_health as api

    module = ast.parse(inspect.getsource(api))
    handlers = {
        "list_source_health", "get_source_health", "get_system_health_summary",
    }
    for node in ast.walk(module):
        if isinstance(node, ast.AsyncFunctionDef) and node.name in handlers:
            calls = [
                child for child in ast.walk(node)
                if isinstance(child, ast.Call)
                and isinstance(child.func, ast.Name)
                and child.func.id == "_utc_now"
            ]
            assert len(calls) == 1, f"{node.name} calls the clock {len(calls)} times"


@pytest.mark.asyncio
async def test_endpoints_serialize_timestamps_that_parse_as_utc(client, db_session):
    """Every timestamp the API emits must round-trip through fromisoformat."""
    admin = await _make_user(db_session)
    token = create_access_token({"sub": str(admin.id), "role": admin.role})
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get(LIST_URL, headers=headers)
    assert response.status_code == 200
    for record in response.json():
        for field_name in (
            "last_run_at", "last_success_at", "last_new_item_at",
            "latest_upstream_published_at", "last_error_at",
        ):
            value = record.get(field_name)
            if value is not None:
                datetime.fromisoformat(value)
