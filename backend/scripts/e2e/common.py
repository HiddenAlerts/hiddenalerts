"""Shared plumbing for the E2E harness: config, guards, redaction, reporting.

Three jobs, in order of how much damage they prevent:

1. **Refuse to run against the wrong thing.** A production target must be HTTPS,
   must not be localhost, and must be on the allowlist.
2. **Never let a secret escape.** Redaction is applied to errors and to every
   report before it is written, and the writer re-scans the serialized bytes as a
   last line of defence.
3. Make results boring and comparable — one result shape, one report shape.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from pathlib import Path
from typing import Any, Iterable, Mapping

import httpx

# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------


class Exit(IntEnum):
    """Deterministic exit codes. Documented in README.md; do not renumber."""

    OK = 0                  #: every assertion passed
    ASSERTION_FAILED = 1    #: an assertion or an API call failed
    CONFIG_ERROR = 2        #: missing/invalid environment or configuration
    AUTH_FAILED = 3         #: could not obtain or verify a token
    SAFETY_REFUSED = 4      #: a production safety guard refused to proceed
    COLLECTOR_TIMEOUT = 5   #: a triggered run did not reach a terminal state
    STOP_CONDITION = 6      #: an explicit stop condition fired


class ConfigError(RuntimeError):
    """Environment or configuration problem. Maps to Exit.CONFIG_ERROR."""


class AuthError(RuntimeError):
    """Authentication or authorization problem. Maps to Exit.AUTH_FAILED."""


class SafetyRefusal(RuntimeError):
    """A guard refused to proceed. Maps to Exit.SAFETY_REFUSED."""


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------

REDACTED = "<redacted>"

#: Anything shaped like a JWT, however it reached us.
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]*")
#: `Authorization: Bearer x`, `apikey: x`, `password=x`, `token": "x"`, …
_HEADER_RE = re.compile(
    r"(?i)\b(authorization|apikey|api[-_]?key|cookie|set-cookie)\b\s*[:=]\s*"
    r"[\"']?[^\s,;\"'}\]]+"
)
_SECRETISH_RE = re.compile(
    r"(?i)\b(password|passwd|secret|refresh_token|access_token|service_role|"
    r"anon_key|publishable_key|jwt_secret|api_key)\b"
    r"([\"']?\s*[:=]\s*[\"']?)([^\s,;\"'}\]]+)"
)
#: postgres://user:pass@host/db and friends.
_DB_URL_RE = re.compile(r"(?i)\b(postgres(?:ql)?(?:\+\w+)?|mysql|redis)://[^\s\"']+")
#: Bare IPv4 addresses.
_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

#: Keys whose values are always dropped, whatever they look like.
_FORBIDDEN_KEYS = frozenset(
    {
        "authorization", "apikey", "api_key", "cookie", "cookies", "set-cookie",
        "password", "passwd", "access_token", "refresh_token", "id_token",
        "token", "secret", "jwt", "supabase_publishable_key", "supabase_anon_key",
        "service_role_key", "database_url", "headers", "env", "environ",
    }
)


def redact(text: str) -> str:
    """Strip anything that looks like a credential out of free text."""
    if not text:
        return text
    out = _JWT_RE.sub(REDACTED, text)
    out = _DB_URL_RE.sub(REDACTED, out)
    out = _HEADER_RE.sub(lambda m: f"{m.group(1)}: {REDACTED}", out)
    out = _SECRETISH_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}{REDACTED}", out)
    out = _IPV4_RE.sub(REDACTED, out)
    return out


def scrub(value: Any) -> Any:
    """Recursively redact a structure destined for a report.

    Forbidden keys are dropped entirely rather than redacted — a key that should
    never appear is better absent than present-and-masked, because the latter
    invites someone to "just unmask it for debugging".
    """
    if isinstance(value, Mapping):
        return {
            key: scrub(item)
            for key, item in value.items()
            if str(key).strip().lower() not in _FORBIDDEN_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [scrub(item) for item in value]
    if isinstance(value, str):
        return redact(value)
    return value


def fingerprint(secret: str) -> str:
    """A stable, non-reversible handle for a token, safe to print and store."""
    if not secret:
        return "sha256:<empty>"
    return "sha256:" + hashlib.sha256(secret.encode("utf-8")).hexdigest()[:12]


def mask(secret: str, keep: int = 4) -> str:
    """`eyJh…(len=812)` — enough to tell two tokens apart, useless to an attacker."""
    if not secret:
        return "<empty>"
    return f"{secret[:keep]}…(len={len(secret)})"


def contains_secret(text: str) -> str | None:
    """Return a description of the first secret-shaped thing found, else None.

    Used as the pre-write gate on every report.
    """
    if _JWT_RE.search(text):
        return "JWT-shaped value"
    if _DB_URL_RE.search(text):
        return "database URL"
    if _HEADER_RE.search(text):
        return "authorization/apikey/cookie header"
    if _IPV4_RE.search(text):
        return "IPv4 address"
    return None


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

#: Hosts an E2E run may target when E2E_TARGET_ENV=production.
DEFAULT_ALLOWED_PRODUCTION_HOSTS = ("api.hiddenalerts.com", "hiddenalerts.com")

#: Substrings that mean "you left the example value in".
_PLACEHOLDERS = (
    "changeme", "change-me", "your-", "your_", "xxx", "<", ">", "example.com",
    "placeholder", "todo", "fixme", "replace-me", "replaceme", "dummy",
)

#: Primary name → accepted aliases. The primary names match this repository's
#: existing convention (`ADMIN_EMAIL`/`ADMIN_PASSWORD` already appear in
#: `.env.example`, and `SUPABASE_PROJECT_URL` matches `settings.supabase_project_url`).
#: The `E2E_`-prefixed aliases are accepted so an operator can keep harness
#: credentials in a file that never collides with the application's own env.
ENV_ALIASES: dict[str, tuple[str, ...]] = {
    "E2E_API_BASE_URL": ("E2E_API_BASE_URL", "API_BASE_URL"),
    "E2E_TARGET_ENV": ("E2E_TARGET_ENV", "TARGET_ENV"),
    "ADMIN_EMAIL": ("ADMIN_EMAIL", "E2E_ADMIN_EMAIL", "E2E_ADMIN_USERNAME"),
    "ADMIN_PASSWORD": ("ADMIN_PASSWORD", "E2E_ADMIN_PASSWORD"),
    "TEST_SUBSCRIBER_EMAIL": ("TEST_SUBSCRIBER_EMAIL", "E2E_SUBSCRIBER_EMAIL"),
    "TEST_SUBSCRIBER_PASSWORD": ("TEST_SUBSCRIBER_PASSWORD", "E2E_SUBSCRIBER_PASSWORD"),
    "SUPABASE_PROJECT_URL": ("SUPABASE_PROJECT_URL", "SUPABASE_URL"),
    "SUPABASE_PUBLISHABLE_KEY": (
        "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_ANON_KEY", "SUPABASE_PUBLIC_KEY",
    ),
    # Optional inactive-subscriber account, for the negative subscription test.
    "TEST_INACTIVE_SUBSCRIBER_EMAIL": ("TEST_INACTIVE_SUBSCRIBER_EMAIL",),
    "TEST_INACTIVE_SUBSCRIBER_PASSWORD": ("TEST_INACTIVE_SUBSCRIBER_PASSWORD",),
}


#: Where reports land by default: `<backend>/reports`, resolved from this file's
#: location rather than the process working directory. A command run from
#: `backend/` and one run from the repository root must write to the same place.
BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_DIR = BACKEND_ROOT / "reports"


@dataclass
class E2EConfig:
    """Validated harness configuration. Holds secrets; never serialize it."""

    api_base_url: str
    target_env: str
    admin_email: str = ""
    admin_password: str = ""
    subscriber_email: str = ""
    subscriber_password: str = ""
    supabase_project_url: str = ""
    supabase_publishable_key: str = ""
    inactive_subscriber_email: str = ""
    inactive_subscriber_password: str = ""
    request_timeout_seconds: float = 30.0
    poll_interval_seconds: float = 5.0
    run_timeout_seconds: float = 900.0
    report_dir: Path = field(default_factory=lambda: DEFAULT_REPORT_DIR)
    allowed_production_hosts: tuple[str, ...] = DEFAULT_ALLOWED_PRODUCTION_HOSTS
    #: Which credential scopes this config was loaded with.
    loaded_scopes: tuple[str, ...] = ()

    @property
    def is_production(self) -> bool:
        return self.target_env.strip().lower() == "production"

    @property
    def has_admin_credentials(self) -> bool:
        return bool(self.admin_email and self.admin_password)

    @property
    def has_subscriber_credentials(self) -> bool:
        return bool(
            self.subscriber_email and self.subscriber_password
            and self.supabase_project_url and self.supabase_publishable_key
        )

    def require_admin_credentials(self) -> None:
        if not self.has_admin_credentials:
            raise ConfigError("admin credentials were not loaded for this command")

    def require_subscriber_credentials(self) -> None:
        if not self.has_subscriber_credentials:
            raise ConfigError("subscriber credentials were not loaded for this command")

    @property
    def has_inactive_subscriber(self) -> bool:
        return bool(self.inactive_subscriber_email and self.inactive_subscriber_password)

    def public_summary(self) -> dict[str, Any]:
        """The only representation of this config allowed into a report."""
        summary: dict[str, Any] = {
            "api_base_url": self.api_base_url,
            "target_env": self.target_env,
            "credential_scopes": list(self.loaded_scopes),
            "request_timeout_seconds": self.request_timeout_seconds,
        }
        if self.has_admin_credentials:
            summary["admin_email_fingerprint"] = fingerprint(self.admin_email)
        if self.has_subscriber_credentials:
            summary["supabase_project_url"] = self.supabase_project_url
            summary["subscriber_email_fingerprint"] = fingerprint(self.subscriber_email)
            summary["inactive_subscriber_configured"] = self.has_inactive_subscriber
        return summary

    def __repr__(self) -> str:  # pragma: no cover - defensive
        return f"E2EConfig(api_base_url={self.api_base_url!r}, target_env={self.target_env!r}, …)"


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse a `KEY=value` file. Comments, blanks and `export ` are tolerated.

    Deliberately minimal: no interpolation, no command substitution. An env file
    is data, not a script.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"cannot read env file {path}: {exc.strerror}") from None

    values: dict[str, str] = {}
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        if stripped.startswith("export "):
            stripped = stripped[len("export "):].lstrip()
        key, _, value = stripped.partition("=")
        value = value.strip().strip('"').strip("'")
        values[key.strip()] = value
    return values


def _lookup(name: str, overlay: Mapping[str, str]) -> str:
    """Environment first, then the operator's env file, across accepted aliases."""
    for alias in ENV_ALIASES.get(name, (name,)):
        value = os.environ.get(alias) or overlay.get(alias)
        if value:
            return value.strip()
    return ""


