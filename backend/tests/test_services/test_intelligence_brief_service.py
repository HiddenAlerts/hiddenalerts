"""Tests for the Intelligence Brief admin service layer and request schemas."""
from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.models.intelligence_brief import IntelligenceBrief
from app.schemas.intelligence_brief import (
    IntelligenceBriefCreate,
    IntelligenceBriefUpdate,
)
from app.services import intelligence_brief_service as service
from app.services.intelligence_brief_helpers import is_valid_brief_code


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def test_blank_title_rejected():
    with pytest.raises(ValidationError):
        IntelligenceBriefCreate(title="   ")


def test_missing_title_rejected():
    with pytest.raises(ValidationError):
        IntelligenceBriefCreate()


@pytest.mark.parametrize("bad_score", [-1, 101, 500])
def test_risk_score_out_of_range_rejected(bad_score):
    with pytest.raises(ValidationError):
        IntelligenceBriefCreate(title="X", risk_score=bad_score)


def test_invalid_risk_level_rejected():
    with pytest.raises(ValidationError):
        IntelligenceBriefCreate(title="X", risk_level="extreme")


def test_invalid_confidence_level_rejected():
    with pytest.raises(ValidationError):
        IntelligenceBriefCreate(title="X", confidence_level="certain")


def test_invalid_time_horizon_rejected():
    with pytest.raises(ValidationError):
        IntelligenceBriefCreate(title="X", time_horizon="yesterday")


def test_invalid_brief_type_rejected():
    with pytest.raises(ValidationError):
        IntelligenceBriefCreate(title="X", brief_type="memo")


def test_supporting_alerts_wrong_type_rejected():
    with pytest.raises(ValidationError):
        IntelligenceBriefCreate(title="X", supporting_alerts="not-a-list")


def test_supporting_alert_without_url_rejected():
    with pytest.raises(ValidationError):
        IntelligenceBriefCreate(title="X", supporting_alerts=[{"title": "no url"}])


def test_supporting_alert_whitespace_url_rejected():
    with pytest.raises(ValidationError):
        IntelligenceBriefCreate(title="X", supporting_alerts=[{"url": "   "}])


def test_key_signals_wrong_type_rejected():
    with pytest.raises(ValidationError):
        IntelligenceBriefCreate(title="X", key_signals="not-a-list")


def test_valid_enum_values_accepted():
    payload = IntelligenceBriefCreate(
        title="X",
        risk_level="critical",
        confidence_level="high",
        time_horizon="near_term",
        brief_type="intelligence_brief",
    )
    # use_enum_values stores plain strings
    assert payload.risk_level == "critical"
    assert payload.time_horizon == "near_term"


# ---------------------------------------------------------------------------
# create_brief
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_generates_slug_and_brief_code(db_session):
    brief = await service.create_brief(
        db_session,
        IntelligenceBriefCreate(title="The Account Takeover Economy"),
        user_id=None,
    )
    assert brief.slug == "the-account-takeover-economy"
    assert is_valid_brief_code(brief.brief_code)


@pytest.mark.asyncio
async def test_create_uses_provided_slug(db_session):
    brief = await service.create_brief(
        db_session,
        IntelligenceBriefCreate(title="Whatever", slug="Custom Slug Value"),
        user_id=None,
    )
    assert brief.slug == "custom-slug-value"


@pytest.mark.asyncio
async def test_create_applies_defaults(db_session):
    brief = await service.create_brief(
        db_session, IntelligenceBriefCreate(title="Draft brief"), user_id=None
    )
    assert brief.status == "draft"
    assert brief.is_featured is False
    assert brief.is_premium is True
    assert brief.brief_type == "intelligence_brief"
    assert brief.published_at is None


@pytest.mark.asyncio
async def test_create_sanitizes_html(db_session):
    brief = await service.create_brief(
        db_session,
        IntelligenceBriefCreate(
            title="X",
            executive_summary="<p>ok</p><script>alert(1)</script>",
        ),
        user_id=None,
    )
    assert "<script" not in brief.executive_summary
    assert "alert(1)" not in brief.executive_summary
    assert "<p>ok</p>" in brief.executive_summary


@pytest.mark.asyncio
async def test_create_calculates_alerts_count(db_session):
    brief = await service.create_brief(
        db_session,
        IntelligenceBriefCreate(
            title="X",
            supporting_alerts=[
                {"url": "https://a.com/1"},
                {"url": "https://a.com/2", "title": "Two"},
            ],
        ),
        user_id=None,
    )
    assert brief.alerts_count == 2


