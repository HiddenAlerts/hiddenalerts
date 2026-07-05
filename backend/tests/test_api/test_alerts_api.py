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
        headers={"Cookie": f"access_token={token}"},
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
        headers={"Cookie": f"access_token={token}"},
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
    response = await client.get("/api/v1/alerts", headers={"Cookie": f"access_token={token}"})
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
            headers={"Cookie": f"access_token={token}"},
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
            headers={"Cookie": f"access_token={token}"},
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
        headers={"Cookie": f"access_token={token}"},
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
        headers={"Cookie": f"access_token={token}"},
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
        headers={"Cookie": f"access_token={token}"},
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
        headers={"Cookie": f"access_token={token}"},
    )
    assert response.status_code == 200

    await db_session.refresh(alert)
    assert alert.is_published is True
    # Slice 7A: approval reconciles V1 manual-admin publication state.
    assert alert.publication_state_source == "manual_admin"
    assert alert.publish_decision == "auto_publish"
    assert alert.published_by_rule is False
    assert alert.publishing_policy_version == "v1.0"


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
        headers={"Cookie": f"access_token={token}"},
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
        headers={"Cookie": f"access_token={token}"},
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
        headers={"Cookie": f"access_token={token}"},
    )

    await db_session.refresh(alert)
    assert alert.is_published is False
    # Slice 7A: false positive now also marks V1 exclusion state.
    assert alert.publish_decision == "exclude"
    assert alert.is_excluded is True
    assert alert.publication_state_source == "manual_admin"


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
        headers={"Cookie": f"access_token={token}"},
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


# ===========================================================================
# Slice 6 — internal V1 publication visibility + risk explanation + filters
# ===========================================================================

_V1_FIELDS = (
    "risk_band", "publish_decision", "publish_decision_reason", "pending_review_reason",
    "is_excluded", "excluded_reason", "is_manual_hold", "published_by_rule",
    "publishing_policy_version", "publication_state_source", "publication_state_updated_at",
)


async def _seed_v1_alert(
    db_session,
    *,
    suffix,
    signal_score_total=22,
    risk_band="critical",
    publish_decision="auto_publish",
    publish_decision_reason="auto_publish_band_and_gates_passed",
    pending_review_reason=None,
    is_published=False,
    published_by_rule=False,
    is_excluded=False,
    excluded_reason=None,
    is_manual_hold=False,
    publication_state_source="auto_policy",
    category="Cybercrime",
    is_relevant=True,
):
    _, raw = await _make_source_and_raw(db_session, url_suffix=suffix)
    now = datetime.now(timezone.utc)
    alert = ProcessedAlert(
        raw_item_id=raw.id,
        primary_category=category,
        risk_level="high",
        signal_score_total=signal_score_total,
        score_source_credibility=5,
        score_financial_impact=5,
        score_victim_scale=4,
        score_cross_source=5,
        score_trend_acceleration=3,
        is_relevant=is_relevant,
        matched_keywords=["fraud"],
        processed_at=now,
        risk_band=risk_band,
        publish_decision=publish_decision,
        publish_decision_reason=publish_decision_reason,
        pending_review_reason=pending_review_reason,
        is_excluded=is_excluded,
        excluded_reason=excluded_reason,
        is_manual_hold=is_manual_hold,
        published_by_rule=published_by_rule,
        publishing_policy_version="v1.0",
        publication_state_source=publication_state_source,
        publication_state_updated_at=now,
        is_published=is_published,
        published_at=now if is_published else None,
    )
    db_session.add(alert)
    await db_session.commit()
    await db_session.refresh(alert)
    return alert


def _auth(token):
    return {"Cookie": f"access_token={token}"}


