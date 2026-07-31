"""Structural checks for migration 0013 (source URL decisions + external telemetry).

Asserts the migration is chained off 0012, that what it creates matches the ORM
models, and that its downgrade drops exactly what upgrade adds. The live
upgrade/downgrade round-trip runs against a scratch Postgres database, since the
unit-test engine is SQLite-built-from-metadata and does not run Alembic.
"""
import importlib.util
from pathlib import Path

from app.models.base import Base
from app.models.run_log import RunLog
from app.models.source_url_decision import (
    EXTERNAL_DESTINATION_EXCLUDED,
    SUPPRESSING_DECISIONS,
    SourceURLDecision,
)

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "0013_source_url_decisions_and_external_telemetry.py"
)
_spec = importlib.util.spec_from_file_location("_mig_0013", _MIGRATION_PATH)
migration = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migration)


def test_revision_chain():
    assert migration.revision == "0013"
    assert migration.down_revision == "0012"


def test_has_upgrade_and_downgrade():
    assert callable(migration.upgrade)
    assert callable(migration.downgrade)


def test_migration_names_match_the_orm_model():
    assert migration._TABLE == SourceURLDecision.__tablename__
    assert migration._RUN_LOG_COLUMN in RunLog.__table__.columns


def test_run_log_counter_is_non_null_with_a_zero_default():
    """Existing rows read as "no exclusions", not as unknown."""
    column = RunLog.__table__.columns[migration._RUN_LOG_COLUMN]
    assert column.nullable is False
    assert column.server_default is not None
    assert "0" in str(column.server_default.arg)


def test_unique_constraint_is_source_scoped():
    constraint = {
        c.name: c for c in SourceURLDecision.__table__.constraints if c.name
    }[migration._UNIQUE_CONSTRAINT]
    assert [c.name for c in constraint.columns] == ["source_id", "url_hash"]


def test_declared_indexes_exist_on_the_model():
    declared = {name for name, _ in migration._INDEXES}
    actual = {index.name for index in SourceURLDecision.__table__.indexes}
    assert declared == actual


def test_downgrade_drops_everything_upgrade_adds():
    source = _MIGRATION_PATH.read_text()
    upgrade_body = source.split("def upgrade()")[1].split("def downgrade()")[0]
    downgrade_body = source.split("def downgrade()")[1]

    assert "op.create_table" in upgrade_body and "op.drop_table" in downgrade_body
    assert "op.add_column" in upgrade_body and "op.drop_column" in downgrade_body
    # Both directions loop over the same _INDEXES tuple, so each appears once.
    assert upgrade_body.count("op.create_index") == 1
    assert downgrade_body.count("op.drop_index") == 1
    assert "_INDEXES" in upgrade_body and "_INDEXES" in downgrade_body


def test_decision_vocabulary_is_narrow():
    """One terminal decision today; the set is the extension point."""
    assert EXTERNAL_DESTINATION_EXCLUDED in SUPPRESSING_DECISIONS
    assert SUPPRESSING_DECISIONS == frozenset({EXTERNAL_DESTINATION_EXCLUDED})


def test_table_is_registered_in_metadata():
    assert "source_url_decisions" in Base.metadata.tables


def test_source_ownership_cascades():
    """A deleted source takes its decisions with it, like its other records."""
    table = Base.metadata.tables["source_url_decisions"]
    fk = next(iter(table.c.source_id.foreign_keys))
    assert fk.column.table.name == "sources"
    assert fk.ondelete == "CASCADE"

    from app.models.source import Source

    relationship = Source.__mapper__.relationships["url_decisions"]
    assert "delete-orphan" in relationship.cascade
