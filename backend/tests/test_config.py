"""Tests for app/config.py::resolve_cors_origins.

Every test passes both cors_allowed_origins and frontend_base_url explicitly
so results don't depend on whatever the local .env happens to contain.
"""
from __future__ import annotations

from app.config import Settings, resolve_cors_origins


def test_explicit_origins_are_split_stripped_and_deduped():
    settings = Settings(
        cors_allowed_origins=" https://hiddenalerts.com/, http://localhost:3000 ,https://hiddenalerts.com",
        frontend_base_url="",
    )
    assert resolve_cors_origins(settings) == [
        "https://hiddenalerts.com", "http://localhost:3000",
    ]


def test_empty_entries_between_commas_are_ignored():
    settings = Settings(
        cors_allowed_origins="https://hiddenalerts.com,,http://localhost:3000,",
        frontend_base_url="",
    )
    assert resolve_cors_origins(settings) == [
        "https://hiddenalerts.com", "http://localhost:3000",
    ]


def test_falls_back_to_frontend_base_url_when_cors_allowed_origins_is_unset():
    settings = Settings(cors_allowed_origins="", frontend_base_url="https://hiddenalerts.com/")
    assert resolve_cors_origins(settings) == ["https://hiddenalerts.com"]


def test_falls_back_to_wildcard_when_neither_is_configured():
    settings = Settings(cors_allowed_origins="", frontend_base_url="")
    assert resolve_cors_origins(settings) == ["*"]


def test_never_adds_a_wildcard_alongside_explicit_origins():
    settings = Settings(cors_allowed_origins="https://hiddenalerts.com", frontend_base_url="")
    assert "*" not in resolve_cors_origins(settings)


def test_explicit_origins_take_precedence_over_frontend_base_url():
    settings = Settings(
        cors_allowed_origins="https://hiddenalerts.com,http://localhost:3000",
        frontend_base_url="https://hiddenalerts.vercel.app",
    )
    assert resolve_cors_origins(settings) == [
        "https://hiddenalerts.com", "http://localhost:3000",
    ]


def test_a_cors_allowed_origins_value_of_only_commas_falls_back_to_frontend_base_url():
    settings = Settings(cors_allowed_origins=" , , ", frontend_base_url="https://hiddenalerts.com")
    assert resolve_cors_origins(settings) == ["https://hiddenalerts.com"]


def test_does_not_mutate_the_settings_object():
    settings = Settings(cors_allowed_origins="https://hiddenalerts.com,http://localhost:3000")
    before = settings.cors_allowed_origins
    resolve_cors_origins(settings)
    assert settings.cors_allowed_origins == before
