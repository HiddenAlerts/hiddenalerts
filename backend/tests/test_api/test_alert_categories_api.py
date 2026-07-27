"""Tests for the canonical alert category metadata endpoints.

Covers both scopes (subscriber = published only, admin = all processed alerts),
the canonical list guarantees, and the invariants that keep the AI classifier
and the V1 publishing policy tied to the same vocabulary.
"""
import uuid

import pytest
from httpx import AsyncClient

from app.auth import create_access_token, hash_password
from app.domain.alert_categories import (
    ALERT_CATEGORIES,
    OTHER_CATEGORY,
    PUBLISHABLE_ALERT_CATEGORIES,
)
from app.main import app
from app.models.user import User
from tests.test_api.test_public_alerts import (
    _seed_alert,
    _seed_raw_item,
    _seed_source,
    clean_db,  # noqa: F401 — fixture
)
from tests.test_api.test_subscriber_api import _claims, _patch_validator
from tests.test_api.test_subscriber_content import _seed_profile_with_subscription

SUBSCRIBER_URL = "/api/v1/subscriber/alerts/categories"
ADMIN_URL = "/api/v1/admin/alerts/categories"

EXPECTED_ORDER = [
    "Investment Fraud",
    "Cybercrime",
    "Consumer Scam",
    "Money Laundering",
    "Cryptocurrency Fraud",
    "Other",
]

_AUTH = {"Authorization": "Bearer ignored"}