@pytest.mark.asyncio
async def test_list_includes_v1_publication_fields(client, db_session):
    user = await _create_admin_user(db_session)
    alert = await _seed_v1_alert(db_session, suffix="v1list", is_published=True, published_by_rule=True)
    token = _make_token(user)

    resp = await client.get("/api/v1/alerts", headers=_auth(token))
    assert resp.status_code == 200
    row = next(d for d in resp.json() if d["id"] == alert.id)
    for f in _V1_FIELDS:
        assert f in row, f"missing V1 field in list item: {f}"
    assert row["publish_decision"] == "auto_publish"
    assert row["published_by_rule"] is True
    assert row["risk_band"] == "critical"
    assert row["publication_state_source"] == "auto_policy"
    assert row["publish_decision_reason"] == "auto_publish_band_and_gates_passed"


@pytest.mark.asyncio
async def test_detail_includes_v1_fields_and_risk_explanation(client, db_session):
    user = await _create_admin_user(db_session)
    alert = await _seed_v1_alert(db_session, suffix="v1detail", is_published=True, published_by_rule=True)
    token = _make_token(user)

    resp = await client.get(f"/api/v1/alerts/{alert.id}", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    for f in _V1_FIELDS:
        assert f in body
    assert "published_by_user_id" in body
    re = body["risk_explanation"]
    assert re is not None
    assert re["score_total"] == 22            # raw internal 5–25
    assert re["score_100"] == 88              # normalized
    assert re["risk_band"] == "critical"
    assert re["publication_decision"] == "auto_publish"


@pytest.mark.asyncio
async def test_risk_explanation_factors_and_reason(client, db_session):
    user = await _create_admin_user(db_session)
    alert = await _seed_v1_alert(
        db_session, suffix="v1factors", is_published=False,
        publish_decision="review", publish_decision_reason="source_credibility_below_threshold",
        pending_review_reason="blocked_by_credibility", risk_band="high",
    )
    token = _make_token(user)

    resp = await client.get(f"/api/v1/alerts/{alert.id}", headers=_auth(token))
    factors = resp.json()["risk_explanation"]["factors"]
    assert set(factors) == {
        "source_credibility", "financial_impact", "victim_scale",
        "cross_source", "trend_acceleration",
    }
    assert factors["cross_source"] == 5
    re = resp.json()["risk_explanation"]
    assert re["publication_reason"] == "source_credibility_below_threshold"
    assert re["pending_review_reason"] == "blocked_by_credibility"
    assert re["source_credibility"] == 4  # from _make_source_and_raw


@pytest.mark.asyncio
async def test_risk_explanation_band_fallback_not_persisted(client, db_session):
    """risk_band is None on the row but the explanation derives it; DB stays NULL."""
    user = await _create_admin_user(db_session)
    alert = await _seed_v1_alert(
        db_session, suffix="v1fallback", signal_score_total=22, risk_band=None,
        publish_decision="review", publish_decision_reason="x", pending_review_reason=None,
    )
    token = _make_token(user)

    resp = await client.get(f"/api/v1/alerts/{alert.id}", headers=_auth(token))
    assert resp.json()["risk_explanation"]["risk_band"] == "critical"  # computed fallback

    # The DB column was NOT written by the read path.
    from sqlalchemy import select as _select
    row = (
        await db_session.execute(
            _select(ProcessedAlert).where(ProcessedAlert.id == alert.id)
        )
    ).scalar_one()
    await db_session.refresh(row)
    assert row.risk_band is None


@pytest.mark.asyncio
async def test_filter_publish_decision(client, db_session):
    user = await _create_admin_user(db_session)
    rev = await _seed_v1_alert(
        db_session, suffix="fpd", publish_decision="review",
        pending_review_reason="blocked_by_score", risk_band="medium", signal_score_total=16,
    )
    token = _make_token(user)
    resp = await client.get("/api/v1/alerts?publish_decision=review", headers=_auth(token))
    assert resp.status_code == 200
    rows = resp.json()
    assert all(r["publish_decision"] == "review" for r in rows)
    assert any(r["id"] == rev.id for r in rows)


@pytest.mark.asyncio
async def test_filter_pending_review_reason(client, db_session):
    user = await _create_admin_user(db_session)
    a = await _seed_v1_alert(
        db_session, suffix="fprr", publish_decision="review",
        pending_review_reason="blocked_by_credibility", risk_band="high",
    )
    token = _make_token(user)
    resp = await client.get(
        "/api/v1/alerts?pending_review_reason=blocked_by_credibility", headers=_auth(token)
    )
    assert resp.status_code == 200
    rows = resp.json()
    assert all(r["pending_review_reason"] == "blocked_by_credibility" for r in rows)
    assert any(r["id"] == a.id for r in rows)


@pytest.mark.asyncio
async def test_filter_risk_band(client, db_session):
    user = await _create_admin_user(db_session)
    a = await _seed_v1_alert(
        db_session, suffix="frb", publish_decision="review",
        pending_review_reason="blocked_by_source_rule", risk_band="high",
    )
    token = _make_token(user)
    resp = await client.get("/api/v1/alerts?risk_band=high", headers=_auth(token))
    assert resp.status_code == 200
    rows = resp.json()
    assert all(r["risk_band"] == "high" for r in rows)
    assert any(r["id"] == a.id for r in rows)


@pytest.mark.asyncio
async def test_filter_is_excluded(client, db_session):
    user = await _create_admin_user(db_session)
    a = await _seed_v1_alert(
        db_session, suffix="fexc", publish_decision="exclude",
        publish_decision_reason="excluded_low_score", pending_review_reason="excluded_low_score",
        risk_band="below_60", signal_score_total=8, is_excluded=True,
        excluded_reason="excluded_low_score",
    )
    token = _make_token(user)
    resp = await client.get("/api/v1/alerts?is_excluded=true", headers=_auth(token))
    assert resp.status_code == 200
    rows = resp.json()
    assert all(r["is_excluded"] is True for r in rows)
    assert any(r["id"] == a.id for r in rows)


@pytest.mark.asyncio
async def test_filter_is_manual_hold(client, db_session):
    user = await _create_admin_user(db_session)
    a = await _seed_v1_alert(
        db_session, suffix="fhold", publish_decision="hold",
        publish_decision_reason="event_grouping_failed", pending_review_reason="manual_hold",
        risk_band="critical", is_manual_hold=True,
    )
    token = _make_token(user)
    resp = await client.get("/api/v1/alerts?is_manual_hold=true", headers=_auth(token))
    assert resp.status_code == 200
    rows = resp.json()
    assert all(r["is_manual_hold"] is True for r in rows)
    assert any(r["id"] == a.id for r in rows)


@pytest.mark.asyncio
async def test_filter_published_by_rule(client, db_session):
    user = await _create_admin_user(db_session)
    a = await _seed_v1_alert(db_session, suffix="fpbr", is_published=True, published_by_rule=True)
    token = _make_token(user)
    resp = await client.get("/api/v1/alerts?published_by_rule=true", headers=_auth(token))
    assert resp.status_code == 200
    rows = resp.json()
    assert all(r["published_by_rule"] is True for r in rows)
    assert any(r["id"] == a.id for r in rows)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "qs",
    [
        "publish_decision=bogus",
        "risk_band=nope",
        "pending_review_reason=not_a_reason",
        "publication_state_source=bogus",
    ],
)
async def test_invalid_enum_filter_returns_422(client, db_session, qs):
    user = await _create_admin_user(db_session)
    token = _make_token(user)
    resp = await client.get(f"/api/v1/alerts?{qs}", headers=_auth(token))
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_existing_category_filter_still_works(client, db_session):
    user = await _create_admin_user(db_session)
    a = await _seed_v1_alert(db_session, suffix="catf", category="Money Laundering")
    token = _make_token(user)
    resp = await client.get("/api/v1/alerts?category=Money Laundering", headers=_auth(token))
    assert resp.status_code == 200
    rows = resp.json()
    assert all(r["primary_category"] == "Money Laundering" for r in rows)
    assert any(r["id"] == a.id for r in rows)


