"""V1 Alert Publishing — Slice 1 schema/model foundation tests.

Verifies the additive publication-state columns on ``processed_alerts`` and the
audit columns on ``alert_reviews`` are present with the correct typing, that the
new boolean columns default to ``False`` at the ORM layer, and that the
controlled-vocabulary constants exist. No pipeline behaviour is exercised here —
this slice only lays the schema foundation.
"""
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models import AlertReview, Base, ProcessedAlert
from app.models.raw_item import RawItem
from app.models.source import Source
from app.pipeline.publishing import (
    DECISION_SOURCES,
    PENDING_REVIEW_REASONS,
    PUBLISH_DECISIONS,
    RISK_BANDS,
)

# --- Expected schema ---------------------------------------------------------

_NEW_ALERT_COLUMNS = {
    "risk_band",
    "publish_decision",
    "publish_decision_reason",
    "pending_review_reason",
    "is_excluded",
    "excluded_reason",
    "is_manual_hold",
    "published_by_rule",
    "publishing_policy_version",
    "publication_state_source",
    "publication_state_updated_at",
}
_NEW_ALERT_BOOLEAN_COLUMNS = {"is_excluded", "is_manual_hold", "published_by_rule"}
_NEW_REVIEW_COLUMNS = {"review_batch_id", "decision_source"}
_NEW_ALERT_INDEXES = {
    "idx_processed_alerts_risk_band",
    "idx_processed_alerts_pending_review_reason",
    "idx_processed_alerts_publish_decision",
    "idx_processed_alerts_publication_state_source",
}


# --- Column presence / typing (metadata-level, no DB needed) -----------------


def test_processed_alert_has_all_v1_columns():
    cols = set(ProcessedAlert.__table__.c.keys())
    missing = _NEW_ALERT_COLUMNS - cols
    assert not missing, f"missing V1 columns on processed_alerts: {missing}"


def test_processed_alert_new_booleans_not_nullable():
    for name in _NEW_ALERT_BOOLEAN_COLUMNS:
        col = ProcessedAlert.__table__.c[name]
        assert col.nullable is False, f"{name} should be NOT NULL"


def test_processed_alert_text_state_columns_nullable():
    for name in _NEW_ALERT_COLUMNS - _NEW_ALERT_BOOLEAN_COLUMNS:
        col = ProcessedAlert.__table__.c[name]
        assert col.nullable is True, f"{name} should be nullable"


def test_processed_alert_v1_indexes_registered():
    index_names = {ix.name for ix in ProcessedAlert.__table__.indexes}
    missing = _NEW_ALERT_INDEXES - index_names
    assert not missing, f"missing V1 indexes: {missing}"


def test_alert_review_has_audit_columns():
    cols = set(AlertReview.__table__.c.keys())
    missing = _NEW_REVIEW_COLUMNS - cols
    assert not missing, f"missing V1 columns on alert_reviews: {missing}"
    for name in _NEW_REVIEW_COLUMNS:
        assert AlertReview.__table__.c[name].nullable is True


# --- Boolean defaults (round-trip through the test DB) -----------------------


@pytest.mark.asyncio
async def test_new_booleans_default_false_on_insert(db_session):
    """Inserting an alert without setting the new booleans yields False."""
    source = Source(
        name="Slice1 Test Source",
        base_url="https://example.test",
        source_type="rss",
        credibility_score=4,
    )
    db_session.add(source)
    await db_session.flush()

    raw = RawItem(
        source_id=source.id,
        title="Slice1 raw",
        item_url="https://example.test/a",
        raw_text="body",
        fetched_at=datetime.now(timezone.utc),
    )
    db_session.add(raw)
    await db_session.flush()

    alert = ProcessedAlert(raw_item_id=raw.id, is_relevant=True)
    db_session.add(alert)
    await db_session.flush()
    await db_session.refresh(alert)

    # New booleans default to False; new nullable state columns default to None.
    assert alert.is_excluded is False
    assert alert.is_manual_hold is False
    assert alert.published_by_rule is False
    assert alert.risk_band is None
    assert alert.publish_decision is None
    assert alert.pending_review_reason is None
    assert alert.publication_state_source is None
    assert alert.publication_state_updated_at is None
    # Existing publication behaviour is untouched: still unpublished by default.
    assert alert.is_published is False


@pytest.mark.asyncio
async def test_review_audit_columns_round_trip(db_session):
    """review_batch_id / decision_source persist and read back."""
    review = AlertReview(
        review_status="approved",
        review_batch_id="batch-2026-06-16",
        decision_source="candidate_backfill",
    )
    db_session.add(review)
    await db_session.flush()
    fetched = (
        await db_session.execute(select(AlertReview).where(AlertReview.id == review.id))
    ).scalar_one()
    assert fetched.review_batch_id == "batch-2026-06-16"
    assert fetched.decision_source == "candidate_backfill"


# --- Constants vocabulary ----------------------------------------------------


def test_risk_band_vocabulary():
    assert RISK_BANDS == {"critical", "high", "medium", "below_60"}


def test_publish_decision_vocabulary():
    assert PUBLISH_DECISIONS == {"auto_publish", "review", "exclude", "hold"}


def test_pending_review_reason_vocabulary():
    assert PENDING_REVIEW_REASONS == {
        "blocked_by_credibility",
        "blocked_by_score",
        "blocked_by_category",
        "blocked_by_source_rule",
        "manual_review_only",
        "excluded_low_score",
        "ai_rejected",
        "manual_hold",
        "manual_rejected",
    }


def test_decision_source_vocabulary():
    assert DECISION_SOURCES == {
        "auto_policy",
        "manual_admin",
        "candidate_backfill",
        "system_migration",
    }


def test_processed_alerts_table_registered():
    assert "processed_alerts" in Base.metadata.tables
    assert "alert_reviews" in Base.metadata.tables