async def _make_admin(db_session, role: str = "admin") -> dict:
    user = User(
        email=f"{role}_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password("pw"),
        is_active=True,
        role=role,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"}


async def _active_subscriber(db_session) -> dict:
    sub_id = f"cat-{uuid.uuid4()}"
    await _seed_profile_with_subscription(db_session, sub_id=sub_id, status="active")
    return _claims(sub=sub_id)


async def _seed(db_session, *, category, is_published, **kwargs):
    source = await _seed_source(db_session, name=f"Src {uuid.uuid4()}")
    raw = await _seed_raw_item(db_session, source, url=f"https://x/{uuid.uuid4()}")
    return await _seed_alert(
        db_session, raw, is_published=is_published, category=category, **kwargs
    )


def _counts(payload) -> dict:
    return {c["value"]: c["count"] for c in payload["categories"]}


# ---------------------------------------------------------------------------
# Canonical list guarantees
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscriber_returns_all_six_in_canonical_order(
    client, db_session, clean_db  # noqa: F811
):
    claims = await _active_subscriber(db_session)
    with _patch_validator(claims):
        resp = await client.get(SUBSCRIBER_URL, headers=_AUTH)
    assert resp.status_code == 200
    assert [c["value"] for c in resp.json()["categories"]] == EXPECTED_ORDER


@pytest.mark.asyncio
async def test_admin_returns_all_six_in_canonical_order(
    client, db_session, clean_db  # noqa: F811
):
    headers = await _make_admin(db_session)
    resp = await client.get(ADMIN_URL, headers=headers)
    assert resp.status_code == 200
    assert [c["value"] for c in resp.json()["categories"]] == EXPECTED_ORDER


@pytest.mark.asyncio
async def test_zero_count_categories_are_still_returned(
    client, db_session, clean_db  # noqa: F811
):
    """Only one category has data; the other five must still appear with count 0."""
    await _seed(db_session, category="Cybercrime", is_published=True)
    headers = await _make_admin(db_session)

    body = (await client.get(ADMIN_URL, headers=headers)).json()

    counts = _counts(body)
    assert len(counts) == 6
    assert counts["Cybercrime"] == 1
    assert all(counts[c] == 0 for c in EXPECTED_ORDER if c != "Cybercrime")


@pytest.mark.asyncio
async def test_label_equals_value(client, db_session, clean_db):  # noqa: F811
    headers = await _make_admin(db_session)
    body = (await client.get(ADMIN_URL, headers=headers)).json()
    assert all(c["label"] == c["value"] for c in body["categories"])


@pytest.mark.asyncio
async def test_fraud_intelligence_is_not_an_alert_category(
    client, db_session, clean_db  # noqa: F811
):
    """`Fraud Intelligence` belongs to the brief module and must never appear."""
    headers = await _make_admin(db_session)
    body = (await client.get(ADMIN_URL, headers=headers)).json()
    assert "Fraud Intelligence" not in [c["value"] for c in body["categories"]]


# ---------------------------------------------------------------------------
# Counts — subscriber scope
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscriber_counts_published_only(
    client, db_session, clean_db  # noqa: F811
):
    await _seed(db_session, category="Consumer Scam", is_published=True)
    await _seed(db_session, category="Consumer Scam", is_published=False)
    await _seed(db_session, category="Money Laundering", is_published=False)
    claims = await _active_subscriber(db_session)

    with _patch_validator(claims):
        body = (await client.get(SUBSCRIBER_URL, headers=_AUTH)).json()

    counts = _counts(body)
    assert counts["Consumer Scam"] == 1
    assert counts["Money Laundering"] == 0
    assert body["total"] == 1


@pytest.mark.asyncio
async def test_subscriber_counts_span_all_published_risk_bands(
    client, db_session, clean_db  # noqa: F811
):
    """The subscriber feed is gated on publication alone, not on risk band.

    Locks in current production behaviour: a published Medium/Low alert is
    retrievable via ``GET /alerts``, so it must be counted here too.
    """
    await _seed(db_session, category="Cybercrime", is_published=True, signal_score=23)
    await _seed(db_session, category="Cybercrime", is_published=True, signal_score=18)
    await _seed(db_session, category="Cybercrime", is_published=True, signal_score=16)
    await _seed(db_session, category="Cybercrime", is_published=True, signal_score=8)
    claims = await _active_subscriber(db_session)

    with _patch_validator(claims):
        body = (await client.get(SUBSCRIBER_URL, headers=_AUTH)).json()

    assert _counts(body)["Cybercrime"] == 4


@pytest.mark.asyncio
async def test_subscriber_counts_match_the_alerts_feed(
    client, db_session, clean_db  # noqa: F811
):
    """Every count must equal what ``?category=`` actually returns."""
    await _seed(db_session, category="Investment Fraud", is_published=True)
    await _seed(db_session, category="Investment Fraud", is_published=True)
    await _seed(db_session, category="Cybercrime", is_published=True)
    await _seed(db_session, category="Cybercrime", is_published=False)
    claims = await _active_subscriber(db_session)

    with _patch_validator(claims):
        counts = _counts((await client.get(SUBSCRIBER_URL, headers=_AUTH)).json())
        for category in ALERT_CATEGORIES:
            feed = await client.get(
                f"/api/v1/subscriber/alerts?category={category}&limit=500",
                headers=_AUTH,
            )
            assert feed.status_code == 200
            assert len(feed.json()["alerts"]) == counts[category], category


@pytest.mark.asyncio
async def test_subscriber_counts_match_stats_breakdown(
    client, db_session, clean_db  # noqa: F811
):
    """Agrees with the existing stats endpoint on every non-zero category."""
    await _seed(db_session, category="Money Laundering", is_published=True)
    await _seed(db_session, category="Other", is_published=True)
    claims = await _active_subscriber(db_session)

    with _patch_validator(claims):
        counts = _counts((await client.get(SUBSCRIBER_URL, headers=_AUTH)).json())
        stats = (
            await client.get("/api/v1/subscriber/alerts/stats", headers=_AUTH)
        ).json()

    for row in stats["category_breakdown"]:
        assert counts[row["category"]] == row["count"], row["category"]


# ---------------------------------------------------------------------------
# Counts — admin scope
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_counts_include_unpublished(
    client, db_session, clean_db  # noqa: F811
):
    await _seed(db_session, category="Cryptocurrency Fraud", is_published=True)
    await _seed(db_session, category="Cryptocurrency Fraud", is_published=False)
    await _seed(db_session, category="Other", is_published=False)
    headers = await _make_admin(db_session)

    body = (await client.get(ADMIN_URL, headers=headers)).json()

    counts = _counts(body)
    assert counts["Cryptocurrency Fraud"] == 2
    assert counts["Other"] == 1
    assert body["total"] == 3


@pytest.mark.asyncio
async def test_admin_and_subscriber_scopes_differ(
    client, db_session, clean_db  # noqa: F811
):
    await _seed(db_session, category="Cybercrime", is_published=True)
    await _seed(db_session, category="Cybercrime", is_published=False)
    headers = await _make_admin(db_session)
    claims = await _active_subscriber(db_session)

    admin_body = (await client.get(ADMIN_URL, headers=headers)).json()
    with _patch_validator(claims):
        sub_body = (await client.get(SUBSCRIBER_URL, headers=_AUTH)).json()

    assert _counts(admin_body)["Cybercrime"] == 2
    assert _counts(sub_body)["Cybercrime"] == 1


# ---------------------------------------------------------------------------
# Non-canonical stored values
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "stored",
    [None, "", "   ", " Cybercrime", "cybercrime", "Healthcare Fraud", "AML"],
    ids=["null", "empty", "whitespace", "padded", "lowercase", "unknown", "legacy"],
)
@pytest.mark.asyncio
async def test_non_canonical_values_are_never_counted_or_exposed(
    client, db_session, clean_db, stored  # noqa: F811
):
    await _seed(db_session, category=stored, is_published=True)
    headers = await _make_admin(db_session)

    body = (await client.get(ADMIN_URL, headers=headers)).json()

    assert [c["value"] for c in body["categories"]] == EXPECTED_ORDER
    assert body["total"] == 0
    assert all(c["count"] == 0 for c in body["categories"])


