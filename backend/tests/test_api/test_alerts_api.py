"""Tests for app/api/alerts.py REST endpoints."""
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


async def _create_admin_user(db_session) -> User:
    """Create a user with a unique email to avoid UNIQUE constraint conflicts across tests."""
    unique_email = f"admin_{uuid.uuid4().hex[:8]}@test.com"
    user = User(
        email=unique_email,
        password_hash=hash_password("adminpass"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


def _make_token(user: User) -> str:
    """Create a JWT token using the session-patched TEST_JWT_SECRET."""
    return create_access_token({"sub": str(user.id)})


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

    # Create source + raw_item + processed_alert
    source = Source(
        name="Test Source API",
        base_url="https://test.com",
        source_type="rss",
        credibility_score=4,
        adapter_class="RSSAdapter",
    )
    db_session.add(source)
    await db_session.flush()

    raw = RawItem(
        source_id=source.id,
        item_url="https://test.com/article1",
        title="Fraud Alert Article",
        url_hash="testhash_api_001",
    )
    db_session.add(raw)
    await db_session.flush()

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

    response = await client.get(
        "/api/v1/alerts",
        cookies={"access_token": token},
    )
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

    # Create an alert to review
    source = Source(
        name="Review Test Source",
        base_url="https://review.com",
        source_type="rss",
        credibility_score=3,
        adapter_class="RSSAdapter",
    )
    db_session.add(source)
    await db_session.flush()

    raw = RawItem(
        source_id=source.id,
        item_url="https://review.com/article",
        title="Review Test",
        url_hash="review_hash_001",
    )
    db_session.add(raw)
    await db_session.flush()

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
