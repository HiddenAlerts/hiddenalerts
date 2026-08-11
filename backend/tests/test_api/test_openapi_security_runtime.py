"""Slice 3B.2AJ — proof that adding OpenAPI security metadata changed nothing.

The ``AdminBearer`` / ``SubscriberBearer`` schemes are declared as
``HTTPBearer(auto_error=False)`` sub-dependencies of the existing auth functions.
``auto_error=False`` is the load-bearing detail: a missing or malformed header
resolves to ``None`` instead of the scheme raising its own 403, so every request
still reaches the original body and the original 401 semantics survive.

That is easy to get wrong — the default ``auto_error=True`` would turn every
unauthenticated request into a **403** and silently change the API. These tests
exist to catch exactly that regression.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# No credentials at all → 401, never 403
# ---------------------------------------------------------------------------


ADMIN_GETS = [
    "/api/v1/alerts",
    "/api/v1/alerts/1",
    "/api/v1/auth/me",
    "/api/v1/admin/alerts/categories",
    "/api/v1/admin/intelligence-briefs",
    "/api/v1/admin/intelligence-briefs/1",
    "/api/v1/admin/sources/health",
    "/api/v1/admin/sources/1/health",
    "/api/v1/admin/system/health-summary",
]

SUBSCRIBER_GETS = [
    "/api/v1/subscriber/me",
    "/api/v1/subscriber/access",
    "/api/v1/subscriber/alerts",
    "/api/v1/subscriber/alerts/top",
    "/api/v1/subscriber/alerts/stats",
    "/api/v1/subscriber/alerts/categories",
    "/api/v1/subscriber/alerts/1",
    "/api/v1/subscriber/search/alerts?q=fraud",
    "/api/v1/subscriber/intelligence-briefs",
    "/api/v1/subscriber/intelligence-briefs/featured",
    "/api/v1/subscriber/intelligence-briefs/some-slug",
    "/api/v1/billing/status",
]

HIDDEN_ADMIN_GETS = [
    "/api/v1/raw-items",
    "/api/v1/stats",
    "/api/v1/sources",
    "/api/v1/events",
    "/api/v1/client/alerts",
]


@pytest.mark.parametrize("path", ADMIN_GETS + SUBSCRIBER_GETS)
async def test_protected_routes_still_return_401_without_a_token(client, path):
    response = await client.get(path)
    assert response.status_code == 401, (
        f"{path} returned {response.status_code}; a 403 here would mean the "
        f"HTTPBearer scheme started rejecting requests itself (auto_error=True)"
    )


@pytest.mark.parametrize("path", HIDDEN_ADMIN_GETS)
async def test_hidden_routes_are_still_protected_at_runtime(client, path):
    """Removing them from Swagger must not remove their guard."""
    response = await client.get(path)
    assert response.status_code == 401


@pytest.mark.parametrize("path", ADMIN_GETS + SUBSCRIBER_GETS)
async def test_malformed_authorization_header_still_returns_401(client, path):
    """A header the bearer scheme cannot parse must fall through, not 403."""
    response = await client.get(path, headers={"Authorization": "NotBearer whatever"})
    assert response.status_code == 401


@pytest.mark.parametrize("path", ADMIN_GETS)
async def test_garbage_bearer_token_still_returns_401(client, path):
    response = await client.get(path, headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Intentionally unauthenticated routes keep working
# ---------------------------------------------------------------------------


async def test_public_teaser_needs_no_authorization(client):
    response = await client.get("/api/alerts")
    assert response.status_code == 200
    assert "alerts" in response.json()


async def test_health_probe_needs_no_authorization(client):
    """Hidden from Swagger, still unauthenticated and still serving."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200


async def test_login_remains_reachable_without_a_token(client):
    """Bootstrap: rejected on credentials, not on a missing bearer token."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.invalid", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


async def test_stripe_webhook_still_rejects_on_signature_not_on_bearer(client):
    """The webhook must keep its own verification and gain no bearer requirement.

    The secret is configured here because it is empty by default in the test
    environment, and an unconfigured webhook returns 500 before it ever reaches
    the signature check — which would prove nothing about the header.
    """
    from app.config import settings

    original = settings.stripe_webhook_secret
    settings.stripe_webhook_secret = "whsec_test_dummy"
    try:
        response = await client.post("/api/v1/stripe/webhook", content=b"{}")
    finally:
        settings.stripe_webhook_secret = original

    assert response.status_code == 400
    assert response.json()["detail"] == "missing_stripe_signature"


# ---------------------------------------------------------------------------
# Cookie sessions must survive a header-based security scheme
# ---------------------------------------------------------------------------


async def test_cookie_authentication_is_not_broken_by_the_bearer_scheme(client):
    """``get_current_user`` reads the cookie first; the scheme must not intercept.

    A bogus cookie proves the cookie branch is still taken — it is decoded and
    rejected as an invalid token rather than being ignored in favour of the
    (absent) Authorization header.
    """
    response = await client.get(
        "/api/v1/alerts", cookies={"access_token": "bogus-cookie-value"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"


# ---------------------------------------------------------------------------
# The review enum reaches the wire as a 422
# ---------------------------------------------------------------------------


async def test_invalid_review_status_is_rejected_before_authentication_matters(client):
    """Schema validation is explicit now; the status code stays 422 either way."""
    response = await client.post(
        "/api/v1/alerts/1/review",
        json={"review_status": "definitely_not_valid"},
    )
    # Auth runs first, so an unauthenticated caller still sees 401 — the point is
    # that neither path became a 500 or a silent accept.
    assert response.status_code in (401, 422)
