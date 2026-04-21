"""Tests for app/api/alerts.py and app/api/client_alerts.py REST endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.auth import create_access_token, hash_password
from app.models.processed_alert import ProcessedAlert
from app.models.raw_item import RawItem
from app.models.source import Source
from app.models.user import User


# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------


async def _create_admin_user(db_session) -> User:
    """Create an admin user with a unique email to avoid UNIQUE constraint conflicts."""
    unique_email = f"admin_{uuid.uuid4().hex[:8]}@test.com"
    user = User(
        email=unique_email,
        password_hash=hash_password("adminpass"),
        is_active=True,
        role="admin",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _create_subscriber_user(db_session) -> User:
    """Create a subscriber user with a unique email."""
    unique_email = f"sub_{uuid.uuid4().hex[:8]}@test.com"
    user = User(
        email=unique_email,
        password_hash=hash_password("subpass"),
        is_active=True,
        role="subscriber",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


def _make_token(user: User) -> str:
    """Create a JWT token using the session-patched TEST_JWT_SECRET."""
    return create_access_token({"sub": str(user.id)})


async def _make_source_and_raw(db_session, *, url_suffix: str = "") -> tuple[Source, RawItem]:
    """Create a Source + RawItem pair for use in alert tests."""
    source = Source(
        name=f"Test Source {url_suffix}",
        base_url=f"https://test-{url_suffix}.com",
        source_type="rss",
        credibility_score=4,
        adapter_class="RSSAdapter",
    )
    db_session.add(source)
    await db_session.flush()

    raw = RawItem(
        source_id=source.id,
        item_url=f"https://test-{url_suffix}.com/article",
        title=f"Test Article {url_suffix}",
        url_hash=f"hash_{url_suffix}_{uuid.uuid4().hex[:8]}",
    )
    db_session.add(raw)
    await db_session.flush()
    return source, raw


# ---------------------------------------------------------------------------
# Existing admin alert endpoints (backwards compat)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_alerts_requires_auth(client):
    """GET /api/v1/alerts without cookie returns 401."""
    response = await client.get("/api/v1/alerts")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_alerts_empty_db(client, db_session):
    """Authenticated request to empty DB returns empty list."""
    user = await _create_admin_user(db_session)
    token = _make_token(user)

    response = await client.get(
        "/api/v1/alerts",
        cookies={"access_token": token},
    )
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_alert_not_found(client, db_session):
    """GET /api/v1/alerts/9999 returns 404."""
    user = await _create_admin_user(db_session)
    token = _make_token(user)

    response = await client.get(
        "/api/v1/alerts/9999",
        cookies={"access_token": token},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_alerts_with_data(client, db_session):
    """Authenticated list returns created alerts."""
    user = await _create_admin_user(db_session)
    _, raw = await _make_source_and_raw(db_session, url_suffix="list001")

    alert = ProcessedAlert(
        raw_item_id=raw.id,
        risk_level="high",
        primary_category="Cybercrime",
        signal_score_total=15,
        is_relevant=True,
        matched_keywords=["fraud"],
        processed_at=datetime.now(timezone.utc),
    )
    db_session.add(alert)
    await db_session.commit()

    token = _make_token(user)
    response = await client.get("/api/v1/alerts", cookies={"access_token": token})
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    ids = [d["id"] for d in data]
    assert alert.id in ids


@pytest.mark.asyncio
async def test_trigger_processing_returns_202(client, db_session):
    """POST /api/v1/alerts/process returns 202 when pipeline not running."""
    user = await _create_admin_user(db_session)
    token = _make_token(user)

    with patch("app.pipeline.alert_pipeline.is_processing", return_value=False):
        response = await client.post(
            "/api/v1/alerts/process",
            cookies={"access_token": token},
        )

    assert response.status_code == 202
    assert response.json()["status"] == "accepted"


@pytest.mark.asyncio
async def test_trigger_processing_returns_409_when_locked(client, db_session):
    """POST /api/v1/alerts/process returns 409 when pipeline already running."""
    user = await _create_admin_user(db_session)
    token = _make_token(user)

    with patch("app.pipeline.alert_pipeline.is_processing", return_value=True):
        response = await client.post(
            "/api/v1/alerts/process",
            cookies={"access_token": token},
        )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_list_events_requires_auth(client):
    """GET /api/v1/events without auth returns 401."""
    response = await client.get("/api/v1/events")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_submit_review_invalid_status(client, db_session):
    """POST /api/v1/alerts/{id}/review with invalid status returns 422."""
    user = await _create_admin_user(db_session)
    _, raw = await _make_source_and_raw(db_session, url_suffix="rev001")

    alert = ProcessedAlert(
        raw_item_id=raw.id,
        is_relevant=True,
        processed_at=datetime.now(timezone.utc),
    )
    db_session.add(alert)
    await db_session.commit()

    token = _make_token(user)
    response = await client.post(
        f"/api/v1/alerts/{alert.id}/review",
        json={"review_status": "invalid_status"},
        cookies={"access_token": token},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Publication state — alert fields
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_published_alert_returns_is_published_true(client, db_session):
    """Admin list endpoint returns is_published=true for published alerts."""
    user = await _create_admin_user(db_session)
    _, raw = await _make_source_and_raw(db_session, url_suffix="pub001")

    alert = ProcessedAlert(
        raw_item_id=raw.id,
        risk_level="high",
        signal_score_total=18,
        is_relevant=True,
        is_published=True,
        published_at=datetime.now(timezone.utc),
        processed_at=datetime.now(timezone.utc),
    )
    db_session.add(alert)
    await db_session.commit()

    token = _make_token(user)
    response = await client.get(
        f"/api/v1/alerts/{alert.id}",
        cookies={"access_token": token},
    )
    assert response.status_code == 200
    assert response.json()["is_published"] is True


@pytest.mark.asyncio
async def test_is_published_filter_admin(client, db_session):
    """Admin can filter GET /api/v1/alerts?is_published=true."""
    user = await _create_admin_user(db_session)
    _, raw_pub = await _make_source_and_raw(db_session, url_suffix="filt001")
    _, raw_unpub = await _make_source_and_raw(db_session, url_suffix="filt002")

    published = ProcessedAlert(
        raw_item_id=raw_pub.id, is_relevant=True, is_published=True,
        processed_at=datetime.now(timezone.utc),
    )
    unpublished = ProcessedAlert(
        raw_item_id=raw_unpub.id, is_relevant=True, is_published=False,
        processed_at=datetime.now(timezone.utc),
    )
    db_session.add_all([published, unpublished])
    await db_session.commit()

    token = _make_token(user)
    response = await client.get(
        "/api/v1/alerts?is_published=true",
        cookies={"access_token": token},
    )
    assert response.status_code == 200
    ids = [d["id"] for d in response.json()]
    assert published.id in ids
    assert unpublished.id not in ids


# ---------------------------------------------------------------------------
# Admin review → publish
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_review_publishes_alert(client, db_session):
    """POST 'approved' review on unpublished relevant alert → is_published = True."""
    user = await _create_admin_user(db_session)
    _, raw = await _make_source_and_raw(db_session, url_suffix="appr001")

    alert = ProcessedAlert(
        raw_item_id=raw.id, is_relevant=True, is_published=False,
        processed_at=datetime.now(timezone.utc),
    )
    db_session.add(alert)
    await db_session.commit()

    token = _make_token(user)
    response = await client.post(
        f"/api/v1/alerts/{alert.id}/review",
        json={"review_status": "approved"},
        cookies={"access_token": token},
    )
    assert response.status_code == 200

    await db_session.refresh(alert)
    assert alert.is_published is True


@pytest.mark.asyncio
async def test_approve_review_sets_published_at(client, db_session):
    """Approval sets published_at timestamp."""
    user = await _create_admin_user(db_session)
    _, raw = await _make_source_and_raw(db_session, url_suffix="appr002")

    alert = ProcessedAlert(
        raw_item_id=raw.id, is_relevant=True, is_published=False,
        processed_at=datetime.now(timezone.utc),
    )
    db_session.add(alert)
    await db_session.commit()

    token = _make_token(user)
    await client.post(
        f"/api/v1/alerts/{alert.id}/review",
        json={"review_status": "approved"},
        cookies={"access_token": token},
    )

    await db_session.refresh(alert)
    assert alert.published_at is not None


@pytest.mark.asyncio
async def test_approve_review_sets_published_by_user_id(client, db_session):
    """Approval sets published_by_user_id to the reviewing admin's id."""
    user = await _create_admin_user(db_session)
    _, raw = await _make_source_and_raw(db_session, url_suffix="appr003")

    alert = ProcessedAlert(
        raw_item_id=raw.id, is_relevant=True, is_published=False,
        processed_at=datetime.now(timezone.utc),
    )
    db_session.add(alert)
    await db_session.commit()

    token = _make_token(user)
    await client.post(
        f"/api/v1/alerts/{alert.id}/review",
        json={"review_status": "approved"},
        cookies={"access_token": token},
    )

    await db_session.refresh(alert)
    assert alert.published_by_user_id == user.id


