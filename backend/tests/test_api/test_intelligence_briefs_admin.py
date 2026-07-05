"""Tests for the admin Intelligence Brief REST endpoints."""
from __future__ import annotations

import uuid

import pytest

from app.auth import create_access_token, hash_password
from app.config import settings
from app.models.user import User
from app.services.intelligence_brief_images import MAX_UPLOAD_BYTES

BASE = "/api/v1/admin/intelligence-briefs"


@pytest.fixture
def upload_root(monkeypatch, tmp_path):
    """Redirect featured-image writes to a throwaway tmp path for each test."""
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


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


# ---------------------------------------------------------------------------
# Featured image upload / remove
# ---------------------------------------------------------------------------


async def _create_brief(client, admin, **overrides) -> int:
    payload = {"title": "Image brief", **overrides}
    resp = await client.post(BASE, json=payload, headers=_auth(admin))
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _image(filename: str, content_type: str, content: bytes = b"image-bytes") -> dict:
    return {"file": (filename, content, content_type)}


@pytest.mark.asyncio
async def test_admin_can_upload_featured_image(client, db_session, upload_root):
    admin = await _make_user(db_session)
    brief_id = await _create_brief(client, admin)
    resp = await client.post(
        f"{BASE}/{brief_id}/featured-image",
        files=_image("photo.jpg", "image/jpeg"),
        headers=_auth(admin),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["featured_image_url"].startswith("/uploads/intelligence-briefs/")
    assert body["featured_image_url"].endswith(".jpg")


@pytest.mark.parametrize(
    "filename, content_type",
    [("photo.png", "image/png"), ("photo.webp", "image/webp")],
)
@pytest.mark.asyncio
async def test_upload_png_and_webp(client, db_session, upload_root, filename, content_type):
    admin = await _make_user(db_session)
    brief_id = await _create_brief(client, admin)
    resp = await client.post(
        f"{BASE}/{brief_id}/featured-image",
        files=_image(filename, content_type),
        headers=_auth(admin),
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_upload_missing_brief_returns_404(client, db_session, upload_root):
    admin = await _make_user(db_session)
    resp = await client.post(
        f"{BASE}/999999/featured-image",
        files=_image("photo.jpg", "image/jpeg"),
        headers=_auth(admin),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_upload_invalid_type_returns_422(client, db_session, upload_root):
    admin = await _make_user(db_session)
    brief_id = await _create_brief(client, admin)
    resp = await client.post(
        f"{BASE}/{brief_id}/featured-image",
        files=_image("evil.svg", "image/svg+xml"),
        headers=_auth(admin),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_upload_too_large_returns_422(client, db_session, upload_root):
    admin = await _make_user(db_session)
    brief_id = await _create_brief(client, admin)
    resp = await client.post(
        f"{BASE}/{brief_id}/featured-image",
        files=_image("big.jpg", "image/jpeg", content=b"\x00" * (MAX_UPLOAD_BYTES + 1)),
        headers=_auth(admin),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_admin_can_replace_featured_image(client, db_session, upload_root):
    admin = await _make_user(db_session)
    brief_id = await _create_brief(client, admin)
    first = await client.post(
        f"{BASE}/{brief_id}/featured-image",
        files=_image("a.jpg", "image/jpeg"),
        headers=_auth(admin),
    )
    second = await client.post(
        f"{BASE}/{brief_id}/featured-image",
        files=_image("b.png", "image/png"),
        headers=_auth(admin),
    )
    assert second.status_code == 200
    assert second.json()["featured_image_url"] != first.json()["featured_image_url"]
    assert second.json()["featured_image_url"].endswith(".png")


@pytest.mark.asyncio
async def test_admin_can_remove_featured_image(client, db_session, upload_root):
    admin = await _make_user(db_session)
    brief_id = await _create_brief(client, admin)
    await client.post(
        f"{BASE}/{brief_id}/featured-image",
        files=_image("a.jpg", "image/jpeg"),
        headers=_auth(admin),
    )
    resp = await client.request("DELETE", f"{BASE}/{brief_id}/featured-image", headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.json()["featured_image_url"] is None


@pytest.mark.asyncio
async def test_remove_missing_brief_returns_404(client, db_session, upload_root):
    admin = await _make_user(db_session)
    resp = await client.request("DELETE", f"{BASE}/999999/featured-image", headers=_auth(admin))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_upload_requires_auth(client, upload_root):
    resp = await client.post(
        f"{BASE}/1/featured-image", files=_image("a.jpg", "image/jpeg")
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_upload_forbidden_for_non_admin(client, db_session, upload_root):
    subscriber = await _make_user(db_session, role="subscriber")
    resp = await client.post(
        f"{BASE}/1/featured-image",
        files=_image("a.jpg", "image/jpeg"),
        headers=_auth(subscriber),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# List search / filter / pagination edge cases
# ---------------------------------------------------------------------------


async def _create(client, admin, **fields) -> dict:
    payload = {"title": "Brief", **fields}
    resp = await client.post(BASE, json=payload, headers=_auth(admin))
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.parametrize("field", ["executive_summary", "main_intelligence_brief"])
@pytest.mark.asyncio
async def test_admin_list_q_searches_content_fields(client, db_session, field):
    admin = await _make_user(db_session)
    token = uuid.uuid4().hex[:8]
    await _create(client, admin, title="Plain", **{field: f"<p>needle {token}</p>"})
    resp = await client.get(BASE, params={"q": token}, headers=_auth(admin))
    body = resp.json()
    assert body["total"] == 1


@pytest.mark.asyncio
async def test_admin_list_q_searches_title(client, db_session):
    admin = await _make_user(db_session)
    token = uuid.uuid4().hex[:8]
    await _create(client, admin, title=f"Title {token}")
    resp = await client.get(BASE, params={"q": f"title {token}"}, headers=_auth(admin))
    assert resp.json()["total"] == 1


@pytest.mark.asyncio
async def test_admin_list_whitespace_q_behaves_like_no_q(client, db_session):
    admin = await _make_user(db_session)
    cat = f"cat-{uuid.uuid4().hex[:8]}"
    await _create(client, admin, category=cat)
    resp = await client.get(BASE, params={"category": cat, "q": "   "}, headers=_auth(admin))
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


@pytest.mark.asyncio
async def test_admin_list_status_filters(client, db_session):
    admin = await _make_user(db_session)
    cat = f"cat-{uuid.uuid4().hex[:8]}"
    await _create(client, admin, category=cat)  # draft
    resp = await client.get(BASE, params={"category": cat, "status": "draft"}, headers=_auth(admin))
    assert resp.json()["total"] == 1
    resp = await client.get(BASE, params={"category": cat, "status": "published"}, headers=_auth(admin))
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_admin_list_invalid_risk_level_returns_422(client, db_session):
    admin = await _make_user(db_session)
    resp = await client.get(BASE, params={"risk_level": "extreme"}, headers=_auth(admin))
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_admin_list_risk_level_filter(client, db_session):
    admin = await _make_user(db_session)
    cat = f"cat-{uuid.uuid4().hex[:8]}"
    await _create(client, admin, category=cat, risk_level="critical")
    await _create(client, admin, category=cat, risk_level="low")
    resp = await client.get(BASE, params={"category": cat, "risk_level": "critical"}, headers=_auth(admin))
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["risk_level"] == "critical"


@pytest.mark.asyncio
async def test_admin_list_brief_type_filter_and_validation(client, db_session):
    admin = await _make_user(db_session)
    cat = f"cat-{uuid.uuid4().hex[:8]}"
    await _create(client, admin, category=cat)
    ok = await client.get(BASE, params={"category": cat, "brief_type": "intelligence_brief"}, headers=_auth(admin))
    assert ok.json()["total"] == 1
    bad = await client.get(BASE, params={"brief_type": "memo"}, headers=_auth(admin))
    assert bad.status_code == 422


@pytest.mark.asyncio
async def test_admin_list_is_premium_filter(client, db_session):
    admin = await _make_user(db_session)
    cat = f"cat-{uuid.uuid4().hex[:8]}"
    await _create(client, admin, category=cat)  # is_premium defaults True
    yes = await client.get(BASE, params={"category": cat, "is_premium": "true"}, headers=_auth(admin))
    assert yes.json()["total"] == 1
    no = await client.get(BASE, params={"category": cat, "is_premium": "false"}, headers=_auth(admin))
    assert no.json()["total"] == 0


@pytest.mark.asyncio
async def test_admin_list_is_featured_filter(client, db_session):
    admin = await _make_user(db_session)
    cat = f"cat-{uuid.uuid4().hex[:8]}"
    created = await _create(
        client, admin, category=cat, risk_level="critical",
        executive_summary="<p>s</p>", main_intelligence_brief="<p>b</p>", risk_score=90,
    )
    bid = created["id"]
    await client.post(f"{BASE}/{bid}/publish", headers=_auth(admin))
    await client.post(f"{BASE}/{bid}/feature", headers=_auth(admin))
    resp = await client.get(BASE, params={"category": cat, "is_featured": "true"}, headers=_auth(admin))
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["is_featured"] is True


@pytest.mark.asyncio
async def test_admin_list_limit_offset_paging(client, db_session):
    admin = await _make_user(db_session)
    cat = f"cat-{uuid.uuid4().hex[:8]}"
    for _ in range(3):
        await _create(client, admin, category=cat)
    page1 = await client.get(BASE, params={"category": cat, "limit": 2, "offset": 0}, headers=_auth(admin))
    b1 = page1.json()
    assert b1["total"] == 3 and len(b1["items"]) == 2
    page2 = await client.get(BASE, params={"category": cat, "limit": 2, "offset": 2}, headers=_auth(admin))
    b2 = page2.json()
    assert b2["total"] == 3 and len(b2["items"]) == 1


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 9999}, {"offset": -1}])
@pytest.mark.asyncio
async def test_admin_list_invalid_paging_returns_422(client, db_session, params):
    admin = await _make_user(db_session)
    resp = await client.get(BASE, params=params, headers=_auth(admin))
    assert resp.status_code == 422