@pytest.mark.asyncio
async def test_detail_requires_auth(client, db_session):
    alert = await _seed_v1_alert(db_session, suffix="noauth")
    resp = await client.get(f"/api/v1/alerts/{alert.id}")
    assert resp.status_code == 401


# ===========================================================================
# Slice 7A — manual review V1 reconciliation
# ===========================================================================


async def _seed_review_alert(
    db_session, *, suffix, is_relevant=True, is_published=False, signal_score_total=22,
    **v1,
):
    """Seed a ProcessedAlert with a source/raw for the review endpoint tests."""
    _, raw = await _make_source_and_raw(db_session, url_suffix=suffix)
    now = datetime.now(timezone.utc)
    alert = ProcessedAlert(
        raw_item_id=raw.id,
        primary_category="Cybercrime",
        risk_level="high",
        signal_score_total=signal_score_total,
        score_source_credibility=5, score_financial_impact=5, score_victim_scale=4,
        score_cross_source=5, score_trend_acceleration=3,
        is_relevant=is_relevant,
        matched_keywords=["fraud"],
        processed_at=now,
        is_published=is_published,
        published_at=now if is_published else None,
        **v1,
    )
    db_session.add(alert)
    await db_session.commit()
    await db_session.refresh(alert)
    return alert


async def _review(client, token, alert_id, status_value, **body):
    return await client.post(
        f"/api/v1/alerts/{alert_id}/review",
        json={"review_status": status_value, **body},
        headers={"Cookie": f"access_token={token}"},
    )


