import pytest

from app.pipeline.normalizer import (
    compute_content_hash,
    compute_url_hash,
    extract_text_from_html,
    normalize_url,
    parse_date,
)


def test_normalize_url_strips_fragment():
    url = "https://example.com/article?id=1#section"
    assert "#section" not in normalize_url(url)


def test_normalize_url_strips_tracking_params():
    url = "https://example.com/article?id=1&utm_source=twitter&utm_medium=social"
    normalized = normalize_url(url)
    assert "utm_source" not in normalized
    assert "id=1" in normalized


def test_normalize_url_lowercases_scheme_and_host():
    url = "HTTPS://Example.COM/path"
    normalized = normalize_url(url)
    assert normalized.startswith("https://example.com")


def test_compute_url_hash_is_deterministic():
    url = "https://example.com/article?id=42"
    assert compute_url_hash(url) == compute_url_hash(url)


def test_compute_url_hash_strips_tracking():
    url1 = "https://example.com/article"
    url2 = "https://example.com/article?utm_source=rss"
    assert compute_url_hash(url1) == compute_url_hash(url2)


def test_compute_content_hash_is_deterministic():
    text = "This is a test article about fraud."
    assert compute_content_hash(text) == compute_content_hash(text)


def test_compute_content_hash_normalizes_whitespace():
    text1 = "This   is   a test"
    text2 = "This is a test"
    assert compute_content_hash(text1) == compute_content_hash(text2)


def test_compute_content_hash_case_insensitive():
    text1 = "SEC charges CEO with securities fraud"
    text2 = "sec charges ceo with securities fraud"
    assert compute_content_hash(text1) == compute_content_hash(text2)


def test_extract_text_from_html_removes_scripts():
    html = "<html><body><script>alert(1)</script><p>Hello world</p></body></html>"
    text = extract_text_from_html(html)
    assert "alert" not in text
    assert "Hello world" in text


def test_extract_text_from_html_empty():
    assert extract_text_from_html("") == ""


def test_parse_date_iso():
    dt = parse_date("2024-01-15T10:30:00Z")
    assert dt is not None
    assert dt.year == 2024
    assert dt.month == 1


def test_parse_date_none():
    assert parse_date(None) is None


def test_parse_date_invalid():
    assert parse_date("not a date") is None
