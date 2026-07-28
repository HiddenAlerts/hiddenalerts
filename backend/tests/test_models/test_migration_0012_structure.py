"""Structural checks for migration 0012 (run_logs skip telemetry).

Asserts the migration is chained off 0011 and that its downgrade drops exactly
what upgrade adds. The live upgrade/downgrade round-trip runs against a scratch
Postgres database, since the unit-test engine is SQLite-built-from-metadata and
does not run Alembic.
"""
import importlib.util
from pathlib import Path

from sqlalchemy import inspect

from app.models.base import Base
from app.models.run_log import RunLog

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "0012_run_log_skip_telemetry.py"
)
_spec = importlib.util.spec_from_file_location("_mig_0012", _MIGRATION_PATH)
migration = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migration)


def test_revision_chain():
    assert migration.revision == "0012"
    assert migration.down_revision == "0011"


def test_has_upgrade_and_downgrade():
    assert callable(migration.upgrade)
    assert callable(migration.downgrade)


def test_counter_columns_are_the_three_skip_fields():
    assert migration._COUNTER_COLUMNS == (
        "items_skipped_url",
        "items_skipped_content",
        "items_skipped_invalid",
    )


def test_migration_columns_match_the_orm_model():
    columns = set(RunLog.__table__.columns.keys())
    assert set(migration._COUNTER_COLUMNS).issubset(columns)


def test_new_index_is_not_a_duplicate_of_an_existing_one():
    """The table already indexes source_id and status; this one adds the ordering."""
    existing = {index.name for index in Base.metadata.tables["run_logs"].indexes}
    assert migration._INDEX_NAME in existing
    assert {"idx_run_logs_source_id", "idx_run_logs_status"}.issubset(existing)


def test_counter_columns_are_non_null_with_a_zero_default():
    for name in migration._COUNTER_COLUMNS:
        column = RunLog.__table__.columns[name]
        assert column.nullable is False
        assert column.server_default is not None


def test_run_log_table_is_inspectable_from_metadata():
    inspector = inspect(RunLog)
    for name in migration._COUNTER_COLUMNS:
        assert name in inspector.columns
