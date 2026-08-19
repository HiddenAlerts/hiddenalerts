"""Tests for app/services/alert_query.py.

Focused on ``_as_naive_utc``, the datetime-normalization helper that fixes the
production ``source_published_from``/``source_published_to`` 500: PostgreSQL's
asyncpg driver crashes binding a timezone-aware Python datetime against
``RawItem.published_at`` because the SQLAlchemy model declares that column
without ``DateTime(timezone=True)``, even though the real column is genuinely
``TIMESTAMP WITH TIME ZONE``. See the function's own docstring for the full
mechanism. SQLite (this test suite's driver) does not reproduce that asyncpg
crash — these tests prove the conversion *logic* is correct; they cannot, on
their own, prove the production crash is fixed. See test_admin_subscriber_alignment.py
and test_alerts_api.py for the API-level filter-correctness coverage, and the
project's E2E harness for the real-PostgreSQL proof after deployment.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.alert_query import _as_naive_utc


def test_none_stays_none():
    assert _as_naive_utc(None) is None


def test_naive_datetime_is_unchanged():
    naive = datetime(2026, 8, 17, 12, 0, 0)
    result = _as_naive_utc(naive)
    assert result == naive
    assert result.tzinfo is None


def test_utc_aware_datetime_becomes_equivalent_naive_utc():
    aware = datetime(2026, 8, 17, 12, 0, 0, tzinfo=timezone.utc)
    result = _as_naive_utc(aware)
    assert result == datetime(2026, 8, 17, 12, 0, 0)
    assert result.tzinfo is None


def test_positive_offset_converts_to_the_correct_utc_instant():
    """2026-08-01T02:00:00+02:00 is the same instant as 2026-08-01T00:00:00Z."""
    plus_two = timezone(timedelta(hours=2))
    aware = datetime(2026, 8, 1, 2, 0, 0, tzinfo=plus_two)
    result = _as_naive_utc(aware)
    assert result == datetime(2026, 8, 1, 0, 0, 0)
    assert result.tzinfo is None


def test_negative_offset_converts_to_the_correct_utc_instant():
    """2026-08-01T20:00:00-05:00 is the same instant as 2026-08-02T01:00:00Z."""
    minus_five = timezone(timedelta(hours=-5))
    aware = datetime(2026, 8, 1, 20, 0, 0, tzinfo=minus_five)
    result = _as_naive_utc(aware)
    assert result == datetime(2026, 8, 2, 1, 0, 0)
    assert result.tzinfo is None


def test_microseconds_are_preserved():
    aware = datetime(2026, 8, 17, 12, 0, 0, 123456, tzinfo=timezone.utc)
    result = _as_naive_utc(aware)
    assert result.microsecond == 123456

    plus_one = timezone(timedelta(hours=1))
    aware_offset = datetime(2026, 8, 17, 13, 0, 0, 654321, tzinfo=plus_one)
    result_offset = _as_naive_utc(aware_offset)
    assert result_offset == datetime(2026, 8, 17, 12, 0, 0, 654321)


def test_input_value_is_not_mutated():
    plus_two = timezone(timedelta(hours=2))
    original = datetime(2026, 8, 1, 2, 0, 0, tzinfo=plus_two)
    before = (original.year, original.month, original.day, original.hour,
              original.minute, original.second, original.tzinfo)

    _as_naive_utc(original)

    after = (original.year, original.month, original.day, original.hour,
              original.minute, original.second, original.tzinfo)
    assert before == after
    assert original.tzinfo is plus_two


def test_z_suffix_and_explicit_utc_offset_are_equivalent():
    """FastAPI parses both '...Z' and '...+00:00' to the same aware value —
    confirm the helper treats them identically."""
    from_z = datetime.fromisoformat("2026-08-17T12:00:00+00:00")
    from_offset = datetime(2026, 8, 17, 12, 0, 0, tzinfo=timezone.utc)
    assert _as_naive_utc(from_z) == _as_naive_utc(from_offset)