@pytest.mark.asyncio
async def test_false_positive_review_does_not_publish(client, db_session):
    """POST 'false_positive' review does NOT publish the alert."""
    user = await _create_admin_user(db_session)
    _, raw = await _make_source_and_raw(db_session, url_suffix="fp001")

    alert = ProcessedAlert(
        raw_item_id=raw.id, is_relevant=True, is_published=False,
        processed_at=datetime.now(timezone.utc),
    )
    db_session.add(alert)
    await db_session.commit()

    token = _make_token(user)
    await client.post(
        f"/api/v1/alerts/{alert.id}/review",
        json={"review_status": "false_positive"},
        cookies={"access_token": token},
    )

    await db_session.refresh(alert)
    assert alert.is_published is False


@pytest.mark.asyncio
async def test_approve_irrelevant_alert_does_not_publish(client, db_session):
    """Approving an irrelevant (Tier 3) alert does not publish it."""
    user = await _create_admin_user(db_session)
    _, raw = await _make_source_and_raw(db_session, url_suffix="irrel001")

    alert = ProcessedAlert(
        raw_item_id=raw.id, is_relevant=False, is_published=False,
        processed_at=datetime.now(timezone.utc),
    )
    db_session.add(alert)
    await db_session.commit()

    token = _make_token(user)
    await client.post(
        f"/api/v1/alerts/{alert.id}/review",
        json={"review_status": "approved"},
        cookies={"access_token": token},
    )

    await db_session.refresh(alert)
    assert alert.is_published is False


