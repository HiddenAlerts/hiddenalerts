"""Endpoint tests for /api/v1/subscriber/intelligence-briefs.

Supabase validation is mocked (as in the other subscriber tests); the active
subscription guard, the visibility filters, and the DB all run for real.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.intelligence_brief import IntelligenceBrief
from app.schemas.intelligence_brief import IntelligenceBriefCreate
from app.services import intelligence_brief_service as briefs
from tests.test_api.test_subscriber_api import _claims, _patch_validator
from tests.test_api.test_subscriber_content import (
    _AUTH,
    _seed_profile_with_subscription,
)

BASE = "/api/v1/subscriber/intelligence-briefs"


async def _active_subscriber(db_session) -> str:
    sub_id = f"active-{uuid.uuid4()}"
    await _seed_profile_with_subscription(db_session, sub_id=sub_id, status="active")
    return sub_id


async def _publish(db_session, *, risk_level="critical", **overrides) -> IntelligenceBrief:
    payload = {
        "title": "Subscriber brief",
        "category": "Fraud Intelligence",
        "risk_score": 90,
        "risk_level": risk_level,
        "executive_summary": "<p>Executive summary</p>",
        "main_intelligence_brief": "<p>Full brief body</p>",
    }
    payload.update(overrides)
    brief = await briefs.create_brief(
        db_session, IntelligenceBriefCreate(**payload), user_id=None
    )
    return await briefs.publish_brief(db_session, brief.id, user_id=None)


async def _draft(db_session, **overrides) -> IntelligenceBrief:
    payload = {"title": "Draft brief", **overrides}
    return await briefs.create_brief(
        db_session, IntelligenceBriefCreate(**payload), user_id=None
    )


# ---------------------------------------------------------------------------
# Access guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_library_requires_auth(client: AsyncClient):
    resp = await client.get(BASE)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_library_requires_active_subscription(client: AsyncClient):
    with _patch_validator(_claims(sub=f"nosub-{uuid.uuid4()}")):
        resp = await client.get(BASE, headers=_AUTH)
    assert resp.status_code == 403
    assert resp.json()["detail"] == "active_subscription_required"


# ---------------------------------------------------------------------------
# Library
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_paid_subscriber_can_list(client: AsyncClient, db_session: AsyncSession):
    sub_id = await _active_subscriber(db_session)
    with _patch_validator(_claims(sub=sub_id)):
        resp = await client.get(BASE, headers=_AUTH)
    assert resp.status_code == 200
    assert {"items", "total", "limit", "offset"} <= resp.json().keys()


@pytest.mark.asyncio
async def test_library_returns_only_visible(client: AsyncClient, db_session: AsyncSession):
    cat = f"cat-{uuid.uuid4().hex[:8]}"
    await _publish(db_session, category=cat, risk_level="critical")
    await _publish(db_session, category=cat, risk_level="high")
    await _publish(db_session, category=cat, risk_level="medium")
    await _draft(db_session, category=cat)

    sub_id = await _active_subscriber(db_session)
    with _patch_validator(_claims(sub=sub_id)):
        resp = await client.get(f"{BASE}?category={cat}", headers=_AUTH)
    body = resp.json()
    assert body["total"] == 2
    assert {item["risk_level"] for item in body["items"]} == {"critical", "high"}
    assert all("is_featured" in item for item in body["items"])


@pytest.mark.asyncio
async def test_library_risk_level_critical_filter(client: AsyncClient, db_session: AsyncSession):
    cat = f"cat-{uuid.uuid4().hex[:8]}"
    await _publish(db_session, category=cat, risk_level="critical")
    await _publish(db_session, category=cat, risk_level="high")

    sub_id = await _active_subscriber(db_session)
    with _patch_validator(_claims(sub=sub_id)):
        resp = await client.get(f"{BASE}?category={cat}&risk_level=critical", headers=_AUTH)
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["risk_level"] == "critical"


@pytest.mark.asyncio
async def test_library_risk_level_medium_rejected(client: AsyncClient, db_session: AsyncSession):
    sub_id = await _active_subscriber(db_session)
    with _patch_validator(_claims(sub=sub_id)):
        resp = await client.get(f"{BASE}?risk_level=medium", headers=_AUTH)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_detail_by_slug(client: AsyncClient, db_session: AsyncSession):
    brief = await _publish(db_session, risk_level="critical")
    sub_id = await _active_subscriber(db_session)
    with _patch_validator(_claims(sub=sub_id)):
        resp = await client.get(f"{BASE}/{brief.slug}", headers=_AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["slug"] == brief.slug
    assert body["main_intelligence_brief"] is not None
    # is_featured is intentionally exposed for featured-card badges.
    assert "is_featured" in body


@pytest.mark.asyncio
async def test_detail_hidden_slugs_return_404(client: AsyncClient, db_session: AsyncSession):
    draft = await _draft(db_session)
    archived = await _publish(db_session)
    await briefs.archive_brief(db_session, archived.id, user_id=None)
    medium = await _publish(db_session, risk_level="medium")
    low = await _publish(db_session, risk_level="low")

    sub_id = await _active_subscriber(db_session)
    with _patch_validator(_claims(sub=sub_id)):
        for slug in (draft.slug, archived.slug, medium.slug, low.slug, "no-such-slug"):
            resp = await client.get(f"{BASE}/{slug}", headers=_AUTH)
            assert resp.status_code == 404, slug


@pytest.mark.asyncio
async def test_detail_excludes_admin_fields(client: AsyncClient, db_session: AsyncSession):
    brief = await _publish(db_session, analyst_notes="<p>secret</p>")
    sub_id = await _active_subscriber(db_session)
    with _patch_validator(_claims(sub=sub_id)):
        resp = await client.get(f"{BASE}/{brief.slug}", headers=_AUTH)
    body = resp.json()
    assert "analyst_notes" not in body
    assert "featured_image_path" not in body
    assert "created_by_user_id" not in body
    assert "updated_by_user_id" not in body


# ---------------------------------------------------------------------------
# Featured
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_featured_returns_visible_featured(client: AsyncClient, db_session: AsyncSession):
    brief = await _publish(db_session, risk_level="critical")
    await briefs.feature_brief(db_session, brief.id, user_id=None)

    sub_id = await _active_subscriber(db_session)
    with _patch_validator(_claims(sub=sub_id)):
        resp = await client.get(f"{BASE}/featured", headers=_AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == brief.id
    assert "analyst_notes" not in body


@pytest.mark.asyncio
async def test_featured_missing_returns_404(client: AsyncClient, db_session: AsyncSession):
    # Clear any leaked featured rows so this transaction has none.
    await db_session.execute(
        update(IntelligenceBrief)
        .values(is_featured=False, featured_order=None)
        .execution_options(synchronize_session=False)
    )
    await db_session.flush()

    sub_id = await _active_subscriber(db_session)
    with _patch_validator(_claims(sub=sub_id)):
        resp = await client.get(f"{BASE}/featured", headers=_AUTH)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Featured intelligence brief not found"


@pytest.mark.asyncio
async def test_featured_ignores_archived_bad_data(client: AsyncClient, db_session: AsyncSession):
    # An archived brief carrying a stale is_featured=True must never surface.
    await db_session.execute(
        update(IntelligenceBrief)
        .values(is_featured=False, featured_order=None)
        .execution_options(synchronize_session=False)
    )
    await db_session.flush()

    brief = await _publish(db_session, risk_level="critical")
    await briefs.archive_brief(db_session, brief.id, user_id=None)
    brief.is_featured = True
    await db_session.flush()

    sub_id = await _active_subscriber(db_session)
    with _patch_validator(_claims(sub=sub_id)):
        resp = await client.get(f"{BASE}/featured", headers=_AUTH)
    assert resp.status_code == 404