@pytest.mark.asyncio
async def test_create_calculates_read_time(db_session):
    long_text = " ".join(["word"] * 201)
    brief = await service.create_brief(
        db_session,
        IntelligenceBriefCreate(title="X", main_intelligence_brief=long_text),
        user_id=None,
    )
    # 201 words at 200 wpm rounds up to 2 minutes.
    assert brief.read_time_minutes == 2


@pytest.mark.asyncio
async def test_read_time_excludes_analyst_notes(db_session):
    notes = " ".join(["secret"] * 5000)
    brief = await service.create_brief(
        db_session,
        IntelligenceBriefCreate(title="X", analyst_notes=notes),
        user_id=None,
    )
    # analyst_notes must not inflate read time — no subscriber content present.
    assert brief.read_time_minutes == 1


@pytest.mark.asyncio
async def test_create_sets_audit_user(db_session):
    from app.models.user import User
    from app.auth import hash_password

    user = User(
        email="analyst@test.com",
        password_hash=hash_password("x"),
        is_active=True,
        role="admin",
    )
    db_session.add(user)
    await db_session.flush()

    brief = await service.create_brief(
        db_session, IntelligenceBriefCreate(title="X"), user_id=user.id
    )
    assert brief.created_by_user_id == user.id
    assert brief.updated_by_user_id == user.id


@pytest.mark.asyncio
async def test_generated_slug_conflict_gets_suffix(db_session):
    first = await service.create_brief(
        db_session, IntelligenceBriefCreate(title="Same Title"), user_id=None
    )
    second = await service.create_brief(
        db_session, IntelligenceBriefCreate(title="Same Title"), user_id=None
    )
    assert first.slug == "same-title"
    assert second.slug == "same-title-2"


@pytest.mark.asyncio
async def test_provided_slug_conflict_raises(db_session):
    await service.create_brief(
        db_session, IntelligenceBriefCreate(title="A", slug="taken"), user_id=None
    )
    with pytest.raises(service.SlugConflictError):
        await service.create_brief(
            db_session, IntelligenceBriefCreate(title="B", slug="taken"), user_id=None
        )


@pytest.mark.asyncio
async def test_brief_code_increments_per_day(db_session):
    a = await service.create_brief(
        db_session, IntelligenceBriefCreate(title="One"), user_id=None
    )
    b = await service.create_brief(
        db_session, IntelligenceBriefCreate(title="Two"), user_id=None
    )
    seq_a = int(a.brief_code.rsplit("-", 1)[1])
    seq_b = int(b.brief_code.rsplit("-", 1)[1])
    assert seq_b == seq_a + 1


# ---------------------------------------------------------------------------
# update_brief
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_changes_only_provided_fields(db_session):
    brief = await service.create_brief(
        db_session,
        IntelligenceBriefCreate(title="Original", category="Fraud"),
        user_id=None,
    )
    original_code = brief.brief_code
    updated = await service.update_brief(
        db_session,
        brief.id,
        IntelligenceBriefUpdate(category="Emerging Threat"),
        user_id=None,
    )
    assert updated.category == "Emerging Threat"
    assert updated.title == "Original"  # untouched
    assert updated.brief_code == original_code  # never changes


@pytest.mark.asyncio
async def test_update_sanitizes_changed_html(db_session):
    brief = await service.create_brief(
        db_session, IntelligenceBriefCreate(title="X"), user_id=None
    )
    updated = await service.update_brief(
        db_session,
        brief.id,
        IntelligenceBriefUpdate(why_this_matters="<b>keep</b><script>x()</script>"),
        user_id=None,
    )
    assert "<b>keep</b>" in updated.why_this_matters
    assert "<script" not in updated.why_this_matters


@pytest.mark.asyncio
async def test_update_recalculates_alerts_count(db_session):
    brief = await service.create_brief(
        db_session,
        IntelligenceBriefCreate(
            title="X", supporting_alerts=[{"url": "https://a.com/1"}]
        ),
        user_id=None,
    )
    assert brief.alerts_count == 1
    updated = await service.update_brief(
        db_session,
        brief.id,
        IntelligenceBriefUpdate(
            supporting_alerts=[
                {"url": "https://a.com/1"},
                {"url": "https://a.com/2"},
                {"url": "https://a.com/3"},
            ]
        ),
        user_id=None,
    )
    assert updated.alerts_count == 3


@pytest.mark.asyncio
async def test_update_recalculates_read_time(db_session):
    brief = await service.create_brief(
        db_session, IntelligenceBriefCreate(title="X"), user_id=None
    )
    assert brief.read_time_minutes == 1
    long_text = " ".join(["word"] * 401)
    updated = await service.update_brief(
        db_session,
        brief.id,
        IntelligenceBriefUpdate(main_intelligence_brief=long_text),
        user_id=None,
    )
    assert updated.read_time_minutes == 3  # 401 words / 200 wpm -> 3


