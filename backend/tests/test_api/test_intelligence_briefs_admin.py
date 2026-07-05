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
