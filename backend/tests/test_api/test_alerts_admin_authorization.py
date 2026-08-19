"""Pre-Launch Admin Authorization Hardening — runtime 401/403 coverage for the
Internal Alert/Event surface in ``app/api/alerts.py``.

Before this slice, ``GET/POST /api/v1/alerts*`` and ``GET /api/v1/events*``
accepted any authenticated Internal JWT user (``get_current_user`` only) even
though they expose unpublished alerts, internal moderation/scoring state, and
mutation operations — an inconsistent boundary against every other
administrative surface (Sources, Raw Items, Stats, Admin Alert Categories,
Source Health, Intelligence Brief CMS), which already used ``require_admin``.
All six routes in ``app/api/alerts.py`` now use the same ``require_admin``
dependency.

Mirrors the established pattern in ``test_internal_route_security.py``
(no-token / invalid-token / subscriber / deactivated-admin rejection, admin
success), plus the module-specific negative proofs hardening exists for here:
a rejected review mutates nothing in the database, and a rejected processing
trigger schedules nothing.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi import BackgroundTasks
from jose import jwt as jose_jwt
from sqlalchemy import delete, select

from app.auth import create_access_token, hash_password
from app.config import settings
from app.models.processed_alert import ProcessedAlert
from app.models.raw_item import RawItem
from app.models.review import AlertReview
from app.models.source import Source
from app.models.user import User

#: Every Source this module creates uses this prefix, so the autouse cleanup
#: fixture below can find and remove exactly the rows this module added —
#: without it, a seeded alert would leak into the shared session-scoped test
#: DB and could break an unrelated test elsewhere that asserts an empty list
#: (e.g. test_alerts_api.py::test_list_alerts_empty_db).
_SOURCE_NAME_PREFIX = "AuthzSrc "


@pytest.fixture(autouse=True)
async def _cleanup_seeded_alerts(db_session):
    yield
    await db_session.rollback()
    source_ids = (
        await db_session.execute(
            select(Source.id).where(Source.name.startswith(_SOURCE_NAME_PREFIX))
        )
    ).scalars().all()
    if not source_ids:
        return
    raw_ids = (
        await db_session.execute(
            select(RawItem.id).where(RawItem.source_id.in_(source_ids))
        )
    ).scalars().all()
    if raw_ids:
        await db_session.execute(
            delete(AlertReview).where(
                AlertReview.alert_id.in_(
                    select(ProcessedAlert.id).where(ProcessedAlert.raw_item_id.in_(raw_ids))
                )
            )
        )
        await db_session.execute(delete(ProcessedAlert).where(ProcessedAlert.raw_item_id.in_(raw_ids)))
        await db_session.execute(delete(RawItem).where(RawItem.id.in_(raw_ids)))
    await db_session.execute(delete(Source).where(Source.id.in_(source_ids)))
    await db_session.commit()

# (method, path) for every hardened admin-only Alert/Event route, concrete ids.
PROTECTED_ROUTES = [
    ("GET", "/api/v1/alerts"),
    ("GET", "/api/v1/alerts/1"),
    ("POST", "/api/v1/alerts/process"),
    ("GET", "/api/v1/events"),
    ("GET", "/api/v1/events/1"),
]


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


def _supabase_shaped_token() -> str:
    """A JWT shaped like a real Supabase token (UUID ``sub``, Supabase claims)
    but signed with a different secret than the Internal JWT — exactly what a
    genuine Supabase-issued token looks like from this app's perspective. Used
    to prove the Internal decoder rejects it rather than treating it as some
    Internal user id.
    """
    payload = {
        "sub": str(uuid.uuid4()),
        "email": "subscriber@example.com",
        "aud": "authenticated",
        "iss": "https://test.supabase.co/auth/v1",
    }
    return jose_jwt.encode(payload, "not-the-internal-jwt-secret", algorithm=settings.jwt_algorithm)


async def _seed_alert(db_session, **overrides) -> ProcessedAlert:
    suffix = uuid.uuid4().hex[:10]
    source = Source(
        name=f"AuthzSrc {suffix}", base_url=f"https://authz-{suffix}.test",
        source_type="rss", credibility_score=4, adapter_class="RSSAdapter",
    )
    db_session.add(source)
    await db_session.flush()
    raw = RawItem(
        source_id=source.id, item_url=f"https://authz-{suffix}.test/a",
        title=f"Authz {suffix}", url_hash=f"authz-{suffix}",
    )
    db_session.add(raw)
    await db_session.flush()
    fields = dict(
        raw_item_id=raw.id, is_relevant=True, primary_category="Cybercrime",
        signal_score_total=18, risk_level="medium", risk_band="high",
        summary="Original summary.", processed_at=datetime.now(timezone.utc),
        is_published=False,
    )
    fields.update(overrides)
    alert = ProcessedAlert(**fields)
    db_session.add(alert)
    await db_session.commit()
    await db_session.refresh(alert)
    return alert


# ---------------------------------------------------------------------------
# Baseline 401 / 403 / admin-success matrix (mirrors test_internal_route_security.py)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("method,path", PROTECTED_ROUTES)
@pytest.mark.asyncio
async def test_no_token_is_401(client, method, path):
    resp = await client.request(method, path)
    assert resp.status_code == 401


@pytest.mark.parametrize("method,path", PROTECTED_ROUTES)
@pytest.mark.asyncio
async def test_invalid_token_is_401(client, method, path):
    resp = await client.request(
        method, path, headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert resp.status_code == 401


@pytest.mark.parametrize("method,path", PROTECTED_ROUTES)
@pytest.mark.asyncio
async def test_active_non_admin_internal_jwt_is_403(client, db_session, method, path):
    """A real row in the internal users table, role=subscriber, is_active=true,
    with a token minted by the same Internal JWT helper the app uses — proving
    authentication succeeds and role authorization is what fails.
    """
    subscriber = await _make_user(db_session, role="subscriber")
    resp = await client.request(method, path, headers=_auth(subscriber))
    assert resp.status_code == 403


@pytest.mark.parametrize("method,path", PROTECTED_ROUTES)
@pytest.mark.asyncio
async def test_deactivated_admin_is_401_not_403(client, db_session, method, path):
    """get_current_user rejects an inactive account with 401 before
    require_admin's role check ever runs — the 403 branch is unreachable."""
    admin = await _make_user(db_session, role="admin", is_active=False)
    resp = await client.request(method, path, headers=_auth(admin))
    assert resp.status_code == 401