@pytest.mark.asyncio
async def test_total_equals_sum_of_returned_counts(
    client, db_session, clean_db  # noqa: F811
):
    await _seed(db_session, category="Cybercrime", is_published=True)
    await _seed(db_session, category="Other", is_published=True)
    await _seed(db_session, category="Investment Fraud", is_published=False)
    await _seed(db_session, category=None, is_published=True)
    headers = await _make_admin(db_session)

    body = (await client.get(ADMIN_URL, headers=headers)).json()

    assert body["total"] == sum(c["count"] for c in body["categories"])
    assert body["total"] == 3


@pytest.mark.asyncio
async def test_counts_are_non_negative_on_an_empty_database(
    client, db_session, clean_db  # noqa: F811
):
    headers = await _make_admin(db_session)
    body = (await client.get(ADMIN_URL, headers=headers)).json()
    assert body["total"] == 0
    assert all(c["count"] == 0 for c in body["categories"])


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscriber_endpoint_requires_a_token(client: AsyncClient):
    assert (await client.get(SUBSCRIBER_URL)).status_code == 401


@pytest.mark.asyncio
async def test_subscriber_endpoint_rejects_user_without_subscription(
    client: AsyncClient,
):
    with _patch_validator(_claims(sub=f"cat-nosub-{uuid.uuid4()}")):
        resp = await client.get(SUBSCRIBER_URL, headers=_AUTH)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_subscriber_endpoint_rejects_canceled_subscription(client, db_session):
    sub_id = f"cat-canceled-{uuid.uuid4()}"
    await _seed_profile_with_subscription(db_session, sub_id=sub_id, status="canceled")
    with _patch_validator(_claims(sub=sub_id)):
        resp = await client.get(SUBSCRIBER_URL, headers=_AUTH)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_active_subscriber_receives_200(client, db_session):
    claims = await _active_subscriber(db_session)
    with _patch_validator(claims):
        resp = await client.get(SUBSCRIBER_URL, headers=_AUTH)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_admin_endpoint_requires_a_token(client: AsyncClient):
    assert (await client.get(ADMIN_URL)).status_code == 401


