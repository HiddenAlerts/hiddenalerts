"""Acquire and *verify* the two kinds of access token this platform uses.

The platform has two independent authentication systems:

* **Internal JWT** — `POST /api/v1/auth/login` with a JSON `{email, password}`
  body, issued and validated by this backend. Used by Admin and Client APIs.
* **Supabase** — an RS256/ES256 JWT obtained from the Supabase password grant and
  validated by this backend against the project's JWKS. Used by Subscriber APIs.

A login returning HTTP 200 is **not** treated as success. A token is only
accepted once it has demonstrably authorized a real request, because the
interesting failures — a valid identity that is not an admin, or a valid
Supabase user whose subscription lapsed — all return 200 at the login step.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from scripts.e2e.common import (
    AssertionFailure,
    AuthError,
    ConfigError,
    E2EConfig,
    Exit,
    fingerprint,
    load_config,
    make_client,
    parse_json,
    redact,
    request_with_retry,
)

#: Internal JWT login. JSON body, not OAuth2 form data — verified against
#: `app/api/auth.py::json_login` and `app/schemas/auth.py::LoginRequest`.
ADMIN_LOGIN_PATH = "/api/v1/auth/login"

#: Read-only admin endpoint used to prove a token really is an admin token.
#: `/api/v1/sources` exists in the currently deployed release, so this works
#: before *and* after the pending deployment.
ADMIN_VERIFY_PATH = "/api/v1/sources"

#: Preferred verification endpoint once the pending release is deployed.
ADMIN_VERIFY_PATH_POST_DEPLOY = "/api/v1/admin/system/health-summary"

#: Proves both a valid Supabase identity and an active subscription.
SUBSCRIBER_VERIFY_PATH = "/api/v1/subscriber/alerts"

#: Supabase password grant.
SUPABASE_TOKEN_PATH = "/auth/v1/token"


@dataclass
class TokenBundle:
    """A verified token. Never serialized, never written to disk."""

    kind: str
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime | None = None
    verified_endpoint: str = ""
    verified_status: int | None = None
    subject: str = ""

    @property
    def header(self) -> dict[str, str]:
        return {"Authorization": f"{self.token_type.capitalize()} {self.access_token}"}

    def safe_summary(self) -> dict[str, Any]:
        """The only representation permitted in output or a report."""
        return {
            "kind": self.kind,
            "token_type": self.token_type,
            "fingerprint": fingerprint(self.access_token),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "expires_in_seconds": (
                int((self.expires_at - datetime.now(timezone.utc)).total_seconds())
                if self.expires_at else None
            ),
            "verified_endpoint": self.verified_endpoint,
            "verified_status": self.verified_status,
            "subject_fingerprint": fingerprint(self.subject) if self.subject else None,
        }

    def __repr__(self) -> str:  # pragma: no cover - defensive
        return f"TokenBundle(kind={self.kind!r}, fingerprint={fingerprint(self.access_token)!r})"


def _decode_unverified_claims(token: str) -> dict[str, Any]:
    """Read JWT claims **without** verifying the signature.

    Only ever used for operator-facing diagnostics such as the expiry shown by
    `--check`. Nothing security-relevant is decided from this: the backend
    performs real signature validation on every request.
    """
    try:
        segment = token.split(".")[1]
        padded = segment + "=" * (-len(segment) % 4)
        return json.loads(base64.urlsafe_b64decode(padded))
    except Exception:
        return {}


def _expiry_from_token(token: str) -> datetime | None:
    exp = _decode_unverified_claims(token).get("exp")
    if not isinstance(exp, (int, float)):
        return None
    return datetime.fromtimestamp(exp, tz=timezone.utc)


def _require_token_shape(payload: Any, field: str, source: str) -> str:
    if not isinstance(payload, dict):
        raise AuthError(f"{source}: expected a JSON object, got {type(payload).__name__}")
    token = payload.get(field)
    if not token or not isinstance(token, str):
        raise AuthError(f"{source}: response has no usable {field!r} field")
    if token.count(".") != 2:
        raise AuthError(f"{source}: {field!r} is not a JWT (expected three segments)")
    return token


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------


async def get_admin_access_token(
    config: E2EConfig,
    client: httpx.AsyncClient | None = None,
    *,
    verify_path: str | None = None,
) -> TokenBundle:
    """Log in as the admin user and prove the token carries admin authorization.

    Distinguishes, by HTTP status:

    * 401 at login  → invalid credentials;
    * 200 at login but 403 at verification → valid identity, **not an admin**;
    * 401 at verification → token rejected (expired, malformed, wrong secret);
    * anything else → an endpoint failure unrelated to authentication.
    """
    config.require_admin_credentials()
    owns_client = client is None
    client = client or make_client(config)
    try:
        response, _ = await request_with_retry(
            client, "POST", ADMIN_LOGIN_PATH,
            json={"email": config.admin_email, "password": config.admin_password},
        )
        if response.status_code == 401:
            raise AuthError("admin login rejected: invalid email or password")
        if response.status_code != 200:
            raise AuthError(
                f"admin login failed with HTTP {response.status_code} "
                f"(not an authentication verdict — check the API is healthy)"
            )

        payload = parse_json(response, "admin login")
        token = _require_token_shape(payload, "access_token", "admin login")
        token_type = payload.get("token_type") or "bearer"

        # The login response embeds the user; a non-admin role is worth naming
        # early, but it is NOT what decides success.
        embedded_role = (payload.get("user") or {}).get("role")

        bundle = TokenBundle(
            kind="admin",
            access_token=token,
            token_type=token_type,
            expires_at=_expiry_from_token(token),
            subject=str((payload.get("user") or {}).get("id", "")),
        )

        path = verify_path or ADMIN_VERIFY_PATH
        verify, _ = await request_with_retry(
            client, "GET", path, headers=bundle.header
        )
        if verify.status_code == 403:
            raise AuthError(
                f"admin token is valid but not authorized for admin APIs "
                f"(role={embedded_role!r}); {path} returned 403"
            )
        if verify.status_code == 401:
            raise AuthError(f"admin token rejected at {path} (401)")
        if verify.status_code == 404:
            raise AuthError(
                f"admin verification endpoint {path} does not exist in this "
                f"release — this is not an authentication failure; choose an "
                f"endpoint that is deployed"
            )
        if verify.status_code != 200:
            raise AuthError(
                f"admin verification at {path} returned HTTP {verify.status_code}"
            )

        bundle.verified_endpoint = path
        bundle.verified_status = verify.status_code
        return bundle
    finally:
        if owns_client:
            await client.aclose()


# ---------------------------------------------------------------------------
# Subscriber
# ---------------------------------------------------------------------------


async def get_subscriber_access_token(
    config: E2EConfig,
    client: httpx.AsyncClient | None = None,
    *,
    email: str | None = None,
    password: str | None = None,
    expect_active: bool = True,
) -> TokenBundle:
    """Obtain a Supabase access token and prove the subscription is active.

    Uses the password grant with the **publishable/anon** key. The service-role
    key is rejected at config load; it is never sent here.

    With ``expect_active=False`` a 403 ``active_subscription_required`` at the
    verification step is the *expected* outcome and is returned as a bundle with
    ``verified_status=403`` — that is how the inactive-subscriber negative test
    distinguishes "lapsed subscription" from "bad password".
    """
    config.require_subscriber_credentials()
    email = email or config.subscriber_email
    password = password or config.subscriber_password

    owns_client = client is None
    client = client or make_client(config)
    supabase = httpx.AsyncClient(
        base_url=config.supabase_project_url,
        timeout=httpx.Timeout(config.request_timeout_seconds),
    )
    try:
        try:
            response = await supabase.post(
                SUPABASE_TOKEN_PATH,
                params={"grant_type": "password"},
                headers={
                    "apikey": config.supabase_publishable_key,
                    "Content-Type": "application/json",
                },
                json={"email": email, "password": password},
            )
        except httpx.HTTPError as exc:
            # A transport failure reaching Supabase is not an authentication
            # verdict, and must not abort a whole smoke run — surface it as an
            # AuthError so the caller records one failed check and continues.
            raise AuthError(
                f"could not reach the Supabase auth endpoint: "
                f"{type(exc).__name__}"
            ) from None
        if response.status_code in (400, 401):
            raise AuthError(
                "Supabase login rejected: invalid subscriber credentials "
                f"(HTTP {response.status_code})"
            )
        if response.status_code != 200:
            raise AuthError(
                f"Supabase login failed with HTTP {response.status_code} "
                f"(not an authentication verdict)"
            )

        payload = parse_json(response, "Supabase login")
        token = _require_token_shape(payload, "access_token", "Supabase login")

        # A refresh token is present in the grant response. It is deliberately
        # neither stored on the bundle nor logged — it would outlive the run.
        claims = _decode_unverified_claims(token)
        bundle = TokenBundle(
            kind="subscriber",
            access_token=token,
            token_type=payload.get("token_type") or "bearer",
            expires_at=_expiry_from_token(token),
            subject=str(claims.get("sub", "")),
        )

        verify, _ = await request_with_retry(
            client, "GET", SUBSCRIBER_VERIFY_PATH, headers=bundle.header
        )
        bundle.verified_endpoint = SUBSCRIBER_VERIFY_PATH
        bundle.verified_status = verify.status_code

        if verify.status_code == 403:
            detail = ""
            try:
                detail = str(parse_json(verify, "subscriber verify").get("detail", ""))
            except Exception:
                pass
            if not expect_active:
                return bundle
            raise AuthError(
                "Supabase identity is valid but the subscription is not active "
                f"({detail or 'active_subscription_required'})"
            )
        if verify.status_code == 401:
            raise AuthError(
                f"Supabase token rejected by the backend at {SUBSCRIBER_VERIFY_PATH} "
                f"(401) — check issuer/audience/JWKS configuration"
            )
        if verify.status_code != 200:
            raise AuthError(
                f"subscriber verification returned HTTP {verify.status_code}"
            )
        if not expect_active:
            raise AuthError(
                "expected an inactive subscription but the account has active access"
            )
        return bundle
    finally:
        await supabase.aclose()
        if owns_client:
            await client.aclose()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.e2e.auth_tokens",
        description="Acquire and verify an access token. Prints no secrets by default.",
    )
    parser.add_argument("--kind", choices=("admin", "subscriber"), required=True)
    parser.add_argument("--check", action="store_true",
                        help="acquire and verify, then report status only")
    parser.add_argument("--env-file", help="path to an env file outside the repository")
    parser.add_argument("--verify-path",
                        help="override the admin verification endpoint")
    parser.add_argument(
        "--print-token", action="store_true",
        help="DANGEROUS, local targets only: print the raw token to stdout",
    )
    return parser


async def _main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        config = load_config(
            args.env_file,
            require_admin=args.kind == "admin",
            require_subscriber=args.kind == "subscriber",
        )
    except ConfigError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return int(Exit.CONFIG_ERROR)

    if args.print_token and config.is_production:
        print(
            "refusing --print-token against a production target. "
            "The production E2E runner never needs the raw token.",
            file=sys.stderr,
        )
        return int(Exit.SAFETY_REFUSED)

    try:
        if args.kind == "admin":
            bundle = await get_admin_access_token(config, verify_path=args.verify_path)
        else:
            bundle = await get_subscriber_access_token(config)
    except AuthError as exc:
        print(f"authentication FAILED: {redact(str(exc))}", file=sys.stderr)
        return int(Exit.AUTH_FAILED)
    except Exception as exc:  # noqa: BLE001 - message is redacted before display
        print(f"unexpected error: {redact(str(exc))}", file=sys.stderr)
        return int(Exit.ASSERTION_FAILED)

    print(f"authentication SUCCEEDED for {bundle.kind}")
    for key, value in bundle.safe_summary().items():
        if value is not None:
            print(f"  {key}: {value}")

    if args.print_token:
        print(
            "\n!! WARNING: printing a live access token. Do not paste this "
            "anywhere. Rotate the credential if it leaves this terminal.",
            file=sys.stderr,
        )
        print(bundle.access_token)

    return int(Exit.OK)


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_main(argv))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
