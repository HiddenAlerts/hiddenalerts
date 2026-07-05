"""Tests for the centralised HTML sanitizer.

Proves dangerous HTML is removed while ordinary rich-text editor formatting is
preserved.
"""
from app.services.html_sanitizer import sanitize_html


# --- unsafe content is removed ---------------------------------------------

def test_removes_script_tag():
    out = sanitize_html("<p>hi</p><script>alert('x')</script>")
    assert "<script" not in out
    assert "alert" not in out
    assert "<p>hi</p>" in out


def test_removes_event_handler_attributes():
    out = sanitize_html('<p onclick="steal()">click</p>')
    assert "onclick" not in out
    assert ">click</p>" in out


def test_removes_inline_style():
    out = sanitize_html('<p style="position:fixed">x</p>')
    assert "style" not in out


def test_strips_javascript_url_scheme():
    out = sanitize_html('<a href="javascript:alert(1)">bad</a>')
    assert "javascript:" not in out


def test_strips_data_uri_scheme():
    out = sanitize_html('<a href="data:text/html,<script>1</script>">x</a>')
    assert "data:" not in out


def test_disallowed_tags_dropped():
    out = sanitize_html("<iframe src='https://evil'></iframe><img src=x>hello")
    assert "<iframe" not in out
    assert "<img" not in out
    assert "hello" in out


# --- allowed editor formatting is kept -------------------------------------

def test_keeps_headings_paragraphs_and_breaks():
    html = "<h2>Title</h2><p>Line one<br>Line two</p>"
    out = sanitize_html(html)
    assert "<h2>Title</h2>" in out
    assert "<p>Line one" in out
    assert "<br>" in out


def test_keeps_bold_italic_and_lists():
    html = "<ul><li><strong>Bold</strong> and <em>italic</em></li></ul>"
    out = sanitize_html(html)
    assert "<ul>" in out and "<li>" in out
    assert "<strong>Bold</strong>" in out
    assert "<em>italic</em>" in out


def test_keeps_safe_links_and_hardens_rel():
    out = sanitize_html('<a href="https://example.com" title="ex">link</a>')
    assert 'href="https://example.com"' in out
    assert "noopener" in out  # rel hardening applied


def test_keeps_mailto_links():
    out = sanitize_html('<a href="mailto:a@b.com">mail</a>')
    assert "mailto:a@b.com" in out


# --- null / empty handling --------------------------------------------------

def test_none_passes_through():
    assert sanitize_html(None) is None


def test_blank_returns_empty_string():
    assert sanitize_html("   ") == ""