def _reject_placeholder(name: str, value: str) -> None:
    lowered = value.lower()
    if any(token in lowered for token in _PLACEHOLDERS):
        raise ConfigError(
            f"{name} still holds a placeholder value — fill in the real value "
            f"or unset it (value not shown)"
        )


#: Credentials each authentication scope needs.
ADMIN_REQUIRED = ("ADMIN_EMAIL", "ADMIN_PASSWORD")
SUBSCRIBER_REQUIRED = (
    "TEST_SUBSCRIBER_EMAIL", "TEST_SUBSCRIBER_PASSWORD",
    "SUPABASE_PROJECT_URL", "SUPABASE_PUBLISHABLE_KEY",
)


def load_config(
    env_file: str | Path | None = None,
    *,
    require_admin: bool = True,
    require_subscriber: bool = True,
) -> E2EConfig:
    """Build a validated config from the environment and an optional env file.

    Only the credentials a command actually uses are required. `auth_tokens
    --kind admin` must not demand Supabase keys, and `collector_stage` must not
    demand a subscriber account — an operator should never have to supply a
    credential a command will not send.

    Unrequested credentials are **not** loaded at all rather than defaulted to
    empty strings, so a command cannot quietly attempt an auth flow it was not
    configured for. Target validation runs in every mode.

    The env file is **only** ever the one the operator names. Nothing here reads
    `.env` or `.env.production` — the application's own environment must not be
    picked up by accident, because that is how a harness ends up pointed at a
    database it was never meant to touch.
    """
    overlay: dict[str, str] = {}
    if env_file is not None:
        path = Path(env_file)
        forbidden = {".env", ".env.production", ".env.local"}
        if path.name in forbidden:
            raise ConfigError(
                f"refusing to load {path.name}: the harness never reads the "
                f"application's own environment file. Use a dedicated file."
            )
        overlay = parse_env_file(path)

    if not (require_admin or require_subscriber):
        raise ConfigError("at least one credential scope must be required")

    required = ["E2E_API_BASE_URL"]
    scopes: list[str] = []
    if require_admin:
        required.extend(ADMIN_REQUIRED)
        scopes.append("admin")
    if require_subscriber:
        required.extend(SUBSCRIBER_REQUIRED)
        scopes.append("subscriber")

    resolved = {name: _lookup(name, overlay) for name in required}
    missing = sorted(name for name, value in resolved.items() if not value)
    if missing:
        raise ConfigError(
            "missing required environment variables: " + ", ".join(missing)
            + " (values are never printed)"
        )
    for name, value in resolved.items():
        _reject_placeholder(name, value)

    target_env = _lookup("E2E_TARGET_ENV", overlay) or "production"
    allowed_hosts = tuple(
        host.strip().lower()
        for host in (
            os.environ.get("E2E_ALLOWED_HOSTS")
            or overlay.get("E2E_ALLOWED_HOSTS")
            or ",".join(DEFAULT_ALLOWED_PRODUCTION_HOSTS)
        ).split(",")
        if host.strip()
    )

    def _number(name: str, default: float) -> float:
        raw = os.environ.get(name) or overlay.get(name)
        if not raw:
            return default
        try:
            return float(raw)
        except ValueError:
            raise ConfigError(f"{name} must be a number") from None

    configured_report_dir = (
        os.environ.get("E2E_REPORT_DIR") or overlay.get("E2E_REPORT_DIR")
    )

    config = E2EConfig(
        api_base_url=resolved["E2E_API_BASE_URL"].rstrip("/"),
        target_env=target_env,
        admin_email=resolved.get("ADMIN_EMAIL", ""),
        admin_password=resolved.get("ADMIN_PASSWORD", ""),
        subscriber_email=resolved.get("TEST_SUBSCRIBER_EMAIL", ""),
        subscriber_password=resolved.get("TEST_SUBSCRIBER_PASSWORD", ""),
        supabase_project_url=resolved.get("SUPABASE_PROJECT_URL", "").rstrip("/"),
        supabase_publishable_key=resolved.get("SUPABASE_PUBLISHABLE_KEY", ""),
        inactive_subscriber_email=(
            _lookup("TEST_INACTIVE_SUBSCRIBER_EMAIL", overlay) if require_subscriber else ""
        ),
        inactive_subscriber_password=(
            _lookup("TEST_INACTIVE_SUBSCRIBER_PASSWORD", overlay) if require_subscriber else ""
        ),
        request_timeout_seconds=_number("E2E_REQUEST_TIMEOUT_SECONDS", 30.0),
        poll_interval_seconds=_number("E2E_POLL_INTERVAL_SECONDS", 5.0),
        run_timeout_seconds=_number("E2E_RUN_TIMEOUT_SECONDS", 900.0),
        report_dir=(
            Path(configured_report_dir).expanduser()
            if configured_report_dir else DEFAULT_REPORT_DIR
        ),
        allowed_production_hosts=allowed_hosts,
        loaded_scopes=tuple(scopes),
    )
    validate_target(config)
    if require_subscriber:
        _validate_supabase_key(config)
    return config