# ---------------------------------------------------------------------------
# Client feed — /api/v1/client/alerts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_client_list_requires_auth(client):
    """GET /api/v1/client/alerts without token → 401."""
    response = await client.get("/api/v1/client/alerts")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_client_list_only_published(client, db_session):
    """Subscriber only sees published alerts in client feed."""
    user = await _create_subscriber_user(db_session)
    _, raw_pub = await _make_source_and_raw(db_session, url_suffix="cl001")
    _, raw_unpub = await _make_source_and_raw(db_session, url_suffix="cl002")

    published = ProcessedAlert(
        raw_item_id=raw_pub.id, is_relevant=True, is_published=True,
        published_at=datetime.now(timezone.utc),
        processed_at=datetime.now(timezone.utc),
    )
    unpublished = ProcessedAlert(
        raw_item_id=raw_unpub.id, is_relevant=True, is_published=False,
        processed_at=datetime.now(timezone.utc),
    )
    db_session.add_all([published, unpublished])
    await db_session.commit()

    token = _make_token(user)
    response = await client.get(
        "/api/v1/client/alerts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    ids = [d["id"] for d in response.json()]
    assert published.id in ids
    assert unpublished.id not in ids


@pytest.mark.asyncio
async def test_client_list_unpublished_absent(client, db_session):
    """Unpublished alert is never returned by the client endpoint."""
    user = await _create_subscriber_user(db_session)
    _, raw = await _make_source_and_raw(db_session, url_suffix="cl003")

    alert = ProcessedAlert(
        raw_item_id=raw.id, is_relevant=True, is_published=False,
        processed_at=datetime.now(timezone.utc),
    )
    db_session.add(alert)
    await db_session.commit()

    token = _make_token(user)
    response = await client.get(
        "/api/v1/client/alerts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    ids = [d["id"] for d in response.json()]
    assert alert.id not in ids


@pytest.mark.asyncio
async def test_client_detail_published(client, db_session):
    """Subscriber can fetch a published alert detail."""
    user = await _create_subscriber_user(db_session)
    _, raw = await _make_source_and_raw(db_session, url_suffix="cl004")

    alert = ProcessedAlert(
        raw_item_id=raw.id,
        risk_level="high",
        is_relevant=True,
        is_published=True,
        published_at=datetime.now(timezone.utc),
        processed_at=datetime.now(timezone.utc),
        summary="Test fraud summary.",
    )
    db_session.add(alert)
    await db_session.commit()

    token = _make_token(user)
    response = await client.get(
        f"/api/v1/client/alerts/{alert.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == alert.id
    assert data["summary"] == "Test fraud summary."
    assert "entities" in data  # subscriber-safe field, not entities_json


@pytest.mark.asyncio
async def test_client_detail_unpublished_returns_404(client, db_session):
    """Subscriber gets 404 when fetching an unpublished alert detail."""
    user = await _create_subscriber_user(db_session)
    _, raw = await _make_source_and_raw(db_session, url_suffix="cl005")

    alert = ProcessedAlert(
        raw_item_id=raw.id, is_relevant=True, is_published=False,
        processed_at=datetime.now(timezone.utc),
    )
    db_session.add(alert)
    await db_session.commit()

    token = _make_token(user)
    response = await client.get(
        f"/api/v1/client/alerts/{alert.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_admin_can_access_client_feed(client, db_session):
    """Admin JWT also works on client endpoints."""
    user = await _create_admin_user(db_session)
    _, raw = await _make_source_and_raw(db_session, url_suffix="cl006")

    alert = ProcessedAlert(
        raw_item_id=raw.id, is_relevant=True, is_published=True,
        published_at=datetime.now(timezone.utc),
        processed_at=datetime.now(timezone.utc),
    )
    db_session.add(alert)
    await db_session.commit()

    token = _make_token(user)
    response = await client.get(
        "/api/v1/client/alerts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert any(d["id"] == alert.id for d in response.json())
