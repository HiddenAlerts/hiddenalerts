"""Structural checks for migration 0010 (V1 publishing state).

These assert the migration is correctly chained off 0009 and that its
downgrade drops exactly what upgrade adds (reversibility by construction). The
live upgrade/downgrade round-trip is verified separately against a scratch
Postgres database (Slice 1 manual verification), since the unit-test engine is
SQLite-built-from-metadata and does not run Alembic.
"""
import importlib.util
from pathlib import Path

# Alembic migration files are loaded by path (digit-prefixed names aren't valid
# dotted module identifiers), so load this one the same way.
_MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "0010_v1_publishing_state.py"
)
_spec = importlib.util.spec_from_file_location("_mig_0010", _MIGRATION_PATH)
migration = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migration)


def test_revision_chain():
    assert migration.revision == "0010"
    assert migration.down_revision == "0009"


def test_upgrade_and_downgrade_are_callable():
    assert callable(migration.upgrade)
    assert callable(migration.downgrade)


def test_column_lists_match_model_expectations():
    alert_cols = {c[0] for c in migration._PROCESSED_ALERT_COLUMNS}
    assert alert_cols == {
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
    review_cols = {c[0] for c in migration._ALERT_REVIEW_COLUMNS}
    assert review_cols == {"review_batch_id", "decision_source"}


def test_boolean_columns_have_false_server_default():
    booleans = {
        name: server_default
        for name, _type, _nullable, server_default in migration._PROCESSED_ALERT_COLUMNS
        if name in {"is_excluded", "is_manual_hold", "published_by_rule"}
    }
    assert set(booleans) == {"is_excluded", "is_manual_hold", "published_by_rule"}
    # Each non-null boolean carries a server_default so existing rows backfill.
    for name, server_default in booleans.items():
        assert server_default is not None, f"{name} needs a server_default"


def test_indexes_declared():
    index_names = {ix[0] for ix in migration._PROCESSED_ALERT_INDEXES}
    assert index_names == {
        "idx_processed_alerts_risk_band",
        "idx_processed_alerts_pending_review_reason",
        "idx_processed_alerts_publish_decision",
        "idx_processed_alerts_publication_state_source",
    }