@pytest.mark.parametrize("method,path", PROTECTED_ROUTES)
@pytest.mark.asyncio
async def test_supabase_shaped_token_cannot_reach_the_internal_admin_surface(client, method, path):
    """Subscriber token isolation (LOCKED SECURITY OBJECTIVE): a Supabase JWT
    must not become an Internal Admin credential. No interop is added — this
    follows the Internal JWT parser's existing behavior."""
    resp = await client.request(
        method, path, headers={"Authorization": f"Bearer {_supabase_shaped_token()}"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_alert_detail_forbidden_regardless_of_whether_the_id_exists(client, db_session):
    """A non-admin must not learn whether an alert id exists via a different
    status code — 403 is returned identically before any lookup happens,
    because FastAPI resolves require_admin before the route body ever runs."""
    subscriber = await _make_user(db_session, role="subscriber")
    real = await _seed_alert(db_session)

    existing = await client.get(f"/api/v1/alerts/{real.id}", headers=_auth(subscriber))
    missing = await client.get("/api/v1/alerts/99999999", headers=_auth(subscriber))
    assert existing.status_code == 403
    assert missing.status_code == 403


@pytest.mark.asyncio
async def test_admin_still_gets_alert_detail(client, db_session):
    admin = await _make_user(db_session, role="admin")
    alert = await _seed_alert(db_session)
    resp = await client.get(f"/api/v1/alerts/{alert.id}", headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.json()["id"] == alert.id


@pytest.mark.asyncio
async def test_admin_still_lists_alerts(client, db_session):
    admin = await _make_user(db_session, role="admin")
    alert = await _seed_alert(db_session)
    resp = await client.get("/api/v1/alerts", headers=_auth(admin))
    assert resp.status_code == 200
    assert alert.id in [a["id"] for a in resp.json()]


@pytest.mark.asyncio
async def test_admin_still_lists_events(client, db_session):
    admin = await _make_user(db_session, role="admin")
    resp = await client.get("/api/v1/events", headers=_auth(admin))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_admin_gets_404_for_unknown_event(client, db_session):
    admin = await _make_user(db_session, role="admin")
    resp = await client.get("/api/v1/events/99999999", headers=_auth(admin))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Review mutation — the highest-priority protected route (§7/§8/§29)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_review_forbidden_for_non_admin_mutates_nothing(client, db_session):
    """Proves persistence, not merely the status code: every field a review
    action can touch is captured before the forbidden request and re-checked
    unchanged after it, and no AlertReview row is created."""
    alert = await _seed_alert(db_session)
    tracked_fields = (
        "summary", "risk_level", "risk_band", "is_published", "published_at",
        "published_by_user_id", "publish_decision", "publish_decision_reason",
        "pending_review_reason", "is_excluded", "excluded_reason",
        "is_manual_hold", "published_by_rule", "publication_state_source",
        "publication_state_updated_at",
    )
    before = {f: getattr(alert, f) for f in tracked_fields}
    existing_review_ids = set(
        (await db_session.execute(select(AlertReview.id))).scalars().all()
    )

    subscriber = await _make_user(db_session, role="subscriber")
    resp = await client.post(
        f"/api/v1/alerts/{alert.id}/review",
        json={
            "review_status": "approved",
            "edited_summary": "A subscriber should never be able to write this.",
            "adjusted_risk_level": "critical",
        },
        headers=_auth(subscriber),
    )
    assert resp.status_code == 403

    await db_session.refresh(alert)
    after = {f: getattr(alert, f) for f in tracked_fields}
    assert after == before, f"forbidden review mutated: {[f for f in tracked_fields if before[f] != after[f]]}"

    new_review_ids = set(
        (await db_session.execute(select(AlertReview.id))).scalars().all()
    )
    assert new_review_ids == existing_review_ids, "no AlertReview row must be created by a forbidden request"


@pytest.mark.asyncio
async def test_admin_approval_still_records_the_correct_admin_user_id(client, db_session):
    """require_admin returns the real ORM User (not a bool, not a subscriber
    profile id, not None) — review.user_id and published_by_user_id must
    still be the actual admin who approved."""
    admin = await _make_user(db_session, role="admin")
    alert = await _seed_alert(db_session, is_relevant=True)

    resp = await client.post(
        f"/api/v1/alerts/{alert.id}/review",
        json={"review_status": "approved"},
        headers=_auth(admin),
    )
    assert resp.status_code == 200
    assert resp.json()["user_id"] == admin.id

    await db_session.refresh(alert)
    assert alert.published_by_user_id == admin.id


# ---------------------------------------------------------------------------
# Manual processing trigger — authorization before scheduling (§9/§30)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_processing_trigger_forbidden_for_non_admin_schedules_nothing(client, db_session):
    subscriber = await _make_user(db_session, role="subscriber")

    with patch.object(BackgroundTasks, "add_task") as mock_add_task, \
         patch("app.pipeline.alert_pipeline.is_processing") as mock_is_processing, \
         patch("app.pipeline.alert_pipeline.process_unprocessed_items") as mock_process:
        resp = await client.post("/api/v1/alerts/process", headers=_auth(subscriber))

    assert resp.status_code == 403
    # require_admin rejects before the route body runs at all — not just before
    # add_task, but before the existing is_processing() lock check too.
    mock_is_processing.assert_not_called()
    mock_add_task.assert_not_called()
    mock_process.assert_not_called()


@pytest.mark.asyncio
async def test_processing_trigger_unauthenticated_schedules_nothing(client):
    with patch.object(BackgroundTasks, "add_task") as mock_add_task:
        resp = await client.post("/api/v1/alerts/process")

    assert resp.status_code == 401
    mock_add_task.assert_not_called()