@pytest.mark.asyncio
async def test_7a_approve_sets_full_manual_admin_state(client, db_session):
    user = await _create_admin_user(db_session)
    alert = await _seed_review_alert(db_session, suffix="7a_appr", signal_score_total=22)
    token = _make_token(user)

    resp = await _review(client, token, alert.id, "approved")
    assert resp.status_code == 200
    await db_session.refresh(alert)

    assert alert.is_published is True
    assert alert.published_at is not None
    assert alert.published_by_user_id == user.id
    assert alert.published_by_rule is False
    assert alert.publish_decision == "auto_publish"
    assert alert.publish_decision_reason == "manual_admin_approved"
    assert alert.pending_review_reason is None
    assert alert.publication_state_source == "manual_admin"
    assert alert.publishing_policy_version == "v1.0"
    assert alert.risk_band == "critical"  # score 22 → critical
    assert alert.is_excluded is False
    assert alert.is_manual_hold is False


@pytest.mark.asyncio
async def test_7a_approve_is_idempotent(client, db_session):
    user = await _create_admin_user(db_session)
    other_user = await _create_admin_user(db_session)
    earlier = datetime(2026, 1, 1, tzinfo=timezone.utc)
    # Already published by a DIFFERENT user, with stale/empty V1 metadata.
    alert = await _seed_review_alert(
        db_session, suffix="7a_idem", is_published=True,
    )
    alert.published_at = earlier
    alert.published_by_user_id = other_user.id
    await db_session.commit()

    token = _make_token(user)
    resp = await _review(client, token, alert.id, "approved")
    assert resp.status_code == 200
    await db_session.refresh(alert)

    # Existing published_at / published_by_user_id preserved (SQLite stores naive
    # datetimes, so compare tz-agnostically — the value itself is unchanged).
    assert alert.published_at.replace(tzinfo=None) == earlier.replace(tzinfo=None)
    assert alert.published_by_user_id == other_user.id
    # But V1 metadata is now reconciled.
    assert alert.publication_state_source == "manual_admin"
    assert alert.publish_decision == "auto_publish"
    assert alert.publish_decision_reason == "manual_admin_approved"


@pytest.mark.asyncio
async def test_7a_approve_irrelevant_does_not_publish_or_set_auto(client, db_session):
    user = await _create_admin_user(db_session)
    alert = await _seed_review_alert(db_session, suffix="7a_irrel", is_relevant=False)
    token = _make_token(user)

    resp = await _review(client, token, alert.id, "approved")
    assert resp.status_code == 200
    await db_session.refresh(alert)
    assert alert.is_published is False
    assert alert.publish_decision != "auto_publish"


