"""Unit tests for the Intelligence Brief pure helpers."""
from datetime import date

import pytest

from app.services.intelligence_brief_helpers import (
    SLUG_FALLBACK,
    calculate_read_time,
    count_supporting_alerts,
    generate_brief_code,
    is_valid_brief_code,
    normalize_slug,
)


# --- normalize_slug ---------------------------------------------------------

def test_normalize_slug_basic():
    assert normalize_slug("The Account Takeover Economy") == "the-account-takeover-economy"


def test_normalize_slug_strips_punctuation_and_collapses():
    assert normalize_slug("  Hello,   World!!  ") == "hello-world"


def test_normalize_slug_transliterates_unicode():
    assert normalize_slug("Café Señor") == "cafe-senor"


def test_normalize_slug_empty_title_uses_fallback():
    assert normalize_slug("") == SLUG_FALLBACK
    assert normalize_slug(None) == SLUG_FALLBACK


def test_normalize_slug_non_slug_friendly_uses_fallback():
    # Title made entirely of punctuation / non-latin symbols -> fallback base.
    assert normalize_slug("!!!") == SLUG_FALLBACK
    assert normalize_slug("你好", fallback="untitled") == "untitled"


# --- generate_brief_code ----------------------------------------------------

def test_generate_brief_code_format():
    code = generate_brief_code(1, on_date=date(2026, 6, 26))
    assert code == "HA-20260626-001"


def test_generate_brief_code_zero_pads_sequence():
    assert generate_brief_code(42, on_date=date(2026, 1, 2)) == "HA-20260102-042"


def test_generate_brief_code_overflow_keeps_digits():
    assert generate_brief_code(1000, on_date=date(2026, 1, 2)) == "HA-20260102-1000"


def test_generate_brief_code_rejects_bad_sequence():
    with pytest.raises(ValueError):
        generate_brief_code(0, on_date=date(2026, 1, 2))


def test_generate_brief_code_defaults_to_today(monkeypatch):
    code = generate_brief_code(1)
    assert is_valid_brief_code(code)


def test_is_valid_brief_code():
    assert is_valid_brief_code("HA-20260626-001")
    assert not is_valid_brief_code("HA-2026-001")
    assert not is_valid_brief_code("XX-20260626-001")
    assert not is_valid_brief_code(None)
    assert not is_valid_brief_code("")


# --- calculate_read_time ----------------------------------------------------

def test_calculate_read_time_minimum_for_empty():
    assert calculate_read_time("", None) == 1
    assert calculate_read_time() == 1


def test_calculate_read_time_rounds_up():
    # 201 words at 200 wpm -> 2 minutes (ceiling).
    text = " ".join(["word"] * 201)
    assert calculate_read_time(text) == 2


def test_calculate_read_time_strips_html():
    # 200 plain words -> exactly 1 minute; HTML tags must not inflate the count.
    html = "<p>" + " ".join(["word"] * 200) + "</p>"
    assert calculate_read_time(html) == 1


def test_calculate_read_time_sums_multiple_fields():
    a = " ".join(["a"] * 150)
    b = " ".join(["b"] * 150)
    # 300 words total -> 2 minutes.
    assert calculate_read_time(a, b) == 2


# --- count_supporting_alerts ------------------------------------------------

def test_count_supporting_alerts_objects():
    alerts = [
        {"url": "https://example.com/1", "title": "One"},
        {"url": "https://example.com/2"},
    ]
    assert count_supporting_alerts(alerts) == 2


def test_count_supporting_alerts_ignores_invalid_entries():
    alerts = [
        {"url": "https://example.com/1"},
        {"url": ""},          # blank url -> ignored
        {"title": "no url"},  # missing url -> ignored
        "",                     # blank string -> ignored
        "https://example.com/plain",  # bare url string -> counted
        123,                    # wrong type -> ignored
    ]
    assert count_supporting_alerts(alerts) == 2


def test_count_supporting_alerts_non_list_returns_zero():
    assert count_supporting_alerts(None) == 0
    assert count_supporting_alerts("not-a-list") == 0
    assert count_supporting_alerts({"url": "x"}) == 0