def validate_target(config: E2EConfig) -> None:
    """Refuse an unsafe or unexpected target. Raises ConfigError."""
    url = httpx.URL(config.api_base_url)
    host = (url.host or "").lower()

    if not host:
        raise ConfigError(f"E2E_API_BASE_URL has no host: {config.api_base_url}")

    if config.is_production:
        if url.scheme != "https":
            raise ConfigError(
                f"production target must use HTTPS, got {url.scheme!r}://{host}"
            )
        if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local"):
            raise ConfigError(
                f"refusing to treat {host} as production — check E2E_TARGET_ENV"
            )
        if host not in config.allowed_production_hosts:
            raise ConfigError(
                f"{host} is not an allowed production host "
                f"({', '.join(config.allowed_production_hosts)}). "
                f"Set E2E_ALLOWED_HOSTS to override deliberately."
            )


def _validate_supabase_key(config: E2EConfig) -> None:
    """Refuse a service-role key. It must never be used for subscriber login.

    Supabase keys are JWTs carrying a `role` claim. A service-role key bypasses
    row-level security entirely, so handing one to a login flow would both defeat
    the test and put an all-powerful credential on the wire.
    """
    key = config.supabase_publishable_key
    if key.count(".") == 2 and key.startswith("eyJ"):
        import base64

        try:
            payload_segment = key.split(".")[1]
            padded = payload_segment + "=" * (-len(payload_segment) % 4)
            claims = json.loads(base64.urlsafe_b64decode(padded))
        except Exception:  # pragma: no cover - malformed key handled downstream
            return
        if str(claims.get("role", "")).lower() == "service_role":
            raise ConfigError(
                "SUPABASE_PUBLISHABLE_KEY is a service-role key. The harness "
                "refuses it: subscriber login must use the publishable/anon key."
            )


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