@pytest.mark.asyncio
async def test_update_missing_brief_raises(db_session):
    with pytest.raises(service.BriefNotFoundError):
        await service.update_brief(
            db_session, 999999, IntelligenceBriefUpdate(title="Nope"), user_id=None
        )


@pytest.mark.asyncio
async def test_update_slug_conflict_raises(db_session):
    await service.create_brief(
        db_session, IntelligenceBriefCreate(title="A", slug="alpha"), user_id=None
    )
    brief_b = await service.create_brief(
        db_session, IntelligenceBriefCreate(title="B", slug="beta"), user_id=None
    )
    with pytest.raises(service.SlugConflictError):
        await service.update_brief(
            db_session, brief_b.id, IntelligenceBriefUpdate(slug="alpha"), user_id=None
        )


@pytest.mark.asyncio
async def test_list_filters_and_pagination(db_session):
    # Scope assertions to a unique category so committed rows from other tests
    # (the API layer commits) don't affect the counts.
    category = f"cat-{uuid.uuid4().hex[:8]}"
    await service.create_brief(
        db_session,
        IntelligenceBriefCreate(
            title="Critical fraud", category=category, risk_level="critical"
        ),
        user_id=None,
    )
    await service.create_brief(
        db_session,
        IntelligenceBriefCreate(
            title="Low noise", category=category, risk_level="low"
        ),
        user_id=None,
    )

    items, total = await service.list_briefs(db_session, category=category)
    assert total == 2

    items, total = await service.list_briefs(
        db_session, category=category, risk_level="critical"
    )
    assert total == 1
    assert items[0].risk_level == "critical"


# ---------------------------------------------------------------------------
# Slug hardening
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_slug_null_keeps_current_slug(db_session):
    brief = await service.create_brief(
        db_session, IntelligenceBriefCreate(title="Keep My Slug"), user_id=None
    )
    original = brief.slug
    updated = await service.update_brief(
        db_session,
        brief.id,
        IntelligenceBriefUpdate(slug=None, category="Fraud"),
        user_id=None,
    )
    assert updated.slug == original
    assert updated.category == "Fraud"


@pytest.mark.asyncio
async def test_long_generated_slug_truncated_to_255(db_session):
    long_title = "a" * 400
    brief = await service.create_brief(
        db_session, IntelligenceBriefCreate(title=long_title), user_id=None
    )
    assert len(brief.slug) <= 255


@pytest.mark.asyncio
async def test_duplicate_long_generated_slug_gets_valid_suffix(db_session):
    long_title = "a" * 400
    first = await service.create_brief(
        db_session, IntelligenceBriefCreate(title=long_title), user_id=None
    )
    second = await service.create_brief(
        db_session, IntelligenceBriefCreate(title=long_title), user_id=None
    )
    assert first.slug != second.slug
    assert len(second.slug) <= 255
    assert second.slug.endswith("-2")


# ---------------------------------------------------------------------------
# Lifecycle: publish / archive / feature / unfeature
# ---------------------------------------------------------------------------


def _publishable(title: str = "Publishable brief", **overrides) -> IntelligenceBriefCreate:
    """A create payload carrying every field required to publish."""
    fields = dict(
        title=title,
        risk_score=90,
        risk_level="critical",
        executive_summary="<p>Executive summary</p>",
        main_intelligence_brief="<p>Full brief body</p>",
    )
    fields.update(overrides)
    return IntelligenceBriefCreate(**fields)


async def _make(db_session, **overrides) -> IntelligenceBrief:
    return await service.create_brief(db_session, _publishable(**overrides), user_id=None)


@pytest.mark.asyncio
async def test_publish_sets_status(db_session):
    brief = await _make(db_session)
    published = await service.publish_brief(db_session, brief.id, user_id=None)
    assert published.status == "published"


@pytest.mark.asyncio
async def test_publish_sets_published_at_when_null(db_session):
    brief = await _make(db_session)
    assert brief.published_at is None
    published = await service.publish_brief(db_session, brief.id, user_id=None)
    assert published.published_at is not None


@pytest.mark.asyncio
async def test_publish_preserves_existing_published_at(db_session):
    brief = await _make(db_session)
    first = await service.publish_brief(db_session, brief.id, user_id=None)
    original = first.published_at
    # Archive then re-publish; the original publication date must be preserved.
    await service.archive_brief(db_session, brief.id, user_id=None)
    republished = await service.publish_brief(db_session, brief.id, user_id=None)
    assert republished.published_at == original


