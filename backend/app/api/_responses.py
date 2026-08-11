"""Shared OpenAPI response documentation for authentication failures.

These dicts are attached at ``include_router(...)`` level (and, for the one
router whose routes differ, on the individual route) so Swagger tells the truth
about what a protected operation can return without copying boilerplate into
every endpoint.

Documentation only — nothing here changes a status code, a payload or an
authorization decision. Each entry mirrors what the deployed dependencies
already raise:

* ``get_current_user`` / ``get_current_subscriber`` → 401 with ``{"detail": ...}``
* ``require_admin`` → 403 ``{"detail": "Admin access required"}``
* ``require_active_subscription`` → 403 ``{"detail": "active_subscription_required"}``

The 403 entries are applied **only** where that dependency is actually in play.
``/api/v1/subscriber/me`` and ``/api/v1/subscriber/access``, for example,
authenticate the token but do not require a subscription, so they document 401
alone. ``get_current_active_user`` nominally raises 403 for an inactive account,
but ``get_current_user`` has already rejected inactive users with a 401, so that
branch is unreachable and is not documented as a possible response.
"""
from __future__ import annotations

from typing import Any

#: Missing, malformed or invalid credentials.
UNAUTHORIZED: dict[int | str, dict[str, Any]] = {
    401: {
        "description": (
            "Missing, invalid or expired token. Returned before any "
            "authorization or business rule is evaluated."
        ),
    },
}

#: Authenticated, but the user is not an admin.
FORBIDDEN_ADMIN: dict[int | str, dict[str, Any]] = {
    403: {
        "description": "Authenticated, but the account is not an admin.",
    },
}

#: Authenticated subscriber whose subscription does not currently grant access.
FORBIDDEN_SUBSCRIPTION: dict[int | str, dict[str, Any]] = {
    403: {
        "description": (
            "Valid subscriber token, but no subscription currently grants "
            "access (`active_subscription_required`)."
        ),
    },
}

#: Admin-protected routers: authentication plus a role check.
ADMIN_AUTH_RESPONSES = {**UNAUTHORIZED, **FORBIDDEN_ADMIN}

#: Subscriber routers where every route also requires an active subscription.
SUBSCRIBER_AUTH_RESPONSES = {**UNAUTHORIZED, **FORBIDDEN_SUBSCRIPTION}