#: Methods the harness may retry. POST is deliberately absent: a retried trigger
#: could start a second collection run.
_RETRYABLE_METHODS = frozenset({"GET", "HEAD"})


def make_client(config: E2EConfig, **kwargs: Any) -> httpx.AsyncClient:
    """An httpx client configured for the harness.

    Cookies are **disabled**. The admin login endpoint sets an HTTP-only session
    cookie, and `get_current_user` reads the cookie *before* the Authorization
    header — so a persistent jar would silently authenticate the negative tests
    ("no token → 401") and they would pass while proving nothing.
    """
    kwargs.setdefault("base_url", config.api_base_url)
    kwargs.setdefault("timeout", httpx.Timeout(config.request_timeout_seconds))
    kwargs.setdefault("follow_redirects", False)
    client = httpx.AsyncClient(**kwargs)
    client.cookies = httpx.Cookies()  # start empty
    return client


async def request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    attempts: int = 3,
    backoff_seconds: float = 1.0,
    **kwargs: Any,
) -> tuple[httpx.Response, float]:
    """Perform a request, retrying only safe methods. Returns (response, seconds).

    Retries cover transport errors and 502/503/504 — a reverse proxy blipping
    mid-deployment should not fail a read-only smoke run. Everything else, and
    every non-idempotent method, is attempted exactly once.
    """
    upper = method.upper()
    allowed = attempts if upper in _RETRYABLE_METHODS else 1
    last_error: Exception | None = None

    for attempt in range(1, allowed + 1):
        started = time.monotonic()
        try:
            response = await client.request(upper, url, **kwargs)
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt >= allowed:
                break
        else:
            elapsed = time.monotonic() - started
            if response.status_code in (502, 503, 504) and attempt < allowed:
                await _sleep(backoff_seconds * attempt)
                continue
            # Never let a login cookie leak into later requests.
            client.cookies.clear()
            return response, elapsed
        await _sleep(backoff_seconds * attempt)

    raise AssertionFailure(
        f"{upper} {url} failed after {allowed} attempt(s): "
        f"{redact(str(last_error)) if last_error else 'unknown error'}"
    )


