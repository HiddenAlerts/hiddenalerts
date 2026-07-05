"""Tests for the IntelligenceBrief model and its controlled vocabulary.

Covers table registration, that inserting a minimal row applies the intended
lifecycle defaults, and that the constants module exposes the expected
vocabulary. The live Alembic upgrade/downgrade round-trip is verified
separately (see test_migration_0011_structure + manual Postgres check), since
the unit-test engine builds the schema from metadata rather than running
migrations.
"""
import uuid

import pytest
from sqlalchemy import select

from app.models import Base, IntelligenceBrief
from app.models.intelligence_brief_constants import (
    BRIEF_CONFIDENCE_LEVELS,
    BRIEF_RISK_LEVELS,
    BRIEF_STATUSES,
    BRIEF_TIME_HORIZONS,
    BRIEF_TYPES,
    SUBSCRIBER_VISIBLE_RISK_LEVELS,
)


def test_table_registered():
    assert IntelligenceBrief.__tablename__ == "intelligence_briefs"
    assert "intelligence_briefs" in Base.metadata.tables


def test_unique_constraints_present():
    table = Base.metadata.tables["intelligence_briefs"]
    constraint_names = {c.name for c in table.constraints}
    assert "uq_intelligence_briefs_slug" in constraint_names
    assert "uq_intelligence_briefs_brief_code" in constraint_names


def test_expected_indexes_present():
    table = Base.metadata.tables["intelligence_briefs"]
    index_names = {i.name for i in table.indexes}
    assert {
        "idx_intelligence_briefs_status",
        "idx_intelligence_briefs_risk_level",
        "idx_intelligence_briefs_category",
        "idx_intelligence_briefs_is_featured",
        "idx_intelligence_briefs_brief_type",
        "idx_intelligence_briefs_is_premium",
        "idx_intelligence_briefs_tags_gin",
        "idx_intelligence_briefs_primary_entities_gin",
    }.issubset(index_names)


def test_foreign_keys_target_users():
    table = Base.metadata.tables["intelligence_briefs"]
    for col in ("created_by_user_id", "updated_by_user_id"):
        fkeys = list(table.c[col].foreign_keys)
        assert len(fkeys) == 1
        assert fkeys[0].column.table.name == "users"


@pytest.mark.asyncio
async def test_create_minimal_brief_applies_defaults(db_session):
    """A minimal insert (only the NOT NULL non-defaulted fields) should get all
    lifecycle defaults from the model."""
    nonce = uuid.uuid4().hex[:8]
    brief = IntelligenceBrief(
        brief_code=f"HA-20260705-{nonce}",
        title="North Korean IT Worker Infiltration Networks",
        slug=f"north-korean-it-worker-infiltration-networks-{nonce}",
    )
    db_session.add(brief)
    await db_session.flush()
    await db_session.refresh(brief)

    assert brief.id is not None
    # Lifecycle defaults
    assert brief.status == "draft"
    assert brief.is_featured is False
    assert brief.is_premium is True
    assert brief.brief_type == "intelligence_brief"
    assert brief.alerts_count == 0
    assert brief.read_time_minutes == 1
    # Timestamps auto-populated, publish date not yet set
    assert brief.created_at is not None
    assert brief.updated_at is not None
    assert brief.published_at is None
    # Future-ready featured_order stays NULL (no misleading default)
    assert brief.featured_order is None


@pytest.mark.asyncio
async def test_jsonb_fields_roundtrip(db_session):
    """JSONB list/object fields persist and read back intact (JSON on SQLite)."""
    nonce = uuid.uuid4().hex[:8]
    slug = f"the-account-takeover-economy-{nonce}"
    brief = IntelligenceBrief(
        brief_code=f"HA-20260705-{nonce}",
        title="The Account Takeover Economy",
        slug=slug,
        tags=["Account Takeover", "Credential Theft"],
        primary_entities=["Mobile Banking Users"],
        key_signals=["Use of stolen identities", "Laptop farm operation"],
        supporting_alerts=[{"url": "https://example.com/a", "title": "A"}],
    )
    db_session.add(brief)
    await db_session.flush()

    fetched = (
        await db_session.execute(
            select(IntelligenceBrief).where(IntelligenceBrief.slug == slug)
        )
    ).scalar_one()
    assert fetched.tags == ["Account Takeover", "Credential Theft"]
    assert fetched.primary_entities == ["Mobile Banking Users"]
    assert fetched.key_signals[0] == "Use of stolen identities"
    assert fetched.supporting_alerts[0]["url"] == "https://example.com/a"


def test_constants_vocabulary():
    assert BRIEF_STATUSES == {"draft", "published", "archived"}
    assert BRIEF_RISK_LEVELS == {"critical", "high", "medium", "low"}
    assert BRIEF_CONFIDENCE_LEVELS == {"high", "medium", "low"}
    assert BRIEF_TIME_HORIZONS == {
        "immediate",
        "near_term",
        "medium_term",
        "long_term",
    }
    assert "intelligence_brief" in BRIEF_TYPES
    assert "premium_report" in BRIEF_TYPES


def test_subscriber_visible_risk_levels_are_critical_and_high():
    assert SUBSCRIBER_VISIBLE_RISK_LEVELS == {"critical", "high"}
    # These must always be a subset of the full risk-level vocabulary.
    assert SUBSCRIBER_VISIBLE_RISK_LEVELS.issubset(BRIEF_RISK_LEVELS)
