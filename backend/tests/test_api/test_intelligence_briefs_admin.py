"""Tests for the admin Intelligence Brief REST endpoints."""
from __future__ import annotations

import uuid

import pytest

from app.auth import create_access_token, hash_password
from app.models.user import User

BASE = "/api/v1/admin/intelligence-briefs"


async def _make_user(db_session, role: str = "admin") -> User:
    user = User(
        email=f"{role}_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password("pw"),
        is_active=True,
        role=role,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


def _auth(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"}


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_requires_auth(client):
    resp = await client.get(BASE)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_non_admin_forbidden(client, db_session):
    subscriber = await _make_user(db_session, role="subscriber")
    resp = await client.get(BASE, headers=_auth(subscriber))
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_create_brief(client, db_session):
    admin = await _make_user(db_session)
    resp = await client.post(
        BASE,
        json={
            "title": "North Korean IT Worker Networks",
            "risk_level": "critical",
            "executive_summary": "<p>Summary</p><script>evil()</script>",
            "supporting_alerts": [{"url": "https://x.com/1"}],
        },
        headers=_auth(admin),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "draft"
    assert body["is_featured"] is False
    assert body["is_premium"] is True
    assert body["brief_type"] == "intelligence_brief"
    assert body["slug"] == "north-korean-it-worker-networks"
    assert body["brief_code"].startswith("HA-")
    assert body["alerts_count"] == 1
    # HTML sanitised on the way in
    assert "<script" not in body["executive_summary"]


@pytest.mark.asyncio
async def test_create_invalid_payload_returns_422(client, db_session):
    admin = await _make_user(db_session)
    resp = await client.post(BASE, json={"title": "   "}, headers=_auth(admin))
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_invalid_risk_score_returns_422(client, db_session):
    admin = await _make_user(db_session)
    resp = await client.post(
        BASE, json={"title": "X", "risk_score": 250}, headers=_auth(admin)
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_duplicate_provided_slug_returns_409(client, db_session):
    admin = await _make_user(db_session)
    payload = {"title": "First", "slug": "dupe"}
    first = await client.post(BASE, json=payload, headers=_auth(admin))
    assert first.status_code == 201
    second = await client.post(
        BASE, json={"title": "Second", "slug": "dupe"}, headers=_auth(admin)
    )
    assert second.status_code == 409


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_list_and_filter(client, db_session):
    admin = await _make_user(db_session)
    # A unique category scopes the counts to this test — the API commits, and the
    # in-memory test engine shares one connection across tests.
    category = f"cat-{uuid.uuid4().hex[:8]}"
    await client.post(
        BASE,
        json={"title": "Critical one", "category": category, "risk_level": "critical"},
        headers=_auth(admin),
    )
    await client.post(
        BASE,
        json={"title": "Medium two", "category": category, "risk_level": "medium"},
        headers=_auth(admin),
    )

    resp = await client.get(f"{BASE}?category={category}", headers=_auth(admin))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2
    assert {"limit", "offset", "total", "items"} <= body.keys()

    resp = await client.get(
        f"{BASE}?category={category}&risk_level=critical", headers=_auth(admin)
    )
    assert resp.json()["total"] == 1


@pytest.mark.asyncio
async def test_list_search_by_title(client, db_session):
    admin = await _make_user(db_session)
    token = uuid.uuid4().hex[:8]
    await client.post(BASE, json={"title": f"Account Takeover {token}"}, headers=_auth(admin))
    await client.post(BASE, json={"title": f"Ransomware {token}"}, headers=_auth(admin))

    resp = await client.get(f"{BASE}?q=takeover {token}", headers=_auth(admin))
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == f"Account Takeover {token}"


@pytest.mark.asyncio
async def test_list_invalid_status_filter_returns_422(client, db_session):
    admin = await _make_user(db_session)
    resp = await client.get(f"{BASE}?status=bogus", headers=_auth(admin))
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_detail_includes_analyst_notes(client, db_session):
    admin = await _make_user(db_session)
    created = await client.post(
        BASE,
        json={"title": "Detail brief", "analyst_notes": "<p>internal</p>"},
        headers=_auth(admin),
    )
    brief_id = created.json()["id"]

    resp = await client.get(f"{BASE}/{brief_id}", headers=_auth(admin))
    assert resp.status_code == 200
    body = resp.json()
    assert "analyst_notes" in body
    assert "internal" in body["analyst_notes"]


@pytest.mark.asyncio
async def test_detail_missing_returns_404(client, db_session):
    admin = await _make_user(db_session)
    resp = await client.get(f"{BASE}/999999", headers=_auth(admin))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_update_brief(client, db_session):
    admin = await _make_user(db_session)
    created = await client.post(
        BASE, json={"title": "Before", "category": "Fraud"}, headers=_auth(admin)
    )
    brief_id = created.json()["id"]

    resp = await client.put(
        f"{BASE}/{brief_id}",
        json={"category": "Emerging Threat"},
        headers=_auth(admin),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["category"] == "Emerging Threat"
    assert body["title"] == "Before"


@pytest.mark.asyncio
async def test_update_missing_returns_404(client, db_session):
    admin = await _make_user(db_session)
    resp = await client.put(
        f"{BASE}/999999", json={"title": "Nope"}, headers=_auth(admin)
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_cannot_set_status_or_featured(client, db_session):
    admin = await _make_user(db_session)
    created = await client.post(BASE, json={"title": "CRUD only"}, headers=_auth(admin))
    brief_id = created.json()["id"]

    # status / is_featured are not in the update schema — extra keys are ignored,
    # so lifecycle cannot be changed through generic PUT.
    resp = await client.put(
        f"{BASE}/{brief_id}",
        json={"status": "published", "is_featured": True, "category": "X"},
        headers=_auth(admin),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "draft"
    assert body["is_featured"] is False
    assert body["category"] == "X"


# ---------------------------------------------------------------------------
# Lifecycle actions
# ---------------------------------------------------------------------------

_PUBLISHABLE = {
    "category": "Fraud Intelligence",
    "risk_score": 90,
    "risk_level": "critical",
    "executive_summary": "<p>Executive summary</p>",
    "main_intelligence_brief": "<p>Full brief body</p>",
}


async def _create_publishable(client, admin, **overrides) -> int:
    payload = {"title": "Publishable", **_PUBLISHABLE, **overrides}
    resp = await client.post(BASE, json=payload, headers=_auth(admin))
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_admin_can_publish(client, db_session):
    admin = await _make_user(db_session)
    brief_id = await _create_publishable(client, admin)
    resp = await client.post(f"{BASE}/{brief_id}/publish", headers=_auth(admin))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "published"
    assert body["published_at"] is not None


@pytest.mark.asyncio
async def test_publish_missing_returns_404(client, db_session):
    admin = await _make_user(db_session)
    resp = await client.post(f"{BASE}/999999/publish", headers=_auth(admin))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_publish_invalid_returns_422(client, db_session):
    admin = await _make_user(db_session)
    # A sparse draft missing risk_score/level and content cannot be published.
    created = await client.post(BASE, json={"title": "Sparse"}, headers=_auth(admin))
    brief_id = created.json()["id"]
    resp = await client.post(f"{BASE}/{brief_id}/publish", headers=_auth(admin))
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_admin_can_archive(client, db_session):
    admin = await _make_user(db_session)
    brief_id = await _create_publishable(client, admin)
    resp = await client.post(f"{BASE}/{brief_id}/archive", headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"


@pytest.mark.asyncio
async def test_archive_missing_returns_404(client, db_session):
    admin = await _make_user(db_session)
    resp = await client.post(f"{BASE}/999999/archive", headers=_auth(admin))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_archive_clears_featured_state(client, db_session):
    admin = await _make_user(db_session)
    brief_id = await _create_publishable(client, admin)
    await client.post(f"{BASE}/{brief_id}/publish", headers=_auth(admin))
    await client.post(f"{BASE}/{brief_id}/feature", headers=_auth(admin))

    resp = await client.post(f"{BASE}/{brief_id}/archive", headers=_auth(admin))
    body = resp.json()
    assert body["status"] == "archived"
    assert body["is_featured"] is False
    assert body["featured_order"] is None


@pytest.mark.asyncio
async def test_admin_can_feature_eligible_brief(client, db_session):
    admin = await _make_user(db_session)
    brief_id = await _create_publishable(client, admin, risk_level="high")
    await client.post(f"{BASE}/{brief_id}/publish", headers=_auth(admin))
    resp = await client.post(f"{BASE}/{brief_id}/feature", headers=_auth(admin))
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_featured"] is True
    assert body["featured_order"] == 1


@pytest.mark.asyncio
async def test_feature_missing_returns_404(client, db_session):
    admin = await _make_user(db_session)
    resp = await client.post(f"{BASE}/999999/feature", headers=_auth(admin))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_feature_ineligible_returns_422(client, db_session):
    admin = await _make_user(db_session)
    # Draft (not published) is ineligible for featuring.
    brief_id = await _create_publishable(client, admin)
    resp = await client.post(f"{BASE}/{brief_id}/feature", headers=_auth(admin))
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_feature_replaces_existing_featured(client, db_session):
    admin = await _make_user(db_session)
    a = await _create_publishable(client, admin, title="Feature A")
    b = await _create_publishable(client, admin, title="Feature B")
    await client.post(f"{BASE}/{a}/publish", headers=_auth(admin))
    await client.post(f"{BASE}/{b}/publish", headers=_auth(admin))

    await client.post(f"{BASE}/{a}/feature", headers=_auth(admin))
    await client.post(f"{BASE}/{b}/feature", headers=_auth(admin))

    a_detail = await client.get(f"{BASE}/{a}", headers=_auth(admin))
    b_detail = await client.get(f"{BASE}/{b}", headers=_auth(admin))
    assert a_detail.json()["is_featured"] is False
    assert b_detail.json()["is_featured"] is True


@pytest.mark.asyncio
async def test_admin_can_unfeature(client, db_session):
    admin = await _make_user(db_session)
    brief_id = await _create_publishable(client, admin)
    await client.post(f"{BASE}/{brief_id}/publish", headers=_auth(admin))
    await client.post(f"{BASE}/{brief_id}/feature", headers=_auth(admin))

    resp = await client.post(f"{BASE}/{brief_id}/unfeature", headers=_auth(admin))
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_featured"] is False
    assert body["featured_order"] is None


@pytest.mark.asyncio
async def test_lifecycle_actions_require_auth(client):
    for action in ("publish", "archive", "feature", "unfeature"):
        resp = await client.post(f"{BASE}/1/{action}")
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_lifecycle_actions_forbidden_for_non_admin(client, db_session):
    subscriber = await _make_user(db_session, role="subscriber")
    resp = await client.post(f"{BASE}/1/publish", headers=_auth(subscriber))
    assert resp.status_code == 403