async def _sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)


class AssertionFailure(RuntimeError):
    """A harness assertion failed. Message is redacted before display."""


def parse_json(response: httpx.Response, context: str) -> Any:
    """Parse a JSON body, failing with a useful — and redacted — message."""
    try:
        return response.json()
    except ValueError:
        snippet = redact(response.text[:200])
        raise AssertionFailure(
            f"{context}: expected JSON, got {response.headers.get('content-type', '?')} "
            f"({snippet!r})"
        ) from None


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


@dataclass
class CheckResult:
    """One assertion. The atom every report is built from."""

    name: str
    passed: bool
    detail: str = ""
    endpoint: str = ""
    method: str = "GET"
    status_code: int | None = None
    latency_ms: float | None = None
    skipped: bool = False
    skip_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return scrub(
            {
                "name": self.name,
                "outcome": "skipped" if self.skipped else ("pass" if self.passed else "FAIL"),
                "detail": self.detail,
                "endpoint": self.endpoint,
                "method": self.method,
                "status_code": self.status_code,
                "latency_ms": round(self.latency_ms, 1) if self.latency_ms else None,
                "skip_reason": self.skip_reason,
            }
        )


class ResultSet:
    """Collects checks and decides the exit code."""

    def __init__(self, title: str) -> None:
        self.title = title
        self.started_at = utc_now()
        self.results: list[CheckResult] = []
        self.context: dict[str, Any] = {}

    def add(self, result: CheckResult) -> CheckResult:
        self.results.append(result)
        marker = "SKIP" if result.skipped else ("ok" if result.passed else "FAIL")
        status = f" [{result.status_code}]" if result.status_code else ""
        print(f"  {marker:>4}  {result.name}{status}")
        if not result.passed and not result.skipped and result.detail:
            print(f"        {redact(result.detail)}")
        return result

    def record(self, name: str, passed: bool, detail: str = "", **kwargs: Any) -> CheckResult:
        return self.add(CheckResult(name=name, passed=passed, detail=detail, **kwargs))

    def skip(self, name: str, reason: str) -> CheckResult:
        return self.add(CheckResult(name=name, passed=True, skipped=True, skip_reason=reason))

    @property
    def failed(self) -> list[CheckResult]:
        return [r for r in self.results if not r.passed and not r.skipped]

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.passed and not r.skipped)

    @property
    def skipped_count(self) -> int:
        return sum(1 for r in self.results if r.skipped)

    def exit_code(self) -> Exit:
        return Exit.ASSERTION_FAILED if self.failed else Exit.OK

    def summary(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "started_at": self.started_at,
            "finished_at": utc_now(),
            "passed": self.passed_count,
            "failed": len(self.failed),
            "skipped": self.skipped_count,
            "context": scrub(self.context),
            "checks": [r.to_dict() for r in self.results],
        }