@pytest.mark.asyncio
async def test_7a_false_positive_marks_exclusion_state(client, db_session):
    user = await _create_admin_user(db_session)
    alert = await _seed_review_alert(db_session, suffix="7a_fp", signal_score_total=16)
    token = _make_token(user)

    resp = await _review(client, token, alert.id, "false_positive")
    assert resp.status_code == 200
    await db_session.refresh(alert)

    assert alert.is_published is False
    assert alert.publish_decision == "exclude"
    assert alert.publish_decision_reason == "manual_false_positive"
    assert alert.pending_review_reason == "manual_rejected"
    assert alert.is_excluded is True
    assert alert.excluded_reason == "manual_false_positive"
    assert alert.publication_state_source == "manual_admin"
    assert alert.is_manual_hold is False
    assert alert.risk_band == "medium"  # score 16 → medium


@pytest.mark.asyncio
async def test_7a_false_positive_on_published_unpublishes(client, db_session):
    user = await _create_admin_user(db_session)
    publisher = await _create_admin_user(db_session)
    alert = await _seed_review_alert(
        db_session, suffix="7a_fppub", is_published=True,
        publish_decision="auto_publish", published_by_rule=True,
        publication_state_source="auto_policy",
        published_by_user_id=publisher.id,  # existing publisher to prove it's cleared
    )
    token = _make_token(user)

    resp = await _review(client, token, alert.id, "false_positive")
    assert resp.status_code == 200
    await db_session.refresh(alert)
    assert alert.is_published is False
    assert alert.published_at is None
    assert alert.published_by_user_id is None  # stale publisher cleared

    # Not returned by the public feed/detail.
    pub_list = await client.get("/api/alerts")
    assert all(a["id"] != alert.id for a in pub_list.json()["alerts"])
    pub_detail = await client.get(f"/api/alerts/{alert.id}")
    assert pub_detail.status_code == 404


@pytest.mark.asyncio
async def test_7a_edited_does_not_overwrite_v1_state(client, db_session):
    user = await _create_admin_user(db_session)
    alert = await _seed_review_alert(
        db_session, suffix="7a_edit", is_published=True,
        publish_decision="auto_publish", publish_decision_reason="auto_publish_band_and_gates_passed",
        publication_state_source="auto_policy", published_by_rule=True, risk_band="high",
    )
    token = _make_token(user)

    resp = await _review(
        client, token, alert.id, "edited",
        edited_summary="New summary", adjusted_risk_level="Low",
    )
    assert resp.status_code == 200
    await db_session.refresh(alert)

    # Content updated…
    assert alert.summary == "New summary"
    assert alert.risk_level == "low"
    # …but V1 publication state untouched.
    assert alert.publish_decision == "auto_publish"
    assert alert.publication_state_source == "auto_policy"
    assert alert.published_by_rule is True
    assert alert.risk_band == "high"
    assert alert.is_published is True


@pytest.mark.asyncio
async def test_7a_detail_exposes_reconciled_state(client, db_session):
    user = await _create_admin_user(db_session)
    alert = await _seed_review_alert(db_session, suffix="7a_detail")
    token = _make_token(user)
    await _review(client, token, alert.id, "approved")

    resp = await client.get(
        f"/api/v1/alerts/{alert.id}", headers={"Cookie": f"access_token={token}"}
    )
    body = resp.json()
    assert body["publication_state_source"] == "manual_admin"
    assert body["risk_explanation"]["publication_decision"] == "auto_publish"
    assert body["risk_explanation"]["publication_reason"] == "manual_admin_approved"


@pytest.mark.asyncio
async def test_7a_list_filter_manual_admin(client, db_session):
    user = await _create_admin_user(db_session)
    alert = await _seed_review_alert(db_session, suffix="7a_filter")
    token = _make_token(user)
    await _review(client, token, alert.id, "approved")

    resp = await client.get(
        "/api/v1/alerts?publication_state_source=manual_admin",
        headers={"Cookie": f"access_token={token}"},
    )
    assert resp.status_code == 200
    rows = resp.json()
    assert all(r["publication_state_source"] == "manual_admin" for r in rows)
    target = next(r for r in rows if r["id"] == alert.id)
    # Manual approvals are identifiable: auto_publish decision but NOT by rule.
    assert target["publish_decision"] == "auto_publish"
    assert target["published_by_rule"] is False


