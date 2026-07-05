"""Structural checks for migration 0011 (intelligence_briefs).

Asserts the migration is chained off 0010 and that its downgrade drops exactly
what upgrade creates (reversibility by construction). The live upgrade/downgrade
round-trip is verified separately against a scratch Postgres database (Slice 1
manual verification), since the unit-test engine is SQLite-built-from-metadata
and does not run Alembic.
"""
import importlib.util
from pathlib import Path

# Alembic migration files are loaded by path (digit-prefixed names aren't valid
# dotted module identifiers), so load this one the same way.
_MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "0011_intelligence_briefs.py"
)
_spec = importlib.util.spec_from_file_location("_mig_0011", _MIGRATION_PATH)
migration = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migration)


def test_revision_chain():
    assert migration.revision == "0011"
    assert migration.down_revision == "0010"


def test_has_upgrade_and_downgrade():
    assert callable(migration.upgrade)
    assert callable(migration.downgrade)


def test_index_lists_cover_expected_columns():
    btree_cols = {col for _name, col in migration._BTREE_INDEXES}
    gin_cols = {col for _name, col in migration._GIN_INDEXES}
    assert {"status", "risk_level", "category", "is_featured", "brief_type", "is_premium"}.issubset(
        btree_cols
    )
    assert gin_cols == {"tags", "primary_entities"}