@pytest.mark.asyncio
async def test_publish_sets_updated_by(db_session):
    from app.models.user import User
    from app.auth import hash_password

    user = User(
        email=f"pub_{uuid.uuid4().hex[:6]}@test.com",
        password_hash=hash_password("x"),
        is_active=True,
        role="admin",
    )
    db_session.add(user)
    await db_session.flush()

    brief = await _make(db_session)
    published = await service.publish_brief(db_session, brief.id, user_id=user.id)
    assert published.updated_by_user_id == user.id


@pytest.mark.parametrize("missing_field", ["risk_score", "risk_level", "executive_summary", "main_intelligence_brief"])
@pytest.mark.asyncio
async def test_publish_rejects_missing_required_field(db_session, missing_field):
    brief = await _make(db_session, **{missing_field: None})
    with pytest.raises(service.BriefPublishValidationError) as excinfo:
        await service.publish_brief(db_session, brief.id, user_id=None)
    assert missing_field in excinfo.value.fields


@pytest.mark.asyncio
async def test_publish_missing_brief_raises(db_session):
    with pytest.raises(service.BriefNotFoundError):
        await service.publish_brief(db_session, 999999, user_id=None)


@pytest.mark.asyncio
async def test_archive_sets_status_and_clears_featured(db_session):
    brief = await _make(db_session)
    await service.publish_brief(db_session, brief.id, user_id=None)
    featured = await service.feature_brief(db_session, brief.id, user_id=None)
    assert featured.is_featured is True
    assert featured.featured_order == 1

    archived = await service.archive_brief(db_session, brief.id, user_id=None)
    assert archived.status == "archived"
    assert archived.is_featured is False
    assert archived.featured_order is None


@pytest.mark.asyncio
async def test_archive_preserves_published_at(db_session):
    brief = await _make(db_session)
    published = await service.publish_brief(db_session, brief.id, user_id=None)
    published_at = published.published_at
    archived = await service.archive_brief(db_session, brief.id, user_id=None)
    assert archived.published_at == published_at


@pytest.mark.asyncio
async def test_feature_rejects_draft(db_session):
    brief = await _make(db_session)  # still draft
    with pytest.raises(service.BriefFeatureEligibilityError):
        await service.feature_brief(db_session, brief.id, user_id=None)


@pytest.mark.asyncio
async def test_feature_rejects_archived(db_session):
    brief = await _make(db_session)
    await service.publish_brief(db_session, brief.id, user_id=None)
    await service.archive_brief(db_session, brief.id, user_id=None)
    with pytest.raises(service.BriefFeatureEligibilityError):
        await service.feature_brief(db_session, brief.id, user_id=None)


@pytest.mark.parametrize("risk_level", ["medium", "low"])
@pytest.mark.asyncio
async def test_feature_rejects_medium_low(db_session, risk_level):
    brief = await _make(db_session, risk_level=risk_level)
    await service.publish_brief(db_session, brief.id, user_id=None)
    with pytest.raises(service.BriefFeatureEligibilityError):
        await service.feature_brief(db_session, brief.id, user_id=None)


@pytest.mark.parametrize("risk_level", ["critical", "high"])
@pytest.mark.asyncio
async def test_feature_accepts_published_critical_high(db_session, risk_level):
    brief = await _make(db_session, risk_level=risk_level)
    await service.publish_brief(db_session, brief.id, user_id=None)
    featured = await service.feature_brief(db_session, brief.id, user_id=None)
    assert featured.is_featured is True
    assert featured.featured_order == 1


@pytest.mark.asyncio
async def test_feature_clears_previous_featured(db_session):
    a = await _make(db_session, title="Brief A")
    b = await _make(db_session, title="Brief B")
    await service.publish_brief(db_session, a.id, user_id=None)
    await service.publish_brief(db_session, b.id, user_id=None)

    await service.feature_brief(db_session, a.id, user_id=None)
    await service.feature_brief(db_session, b.id, user_id=None)

    # The bulk clear bypasses the identity map; refresh A to read committed state.
    await db_session.refresh(a)
    assert a.is_featured is False
    assert a.featured_order is None
    assert b.is_featured is True

    # Invariant: at most one featured brief exists.
    featured, total = await service.list_briefs(db_session, is_featured=True)
    assert total == 1
    assert featured[0].id == b.id


@pytest.mark.asyncio
async def test_unfeature_clears_state_and_is_idempotent(db_session):
    brief = await _make(db_session)
    await service.publish_brief(db_session, brief.id, user_id=None)
    await service.feature_brief(db_session, brief.id, user_id=None)

    unfeatured = await service.unfeature_brief(db_session, brief.id, user_id=None)
    assert unfeatured.is_featured is False
    assert unfeatured.featured_order is None

    # Idempotent: unfeaturing again is a no-op, not an error.
    again = await service.unfeature_brief(db_session, brief.id, user_id=None)
    assert again.is_featured is False