@pytest.mark.asyncio
async def test_admin_endpoint_rejects_invalid_token(client: AsyncClient):
    resp = await client.get(ADMIN_URL, headers={"Authorization": "Bearer nope"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_endpoint_rejects_subscriber_role(client, db_session):
    headers = await _make_admin(db_session, role="subscriber")
    assert (await client.get(ADMIN_URL, headers=headers)).status_code == 403


@pytest.mark.asyncio
async def test_admin_endpoint_rejects_deactivated_admin(client, db_session):
    user = User(
        email=f"inactive_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password("pw"),
        is_active=False,
        role="admin",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    headers = {"Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"}
    assert (await client.get(ADMIN_URL, headers=headers)).status_code == 401


@pytest.mark.asyncio
async def test_admin_receives_200(client, db_session):
    headers = await _make_admin(db_session)
    assert (await client.get(ADMIN_URL, headers=headers)).status_code == 200


@pytest.mark.asyncio
async def test_subscriber_endpoint_does_not_leak_data_without_auth(client: AsyncClient):
    resp = await client.get(SUBSCRIBER_URL)
    assert resp.status_code == 401
    assert "categories" not in resp.text


# ---------------------------------------------------------------------------
# Route resolution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_categories_is_not_parsed_as_an_alert_id(client, db_session):
    """`/alerts/categories` must not fall through to `/alerts/{alert_id}` (422)."""
    claims = await _active_subscriber(db_session)
    with _patch_validator(claims):
        resp = await client.get(SUBSCRIBER_URL, headers=_AUTH)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_numeric_alert_detail_route_still_resolves(client, db_session):
    """The dynamic route keeps working alongside the new static one."""
    claims = await _active_subscriber(db_session)
    with _patch_validator(claims):
        resp = await client.get("/api/v1/subscriber/alerts/999999", headers=_AUTH)
    assert resp.status_code == 404


def test_openapi_exposes_both_category_paths():
    paths = app.openapi()["paths"]
    assert SUBSCRIBER_URL in paths and "get" in paths[SUBSCRIBER_URL]
    assert ADMIN_URL in paths and "get" in paths[ADMIN_URL]


def test_openapi_exposes_the_category_enum_and_count_floor():
    schema = app.openapi()["components"]["schemas"]["AlertCategoryRead"]
    assert schema["properties"]["value"]["enum"] == EXPECTED_ORDER
    assert schema["properties"]["count"]["minimum"] == 0
    response = app.openapi()["components"]["schemas"]["AlertCategoriesResponse"]
    assert response["properties"]["total"]["minimum"] == 0


def test_response_json_shape_is_unchanged():
    schema = app.openapi()["components"]["schemas"]["AlertCategoryRead"]
    assert sorted(schema["properties"]) == ["count", "label", "value"]
    assert sorted(schema["required"]) == ["count", "label", "value"]


def test_negative_counts_fail_schema_validation():
    from pydantic import ValidationError

    from app.schemas.alert_category import AlertCategoriesResponse, AlertCategoryRead

    with pytest.raises(ValidationError):
        AlertCategoryRead(value="Cybercrime", label="Cybercrime", count=-1)

    with pytest.raises(ValidationError):
        AlertCategoriesResponse(categories=[], total=-1)


def test_value_must_be_a_canonical_category():
    from pydantic import ValidationError

    from app.schemas.alert_category import AlertCategoryRead

    with pytest.raises(ValidationError):
        AlertCategoryRead(value="Healthcare Fraud", label="Healthcare Fraud", count=0)


def test_existing_alert_paths_are_unchanged():
    paths = app.openapi()["paths"]
    for path in (
        "/api/v1/subscriber/alerts",
        "/api/v1/subscriber/alerts/{alert_id}",
        "/api/v1/subscriber/alerts/stats",
        "/api/v1/subscriber/alerts/top",
        "/api/v1/alerts",
    ):
        assert path in paths, path


# ---------------------------------------------------------------------------
# Canonical vocabulary invariants
# ---------------------------------------------------------------------------


def test_canonical_tuple_matches_expected_values_and_order():
    assert list(ALERT_CATEGORIES) == EXPECTED_ORDER


def test_literal_and_ordered_tuple_stay_in_sync():
    """The type and the runtime sequence are written out separately on purpose;
    changing one without the other must fail here."""
    from typing import get_args

    from app.domain.alert_categories import AlertCategory

    assert tuple(get_args(AlertCategory)) == ALERT_CATEGORIES


def test_ai_structured_output_allows_exactly_the_canonical_categories():
    from typing import get_args

    from app.pipeline.ai_processor import AIArticleAnalysis, FRAUD_CATEGORIES

    assert list(get_args(FRAUD_CATEGORIES)) == EXPECTED_ORDER
    schema = AIArticleAnalysis.model_json_schema()
    assert schema["properties"]["primary_category"]["enum"] == EXPECTED_ORDER


def test_v1_publishable_categories_are_the_five_approved_values():
    from app.pipeline.publishing.publishing_policy import DEFAULT_V1_POLICY

    assert PUBLISHABLE_ALERT_CATEGORIES == frozenset(
        {
            "Investment Fraud",
            "Cybercrime",
            "Consumer Scam",
            "Money Laundering",
            "Cryptocurrency Fraud",
        }
    )
    assert OTHER_CATEGORY not in PUBLISHABLE_ALERT_CATEGORIES
    assert DEFAULT_V1_POLICY.approved_categories == PUBLISHABLE_ALERT_CATEGORIES
    assert DEFAULT_V1_POLICY.manual_review_categories == frozenset({OTHER_CATEGORY})


def test_publish_allowlist_is_not_derived_from_the_taxonomy():
    """A category added to the taxonomy must not become auto-publishable on its own.

    Simulates a seventh canonical category and asserts the allowlist does not
    grow with it, and that such a category routes to review.
    """
    from app.pipeline.publishing.constants import (
        PendingReviewReason,
        PublishDecisionValue,
    )
    from app.pipeline.publishing.publishing_policy import (
        evaluate_basic_publish_decision,
    )

    hypothetical = "Healthcare Fraud"
    assert hypothetical not in PUBLISHABLE_ALERT_CATEGORIES

    decision = evaluate_basic_publish_decision(
        signal_score_total=23,
        primary_category=hypothetical,
        source_credibility=5,
    )
    assert decision.action == PublishDecisionValue.REVIEW
    assert decision.pending_review_reason == PendingReviewReason.BLOCKED_BY_CATEGORY


def test_other_still_routes_to_review():
    from app.pipeline.publishing.constants import (
        PendingReviewReason,
        PublishDecisionValue,
    )
    from app.pipeline.publishing.publishing_policy import (
        evaluate_basic_publish_decision,
    )

    decision = evaluate_basic_publish_decision(
        signal_score_total=23,
        primary_category=OTHER_CATEGORY,
        source_credibility=5,
    )
    assert decision.action == PublishDecisionValue.REVIEW
    assert decision.reason == "manual_review_category"
    assert decision.pending_review_reason == PendingReviewReason.MANUAL_REVIEW_ONLY


def test_publishable_categories_auto_publish_at_critical():
    from app.pipeline.publishing.constants import PublishDecisionValue
    from app.pipeline.publishing.publishing_policy import (
        evaluate_basic_publish_decision,
    )

    for category in sorted(PUBLISHABLE_ALERT_CATEGORIES):
        decision = evaluate_basic_publish_decision(
            signal_score_total=23,
            primary_category=category,
            source_credibility=5,
        )
        assert decision.action == PublishDecisionValue.AUTO_PUBLISH, category