# ---------------------------------------------------------------------------
# Time and reporting
# ---------------------------------------------------------------------------


def utc_now() -> str:
    """ISO-8601 UTC, second precision — stable across a report."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def write_reports(
    payload: Mapping[str, Any],
    markdown: str,
    *,
    report_dir: Path,
    stem: str,
) -> tuple[Path, Path]:
    """Write `<stem>.json` and `<stem>.md`, refusing if either holds a secret.

    The scan runs on the **serialized** text, after scrubbing, so it catches
    anything a nested structure or an unexpected key smuggled through.
    """
    report_dir.mkdir(parents=True, exist_ok=True)
    scrubbed = scrub(dict(payload))
    json_text = json.dumps(scrubbed, indent=2, default=str) + "\n"
    md_text = redact(markdown)

    for label, text in (("JSON", json_text), ("Markdown", md_text)):
        found = contains_secret(text)
        if found:
            raise AssertionFailure(
                f"refusing to write {label} report — it contains a {found}. "
                f"This is a harness bug; fix the redaction before rerunning."
            )

    json_path = report_dir / f"{stem}.json"
    md_path = report_dir / f"{stem}.md"
    json_path.write_text(json_text, encoding="utf-8")
    md_path.write_text(md_text, encoding="utf-8")
    return json_path, md_path


def results_markdown(results: ResultSet, *, heading: str, notes: Iterable[str] = ()) -> str:
    """Render a ResultSet as a readable Markdown report."""
    lines = [
        f"# {heading}",
        "",
        f"- Started: `{results.started_at}`",
        f"- Finished: `{utc_now()}`",
        f"- Passed: **{results.passed_count}** · Failed: **{len(results.failed)}** "
        f"· Skipped: **{results.skipped_count}**",
        "",
    ]
    if results.context:
        lines += ["## Context", ""]
        for key, value in scrub(results.context).items():
            lines.append(f"- {key}: `{value}`")
        lines.append("")
    for note in notes:
        lines += [note, ""]

    if results.failed:
        lines += ["## Failures", ""]
        for item in results.failed:
            lines.append(f"- **{item.name}** — {redact(item.detail)}")
        lines.append("")

    lines += [
        "## All checks",
        "",
        "| Result | Check | Endpoint | Status | ms |",
        "|---|---|---|---:|---:|",
    ]
    for item in results.results:
        outcome = "SKIP" if item.skipped else ("PASS" if item.passed else "**FAIL**")
        latency = f"{item.latency_ms:.0f}" if item.latency_ms else ""
        status = item.status_code or ""
        lines.append(
            f"| {outcome} | {item.name} | `{item.endpoint or '—'}` | {status} | {latency} |"
        )
    lines.append("")
    return "\n".join(lines)