# ---------------------------------------------------------------------------
# OPEN-6: subscriber-safe risk_band (Critical badge) + curated risk_explanation
# on the /client/* surface, with no internal V1 field leakage.
# ---------------------------------------------------------------------------

_CLIENT_FORBIDDEN = {
    "publish_decision", "publish_decision_reason", "pending_review_reason",
    "publication_state_source", "publication_state_updated_at", "is_excluded",
    "excluded_reason", "is_manual_hold", "published_by_rule",
    "publishing_policy_version", "published_by_user_id",
}


async def _seed_client_alert(db_session, *, suffix, score=22, category="Consumer Scam"):
    _, raw = await _make_source_and_raw(db_session, url_suffix=suffix)
    alert = ProcessedAlert(
        raw_item_id=raw.id, is_relevant=True, is_published=True,
        primary_category=category, victim_scale_raw="nationwide",
        matched_keywords=["payment fraud"], summary="A payment fraud scam.",
        signal_score_total=score,
        score_source_credibility=5, score_financial_impact=5, score_victim_scale=4,
        score_cross_source=5, score_trend_acceleration=3,
        published_at=datetime.now(timezone.utc), processed_at=datetime.now(timezone.utc),
    )
    db_session.add(alert)
    await db_session.commit()
    return alert


@pytest.mark.asyncio
async def test_client_open6_risk_band_and_explanation(client, db_session):
    user = await _create_subscriber_user(db_session)
    alert = await _seed_client_alert(db_session, suffix="o6a", score=22)  # 88/100 → critical
    hdr = {"Authorization": f"Bearer {_make_token(user)}"}

    lst = await client.get("/api/v1/client/alerts", headers=hdr)
    assert lst.status_code == 200
    item = next(a for a in lst.json() if a["id"] == alert.id)
    assert item["risk_band"] == "critical"  # Critical badge data on the list

    det = await client.get(f"/api/v1/client/alerts/{alert.id}", headers=hdr)
    assert det.status_code == 200
    body = det.json()
    assert body["risk_band"] == "critical"
    re_ = body["risk_explanation"]
    assert re_["risk_band"] == "critical" and re_["score"] == 88
    assert re_["factor_labels"]["source_credibility"] == "High"
    assert "Consumers" in re_["primary_exposure"] and "Payment Systems" in re_["primary_exposure"]
    assert "Multiple independent sources" in re_["reason_for_score"]
    assert re_["confidence"] in ("High", "Medium", "Low")


@pytest.mark.asyncio
async def test_client_open6_no_internal_field_leak(client, db_session):
    user = await _create_subscriber_user(db_session)
    alert = await _seed_client_alert(db_session, suffix="o6b")
    hdr = {"Authorization": f"Bearer {_make_token(user)}"}

    item = (await client.get("/api/v1/client/alerts", headers=hdr)).json()[0]
    assert _CLIENT_FORBIDDEN.isdisjoint(item.keys())
    body = (await client.get(f"/api/v1/client/alerts/{alert.id}", headers=hdr)).json()
    assert _CLIENT_FORBIDDEN.isdisjoint(body.keys())
    # The curated explanation also carries no internal fields.
    assert _CLIENT_FORBIDDEN.isdisjoint(body["risk_explanation"].keys())


@pytest.mark.asyncio
async def test_client_risk_band_filter(client, db_session):
    user = await _create_subscriber_user(db_session)
    crit = await _seed_client_alert(db_session, suffix="o6c1", score=22)   # critical
    med = await _seed_client_alert(db_session, suffix="o6c2", score=16)    # medium (64/100)
    hdr = {"Authorization": f"Bearer {_make_token(user)}"}

    crit_only = await client.get("/api/v1/client/alerts?risk_band=critical", headers=hdr)
    ids = {a["id"] for a in crit_only.json()}
    assert crit.id in ids and med.id not in ids

    bad = await client.get("/api/v1/client/alerts?risk_band=bogus", headers=hdr)
    assert bad.status_code == 422
