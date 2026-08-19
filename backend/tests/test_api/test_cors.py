"""Focused CORS regression coverage for app/config.py::resolve_cors_origins
and its wiring into app/main.py's CORSMiddleware (Production CORS Alignment).

app.main.app adds CORSMiddleware once, at import time, from whatever settings
existed then — so mutating `settings.cors_allowed_origins` afterwards and
hitting the real app would not exercise anything. Instead, these tests build a
small standalone FastAPI app wired with the exact same CORSMiddleware call
main.py makes (same allow_methods/allow_headers/allow_credentials), driven by
a throwaway Settings instance, and prove: both target origins pass preflight
and get the actual-request Allow-Origin header, an unrelated origin gets
neither, and Authorization stays allowed for preflight (Subscriber/Admin APIs
send it on every request).
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from httpx import ASGITransport, AsyncClient

from app.config import Settings, resolve_cors_origins

#: The exact value the CORS alignment task asks production to be configured
#: with: the production domain plus local frontend dev.
PRODUCTION_CORS_ALLOWED_ORIGINS = "https://hiddenalerts.com,http://localhost:3000"


def _cors_app(cors_allowed_origins: str, *, frontend_base_url: str = "") -> FastAPI:
    settings = Settings(
        cors_allowed_origins=cors_allowed_origins, frontend_base_url=frontend_base_url,
    )
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolve_cors_origins(settings),
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    return app


def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_preflight_allows_the_production_domain():
    app = _cors_app(PRODUCTION_CORS_ALLOWED_ORIGINS)
    async with _client(app) as client:
        resp = await client.options(
            "/ping",
            headers={
                "Origin": "https://hiddenalerts.com",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "https://hiddenalerts.com"


@pytest.mark.asyncio
async def test_preflight_allows_localhost_dev():
    app = _cors_app(PRODUCTION_CORS_ALLOWED_ORIGINS)
    async with _client(app) as client:
        resp = await client.options(
            "/ping",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:3000"


@pytest.mark.asyncio
async def test_actual_get_from_the_production_domain_gets_the_allow_header():
    app = _cors_app(PRODUCTION_CORS_ALLOWED_ORIGINS)
    async with _client(app) as client:
        resp = await client.get("/ping", headers={"Origin": "https://hiddenalerts.com"})
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "https://hiddenalerts.com"


@pytest.mark.asyncio
async def test_preflight_does_not_allow_an_unrelated_origin():
    app = _cors_app(PRODUCTION_CORS_ALLOWED_ORIGINS)
    async with _client(app) as client:
        resp = await client.options(
            "/ping",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
    # Starlette's CORSMiddleware still returns 200 for a disallowed preflight —
    # it just omits Access-Control-Allow-Origin, which is what makes the
    # browser block the real request that would follow.
    assert "access-control-allow-origin" not in resp.headers


@pytest.mark.asyncio
async def test_actual_get_from_an_unrelated_origin_gets_no_allow_header():
    app = _cors_app(PRODUCTION_CORS_ALLOWED_ORIGINS)
    async with _client(app) as client:
        resp = await client.get("/ping", headers={"Origin": "https://evil.example.com"})
    assert resp.status_code == 200  # not blocked server-side; the browser blocks it
    assert "access-control-allow-origin" not in resp.headers


@pytest.mark.asyncio
async def test_authorization_header_preflight_remains_supported():
    """Subscriber and Admin APIs send Authorization: Bearer <token> on every
    request — the preflight for that real authenticated request must pass."""
    app = _cors_app(PRODUCTION_CORS_ALLOWED_ORIGINS)
    async with _client(app) as client:
        resp = await client.options(
            "/ping",
            headers={
                "Origin": "https://hiddenalerts.com",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
    assert resp.status_code == 200
    assert "authorization" in resp.headers.get("access-control-allow-headers", "").lower()


@pytest.mark.asyncio
async def test_credentials_are_not_enabled_by_this_change():
    """Subscriber APIs use Bearer tokens, not cookies — CORS_ALLOWED_ORIGINS
    must not silently start advertising allow_credentials."""
    app = _cors_app(PRODUCTION_CORS_ALLOWED_ORIGINS)
    async with _client(app) as client:
        resp = await client.options(
            "/ping",
            headers={
                "Origin": "https://hiddenalerts.com",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert "access-control-allow-credentials" not in resp.headers


@pytest.mark.asyncio
async def test_unconfigured_cors_still_falls_back_to_frontend_base_url_origin():
    """Back-compat: with CORS_ALLOWED_ORIGINS unset, behavior matches the
    pre-existing single-origin FRONTEND_BASE_URL lock."""
    app = _cors_app("", frontend_base_url="https://hiddenalerts.vercel.app")
    async with _client(app) as client:
        allowed = await client.get(
            "/ping", headers={"Origin": "https://hiddenalerts.vercel.app"}
        )
        other = await client.get("/ping", headers={"Origin": "https://hiddenalerts.com"})
    assert allowed.headers["access-control-allow-origin"] == "https://hiddenalerts.vercel.app"
    assert "access-control-allow-origin" not in other.headers
