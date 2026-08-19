"""The E2E harness's own tests.

Everything here runs offline against `httpx.MockTransport`. The harness exists to
be pointed at production, so its safety properties — redaction, target guards and
the collector execution gates — are tested as behaviour, not documented as
intent.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.domain.alert_categories import ALERT_CATEGORIES
import scripts.e2e.common as common_module
from scripts.e2e import api_assertions as checks
from scripts.e2e import auth_tokens, collector_stage
from scripts.e2e.common import (
    AssertionFailure,
    AuthError,
    ConfigError,
    E2EConfig,
    Exit,
    ResultSet,
    SafetyRefusal,
    contains_secret,
    fingerprint,
    load_config,
    mask,
    parse_env_file,
    redact,
    scrub,
    write_reports,
)

FAKE_JWT = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJzdWIiOiIxIiwiZXhwIjo0MTAyNDQ0ODAwfQ"
    ".c2lnbmF0dXJlLXBsYWNlaG9sZGVy"
)


def _config(**overrides) -> E2EConfig:
    base = dict(
        api_base_url="https://api.hiddenalerts.com",
        target_env="production",
        admin_email="admin@example.test",
        admin_password="pw",
        subscriber_email="sub@example.test",
        subscriber_password="pw",
        supabase_project_url="https://project.supabase.co",
        supabase_publishable_key="anon-key",
    )
    base.update(overrides)
    return E2EConfig(**base)


def _client(config: E2EConfig, handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=config.api_base_url, transport=httpx.MockTransport(handler)
    )


# ---------------------------------------------------------------------------
# 1–7 · Environment and redaction
# ---------------------------------------------------------------------------


def test_missing_variables_are_named_without_values(monkeypatch):
    for name in ("E2E_API_BASE_URL", "ADMIN_EMAIL", "ADMIN_PASSWORD",
                 "TEST_SUBSCRIBER_EMAIL", "TEST_SUBSCRIBER_PASSWORD",
                 "SUPABASE_PROJECT_URL", "SUPABASE_PUBLISHABLE_KEY"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ConfigError) as excinfo:
        load_config()
    message = str(excinfo.value)
    assert "ADMIN_PASSWORD" in message
    assert "values are never printed" in message


def test_placeholder_values_are_rejected(monkeypatch, tmp_path):
    env = tmp_path / "e2e.env"
    env.write_text(
        "E2E_API_BASE_URL=https://api.hiddenalerts.com\n"
        "ADMIN_EMAIL=changeme@example.com\nADMIN_PASSWORD=changeme\n"
        "TEST_SUBSCRIBER_EMAIL=a@b.co\nTEST_SUBSCRIBER_PASSWORD=x\n"
        "SUPABASE_PROJECT_URL=https://p.supabase.co\nSUPABASE_PUBLISHABLE_KEY=k\n"
    )
    for name in ("ADMIN_EMAIL", "ADMIN_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ConfigError, match="placeholder"):
        load_config(env)


def test_production_requires_https():
    config = _config(api_base_url="http://api.hiddenalerts.com")
    from scripts.e2e.common import validate_target

    with pytest.raises(ConfigError, match="HTTPS"):
        validate_target(config)


def test_production_rejects_localhost():
    from scripts.e2e.common import validate_target

    with pytest.raises(ConfigError, match="production"):
        validate_target(_config(api_base_url="https://localhost:8000"))


def test_unexpected_production_host_is_rejected():
    from scripts.e2e.common import validate_target

    with pytest.raises(ConfigError, match="not an allowed production host"):
        validate_target(_config(api_base_url="https://staging.example.com"))


def test_harness_refuses_the_applications_own_env_file(tmp_path):
    (tmp_path / ".env").write_text("ADMIN_EMAIL=a@b.co\n")
    with pytest.raises(ConfigError, match="refusing to load"):
        load_config(tmp_path / ".env")


def test_service_role_key_is_refused(monkeypatch, tmp_path):
    import base64

    payload = base64.urlsafe_b64encode(json.dumps({"role": "service_role"}).encode()).decode()
    service_key = f"eyJhbGciOiJIUzI1NiJ9.{payload}.sig"
    env = tmp_path / "e2e.env"
    env.write_text(
        "E2E_API_BASE_URL=https://api.hiddenalerts.com\n"
        "ADMIN_EMAIL=a@b.co\nADMIN_PASSWORD=pw\n"
        "TEST_SUBSCRIBER_EMAIL=s@b.co\nTEST_SUBSCRIBER_PASSWORD=pw\n"
        "SUPABASE_PROJECT_URL=https://p.supabase.co\n"
        f"SUPABASE_PUBLISHABLE_KEY={service_key}\n"
    )
    for name in ("ADMIN_EMAIL", "ADMIN_PASSWORD", "SUPABASE_PUBLISHABLE_KEY",
                 "E2E_API_BASE_URL", "TEST_SUBSCRIBER_EMAIL",
                 "TEST_SUBSCRIBER_PASSWORD", "SUPABASE_PROJECT_URL"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ConfigError, match="service-role"):
        load_config(env)


@pytest.mark.parametrize("text,label", [
    (f"Authorization: Bearer {FAKE_JWT}", "JWT"),
    ("password=hunter2", "password"),
    ("postgresql+asyncpg://u:p@db:5432/x", "database URL"),
    ("client 203.0.113.7 connected", "IP"),
])
def test_redaction_removes_secrets(text, label):
    out = redact(text)
    assert "hunter2" not in out
    assert FAKE_JWT not in out
    assert "203.0.113.7" not in out
    assert "u:p@db" not in out


def test_scrub_drops_forbidden_keys_entirely():
    cleaned = scrub({
        "endpoint": "/api/v1/sources",
        "headers": {"Authorization": f"Bearer {FAKE_JWT}"},
        "password": "hunter2",
        "nested": [{"access_token": FAKE_JWT, "status": 200}],
    })
    assert "headers" not in cleaned
    assert "password" not in cleaned
    assert "access_token" not in cleaned["nested"][0]
    assert cleaned["nested"][0]["status"] == 200
    assert cleaned["endpoint"] == "/api/v1/sources"


def test_redaction_strips_a_token_before_the_report_is_written(tmp_path):
    """Layer 1: a token in report text is scrubbed, and the file is still written."""
    json_path, md_path = write_reports(
        {"note": f"token {FAKE_JWT}"}, f"token {FAKE_JWT}",
        report_dir=tmp_path, stem="redacted",
    )
    assert FAKE_JWT not in md_path.read_text()
    assert FAKE_JWT not in json_path.read_text()
    assert "<redacted>" in md_path.read_text()


def test_report_scan_refuses_what_redaction_cannot_reach(tmp_path):
    """Layer 2: the pre-write scan is a real backstop, not decoration.

    `scrub` only rewrites `str` values, so a non-string object carrying a token
    slips past it and is serialized by `json.dumps(default=str)`. The scan on the
    serialized bytes is what catches that, and it must refuse to write.
    """

    class Opaque:
        def __str__(self) -> str:
            return f"Bearer {FAKE_JWT}"

    with pytest.raises(AssertionFailure, match="JWT-shaped"):
        write_reports({"leaked": Opaque()}, "# clean\n",
                      report_dir=tmp_path, stem="leak")
    assert not list(tmp_path.glob("leak.*"))


def test_reports_write_when_clean(tmp_path):
    json_path, md_path = write_reports(
        {"checks": [{"name": "x", "outcome": "pass"}]},
        "# Report\n\nAll good.\n", report_dir=tmp_path, stem="clean",
    )
    assert json.loads(json_path.read_text())["checks"][0]["outcome"] == "pass"
    assert "All good" in md_path.read_text()


def test_fingerprint_and_mask_never_reveal_the_token():
    assert FAKE_JWT not in fingerprint(FAKE_JWT)
    assert FAKE_JWT not in mask(FAKE_JWT)
    assert fingerprint(FAKE_JWT) == fingerprint(FAKE_JWT)
    assert contains_secret(fingerprint(FAKE_JWT)) is None


def test_env_file_parser_handles_export_and_quotes(tmp_path):
    path = tmp_path / "x.env"
    path.write_text('# comment\nexport A="one"\nB=\'two\'\n\nC=three\n')
    assert parse_env_file(path) == {"A": "one", "B": "two", "C": "three"}


# ---------------------------------------------------------------------------
# 8–13 · Admin authentication
# ---------------------------------------------------------------------------


def _admin_handler(*, login_status=200, verify_status=200, role="admin", token=FAKE_JWT):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == auth_tokens.ADMIN_LOGIN_PATH:
            if login_status != 200:
                return httpx.Response(login_status, json={"detail": "nope"})
            body = {
                "access_token": token, "token_type": "bearer", "expires_in": 3600,
                "user": {"id": 1, "email": "a@b.co", "role": role, "is_active": True},
            }
            return httpx.Response(200, json=body)
        return httpx.Response(verify_status, json=[] if verify_status == 200 else {"detail": "x"})
    return handler


@pytest.mark.asyncio
async def test_admin_login_extracts_token_and_verifies_authorization():
    config = _config()
    async with _client(config, _admin_handler()) as client:
        bundle = await auth_tokens.get_admin_access_token(config, client)
    assert bundle.access_token == FAKE_JWT
    assert bundle.token_type == "bearer"
    assert bundle.verified_status == 200
    assert bundle.verified_endpoint == auth_tokens.ADMIN_VERIFY_PATH


@pytest.mark.asyncio
async def test_admin_wrong_credentials_fail():
    config = _config()
    async with _client(config, _admin_handler(login_status=401)) as client:
        with pytest.raises(AuthError, match="invalid email or password"):
            await auth_tokens.get_admin_access_token(config, client)


@pytest.mark.asyncio
async def test_admin_missing_token_field_fails():
    def handler(request):
        if request.url.path == auth_tokens.ADMIN_LOGIN_PATH:
            return httpx.Response(200, json={"expires_in": 60})
        return httpx.Response(200, json=[])

    config = _config()
    async with _client(config, handler) as client:
        with pytest.raises(AuthError, match="no usable 'access_token'"):
            await auth_tokens.get_admin_access_token(config, client)


@pytest.mark.asyncio
async def test_non_admin_token_fails_authorization_not_login():
    """HTTP 200 at login is never sufficient — 403 at verification must fail."""
    config = _config()
    async with _client(config, _admin_handler(verify_status=403, role="viewer")) as client:
        with pytest.raises(AuthError, match="not authorized for admin"):
            await auth_tokens.get_admin_access_token(config, client)


@pytest.mark.asyncio
async def test_missing_endpoint_is_not_reported_as_auth_failure():
    config = _config()
    async with _client(config, _admin_handler(verify_status=404)) as client:
        with pytest.raises(AuthError, match="not an authentication failure"):
            await auth_tokens.get_admin_access_token(config, client)


@pytest.mark.asyncio
async def test_expiry_is_extracted_when_present():
    config = _config()
    async with _client(config, _admin_handler()) as client:
        bundle = await auth_tokens.get_admin_access_token(config, client)
    assert bundle.expires_at is not None
    assert bundle.expires_at.tzinfo is not None


@pytest.mark.asyncio
async def test_token_is_never_in_the_default_summary():
    config = _config()
    async with _client(config, _admin_handler()) as client:
        bundle = await auth_tokens.get_admin_access_token(config, client)
    serialized = json.dumps(bundle.safe_summary())
    assert FAKE_JWT not in serialized
    assert contains_secret(serialized) is None
    assert FAKE_JWT not in repr(bundle)


# ---------------------------------------------------------------------------
# 14–18 · Subscriber authentication
# ---------------------------------------------------------------------------


def _supabase_handler(config, *, grant_status=200, verify_status=200, captured=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == httpx.URL(config.supabase_project_url).host:
            if captured is not None:
                captured["apikey"] = request.headers.get("apikey")
                captured["grant_type"] = request.url.params.get("grant_type")
            if grant_status != 200:
                return httpx.Response(grant_status, json={"error": "invalid_grant"})
            return httpx.Response(200, json={
                "access_token": FAKE_JWT, "token_type": "bearer",
                "refresh_token": "REFRESH-SECRET-VALUE", "expires_in": 3600,
            })
        body = [] if verify_status == 200 else {"detail": "active_subscription_required"}
        return httpx.Response(verify_status, json=body)
    return handler


@pytest.mark.asyncio
async def test_subscriber_login_uses_publishable_key_and_password_grant():
    config = _config()
    captured: dict[str, str] = {}
    transport = httpx.MockTransport(_supabase_handler(config, captured=captured))
    async with httpx.AsyncClient(base_url=config.api_base_url, transport=transport) as client:
        import scripts.e2e.auth_tokens as module

        original = httpx.AsyncClient

        def patched(*args, **kwargs):
            kwargs["transport"] = transport
            return original(*args, **kwargs)

        module.httpx.AsyncClient = patched
        try:
            bundle = await module.get_subscriber_access_token(config, client)
        finally:
            module.httpx.AsyncClient = original

    assert captured["apikey"] == config.supabase_publishable_key
    assert captured["grant_type"] == "password"
    assert bundle.kind == "subscriber"
    assert bundle.verified_status == 200


@pytest.mark.asyncio
async def test_inactive_subscription_is_distinct_from_invalid_credentials():
    config = _config()
    transport = httpx.MockTransport(_supabase_handler(config, verify_status=403))
    async with httpx.AsyncClient(base_url=config.api_base_url, transport=transport) as client:
        import scripts.e2e.auth_tokens as module

        original = httpx.AsyncClient
        module.httpx.AsyncClient = lambda *a, **k: original(*a, **{**k, "transport": transport})
        try:
            with pytest.raises(AuthError, match="subscription is not active"):
                await module.get_subscriber_access_token(config, client)
            bundle = await module.get_subscriber_access_token(config, client, expect_active=False)
        finally:
            module.httpx.AsyncClient = original
    assert bundle.verified_status == 403


@pytest.mark.asyncio
async def test_invalid_supabase_credentials_fail_safely():
    config = _config()
    transport = httpx.MockTransport(_supabase_handler(config, grant_status=400))
    async with httpx.AsyncClient(base_url=config.api_base_url, transport=transport) as client:
        import scripts.e2e.auth_tokens as module

        original = httpx.AsyncClient
        module.httpx.AsyncClient = lambda *a, **k: original(*a, **{**k, "transport": transport})
        try:
            with pytest.raises(AuthError, match="invalid subscriber credentials"):
                await module.get_subscriber_access_token(config, client)
        finally:
            module.httpx.AsyncClient = original


@pytest.mark.asyncio
async def test_refresh_token_is_never_retained_or_serialized():
    config = _config()
    transport = httpx.MockTransport(_supabase_handler(config))
    async with httpx.AsyncClient(base_url=config.api_base_url, transport=transport) as client:
        import scripts.e2e.auth_tokens as module

        original = httpx.AsyncClient
        module.httpx.AsyncClient = lambda *a, **k: original(*a, **{**k, "transport": transport})
        try:
            bundle = await module.get_subscriber_access_token(config, client)
        finally:
            module.httpx.AsyncClient = original

    blob = json.dumps(bundle.safe_summary()) + repr(bundle) + str(vars(bundle))
    assert "REFRESH-SECRET-VALUE" not in blob


# ---------------------------------------------------------------------------
# 19–31 · API smoke assertions
# ---------------------------------------------------------------------------


def _health_record(**overrides):
    """Mirrors the real `SourceHealthRead` field names, not the RunLog ones."""
    base = {
        "source_id": 1, "name": "SEC", "state": "healthy", "reason_code": "ok",
        "items_skipped_invalid_24h": 0,
        "latest_run_items_skipped_external": 0,
        "items_skipped_external_24h": 0,
        "items_skipped_external_7d": 0,
        "last_run_at": "2026-08-02T10:00:00Z",
    }
    base.update(overrides)
    return base


def test_source_health_list_accepts_valid_payload():
    assert checks.check_source_health_list([_health_record()]) == []


def test_source_health_list_rejects_bad_state_and_empty_reason():
    problems = checks.check_source_health_list(
        [_health_record(state="broken", reason_code="  ")]
    )
    assert any("state" in p for p in problems)
    assert any("reason_code" in p for p in problems)


def test_source_health_list_requires_external_counter_and_all_sources():
    record = _health_record()
    del record["items_skipped_external_24h"]
    assert any("items_skipped_external_24h is missing" in p
               for p in checks.check_source_health_list([record]))
    problems = checks.check_source_health_list([_health_record()], expected_source_ids=[1, 2])
    assert any("missing source ids [2]" in p for p in problems)


def test_source_health_detail_requires_newest_first_runs():
    payload = {
        "health": _health_record(),
        "recent_runs": [
            {"run_started_at": "2026-08-01T00:00:00Z", "items_skipped_external": 0},
            {"run_started_at": "2026-08-02T00:00:00Z", "items_skipped_external": 0},
        ],
    }
    assert any("newest-first" in p for p in checks.check_source_health_detail(payload))


def test_system_summary_totals_must_reconcile():
    good = {"sources_total": 3, "by_state": {"healthy": 2, "error": 1},
            "scheduler_running": False}
    assert checks.check_system_health_summary(good) == []
    bad = {"sources_total": 5, "by_state": {"healthy": 2}, "scheduler_running": False}
    assert any("!= sources_total" in p for p in checks.check_system_health_summary(bad))


def test_system_summary_requires_scheduler_state():
    payload = {"sources_total": 1, "by_state": {"healthy": 1}}
    assert any("scheduler_running" in p for p in checks.check_system_health_summary(payload))


def test_external_and_invalid_counters_stay_distinct():
    """Both must exist independently; neither may stand in for the other.

    The health record names these differently from the RunLog counters, which is
    precisely why this is asserted from a shared constant rather than a literal.
    """
    record = _health_record(items_skipped_invalid_24h=4, items_skipped_external_24h=9)
    assert checks.check_source_health_list([record]) == []
    assert checks.HEALTH_INVALID_COUNTER not in checks.HEALTH_EXTERNAL_COUNTERS

    # Dropping the invalid counter must be caught on its own.
    without_invalid = _health_record()
    del without_invalid[checks.HEALTH_INVALID_COUNTER]
    assert any(checks.HEALTH_INVALID_COUNTER in p
               for p in checks.check_source_health_list([without_invalid]))


def _categories_payload(counts=None, *, order=None, drop=()):
    values = list(order or ALERT_CATEGORIES)
    counts = counts or {}
    return {
        "categories": [
            {"value": v, "label": v, "count": counts.get(v, 0)}
            for v in values if v not in drop
        ],
        "total": sum(counts.values()),
    }


@pytest.mark.parametrize("scope", ["admin", "subscriber"])
def test_canonical_categories_accepted(scope):
    assert checks.check_categories(_categories_payload(), scope=scope) == []


def test_categories_reject_wrong_order():
    reordered = list(ALERT_CATEGORIES)[::-1]
    problems = checks.check_categories(_categories_payload(order=reordered), scope="admin")
    assert any("canonical order" in p for p in problems)


def test_categories_reject_duplicates_and_negative_counts():
    payload = _categories_payload()
    payload["categories"].append(dict(payload["categories"][0]))
    assert any("duplicate" in p for p in checks.check_categories(payload, scope="admin"))
    negative = _categories_payload()
    negative["categories"][0]["count"] = -1
    assert any("negative" in p for p in checks.check_categories(negative, scope="admin"))


def test_zero_count_categories_must_be_retained():
    dropped = _categories_payload(drop=("Other",))
    assert checks.missing_zero_count_categories(dropped) == ["Other"]
    assert checks.missing_zero_count_categories(_categories_payload()) == []


def test_top_alerts_empty_is_accepted():
    assert checks.check_top_alerts(
        {"alerts": [], "is_fallback": False, "message": None}
    ) == []


def test_top_alerts_enforces_maximum_of_three():
    alert = {"risk_band": "critical", "published_at": "2026-08-01T00:00:00Z",
             "source_published_at": None, "processed_at": "2026-08-01T00:00:00Z"}
    payload = {"alerts": [alert] * 4, "is_fallback": False, "message": None}
    assert any("maximum is 3" in p for p in checks.check_top_alerts(payload))


def test_top_alerts_rejects_medium_band():
    alert = {"risk_band": "medium", "published_at": "2026-08-01T00:00:00Z",
             "source_published_at": None, "processed_at": "2026-08-01T00:00:00Z"}
    payload = {"alerts": [alert], "is_fallback": False, "message": None}
    problems = checks.check_top_alerts(payload)
    assert any("neither critical nor high" in p for p in problems)


def test_top_alerts_allows_published_at_and_source_published_at_to_differ():
    """Final contract: the two timestamps are independent — never required to
    match, and published_at must never be overwritten with source_published_at."""
    differing = {"risk_band": "high", "published_at": "2026-08-02T00:00:00Z",
                 "source_published_at": "2026-01-14T10:30:00Z",
                 "processed_at": "2026-08-02T00:05:00Z"}
    payload = {"alerts": [differing], "is_fallback": False, "message": None}
    assert checks.check_top_alerts(payload) == []

    matching = {"risk_band": "high", "published_at": "2026-07-01T00:00:00Z",
                "source_published_at": "2026-07-01T00:00:00Z",
                "processed_at": "2026-07-01T00:05:00Z"}
    payload_matching = {"alerts": [matching], "is_fallback": False, "message": None}
    assert checks.check_top_alerts(payload_matching) == []

    no_source_date = {"risk_band": "high", "published_at": "2026-08-02T00:00:00Z",
                       "source_published_at": None,
                       "processed_at": "2026-08-02T00:05:00Z"}
    payload_no_source = {"alerts": [no_source_date], "is_fallback": False, "message": None}
    assert checks.check_top_alerts(payload_no_source) == []


def test_top_alerts_requires_source_published_at_field_present():
    alert = {"risk_band": "high", "published_at": "2026-08-02T00:00:00Z",
             "processed_at": "2026-08-02T00:05:00Z"}
    payload = {"alerts": [alert], "is_fallback": False, "message": None}
    assert any("separately present" in p for p in checks.check_top_alerts(payload))


def test_top_alerts_fallback_flag_requires_a_message():
    alert = {"risk_band": "high", "published_at": "2026-01-01T00:00:00Z",
             "source_published_at": None, "processed_at": "2026-01-01T00:05:00Z"}
    missing_message = {"alerts": [alert], "is_fallback": True, "message": None}
    assert any("message is missing" in p for p in checks.check_top_alerts(missing_message))

    with_message = {"alerts": [alert], "is_fallback": True,
                     "message": "No new Critical or High alerts this week."}
    assert checks.check_top_alerts(with_message) == []


def test_top_alerts_non_fallback_must_not_carry_a_message():
    payload = {"alerts": [], "is_fallback": False, "message": "should not be here"}
    assert any("is not null" in p for p in checks.check_top_alerts(payload))


def test_top_alerts_fallback_true_with_no_alerts_is_a_problem():
    payload = {"alerts": [], "is_fallback": True, "message": "stale message"}
    assert any("must only be claimed" in p for p in checks.check_top_alerts(payload))


def test_public_alerts_must_not_leak_private_fields():
    payload = {"alerts": [{"id": 1, "title": "x", "publication_state_source": "auto_policy"}]}
    assert any("private fields" in p for p in checks.check_public_alerts(payload))
    assert checks.check_public_alerts({"alerts": [{"id": 1, "title": "x"}]}) == []


def test_run_log_counter_identity():
    balanced = {"items_fetched": 10, "items_new": 3, "items_skipped_url": 5,
                "items_skipped_content": 1, "items_skipped_invalid": 1,
                "items_skipped_external": 0}
    assert checks.check_run_log_counters(balanced) == []
    balanced["items_skipped_external"] = 4
    assert any("does not balance" in p for p in checks.check_run_log_counters(balanced))


# ---------------------------------------------------------------------------
# 32–47 · Collector stage safety
# ---------------------------------------------------------------------------


def _summary(**overrides):
    base = {"scheduler_running": False, "alembic_revision": "0013", "sources_total": 10}
    base.update(overrides)
    return base


def _preview_evidence(**overrides) -> collector_stage.PreviewEvidence:
    base = dict(
        prospective_unseen=5, source_name="SEC Press Releases", status="listing_ready",
        generated_at=datetime.now(timezone.utc), age_seconds=30.0,
        database_revision="0013", config_changed=False,
    )
    base.update(overrides)
    return collector_stage.PreviewEvidence(**base)


def _gates(**overrides):
    kwargs = dict(
        execute=True, confirmation=collector_stage.CONFIRMATION_PHRASE,
        config=_config(), summary=_summary(), health={"health": {"state": "healthy"}},
        preview=_preview_evidence(), max_unseen=10, max_new_raw_items=10,
        stage=None, stage_confirmation=None,
        ai_disabled=True, ai_detail="API reports ai_processing_enabled=false",
    )
    kwargs.update(overrides)
    return kwargs


def test_gates_pass_when_everything_is_satisfied():
    collector_stage.enforce_execution_gates(**_gates())


def test_missing_execute_refuses():
    with pytest.raises(SafetyRefusal, match="dry-run is the default"):
        collector_stage.enforce_execution_gates(**_gates(execute=False))


def test_wrong_confirmation_phrase_refuses():
    with pytest.raises(SafetyRefusal, match="confirmation phrase"):
        collector_stage.enforce_execution_gates(**_gates(confirmation="yes"))


def test_running_scheduler_refuses():
    with pytest.raises(SafetyRefusal, match="scheduler must be paused|must be paused"):
        collector_stage.enforce_execution_gates(**_gates(summary=_summary(scheduler_running=True)))


def test_unknown_scheduler_state_refuses():
    with pytest.raises(SafetyRefusal):
        collector_stage.enforce_execution_gates(**_gates(summary=_summary(scheduler_running=None)))


def test_migration_below_0013_refuses():
    with pytest.raises(SafetyRefusal, match="migration revision"):
        collector_stage.enforce_execution_gates(**_gates(summary=_summary(alembic_revision="0011")))


def test_execution_without_a_preview_report_refuses():
    with pytest.raises(SafetyRefusal, match="--preview-report is required"):
        collector_stage.enforce_execution_gates(**_gates(preview=None))


def test_missing_volume_limits_refuse():
    with pytest.raises(SafetyRefusal, match="--max-unseen"):
        collector_stage.enforce_execution_gates(**_gates(max_unseen=None))
    with pytest.raises(SafetyRefusal, match="--max-new-raw-items"):
        collector_stage.enforce_execution_gates(**_gates(max_new_raw_items=None))


def test_disabled_source_refuses():
    with pytest.raises(SafetyRefusal, match="disabled"):
        collector_stage.enforce_execution_gates(
            **_gates(health={"health": {"state": "disabled"}})
        )


def test_non_production_target_refuses_execution():
    with pytest.raises(SafetyRefusal, match="only defined for a validated production"):
        collector_stage.enforce_execution_gates(
            **_gates(config=_config(target_env="staging",
                                    api_base_url="https://api.hiddenalerts.com"))
        )


@pytest.mark.parametrize("stage,phrase", sorted(collector_stage.STAGE_EXTRA_CONFIRMATION.items()))
def test_fbi_stages_need_their_own_confirmation(stage, phrase):
    with pytest.raises(SafetyRefusal, match="stage-confirmation"):
        collector_stage.enforce_execution_gates(**_gates(stage=stage, stage_confirmation=None))
    collector_stage.enforce_execution_gates(**_gates(stage=stage, stage_confirmation=phrase))


def test_source_id_name_mismatch_refuses():
    sources = [{"id": 4, "name": "IC3 Press Releases"}]
    with pytest.raises(SafetyRefusal, match="does not exactly match"):
        collector_stage.resolve_source(sources, 4, "SEC Press Releases")
    assert collector_stage.resolve_source(sources, 4, "IC3 Press Releases")["id"] == 4


def test_source_matching_is_exact_not_substring():
    """A short prefix must not authorize a run against a longer source name."""
    sources = [{"id": 1, "name": "SEC Press Releases"}]
    with pytest.raises(SafetyRefusal, match="does not exactly match"):
        collector_stage.resolve_source(sources, 1, "SEC")
    # Whitespace and case are normalized; nothing else is.
    assert collector_stage.resolve_source(sources, 1, "  sec press releases  ")["id"] == 1
    assert collector_stage.names_match("SEC Press Releases", "SEC Press Releases")
    assert not collector_stage.names_match("SEC Press Releases", "SEC")
    assert not collector_stage.names_match("FBI National Press Releases", "FBI")


def test_unknown_source_id_refuses():
    with pytest.raises(SafetyRefusal, match="does not exist"):
        collector_stage.resolve_source([{"id": 1, "name": "SEC"}], 99, "x")


def test_stage_plans_cover_expected_sources_and_never_batch():
    assert set(collector_stage.STAGE_PLANS) == {"A", "B", "C", "D", "E"}
    assert "FBI National Press Releases" in collector_stage.STAGE_PLANS["D"]
    assert "FBI in the News RSS" in collector_stage.STAGE_PLANS["E"]
    # The runner takes exactly one --source-id; there is no multi-source path.
    parser = collector_stage._build_parser()
    action = next(a for a in parser._actions if a.dest == "source_id")
    assert action.nargs is None and action.type is int


def test_paused_scheduler_alone_is_not_ai_evidence():
    """The 30-minute AI job is gated separately from collect_all_sources."""
    ok, detail = collector_stage.ai_processing_evidence(_summary())
    assert not ok
    assert "not evidence about the standalone 30-minute AI job" in detail


def test_explicit_api_evidence_settles_the_ai_question():
    ok, detail = collector_stage.ai_processing_evidence(
        _summary(ai_processing_enabled=False))
    assert ok and "ai_processing_enabled=false" in detail
    ok, detail = collector_stage.ai_processing_evidence(
        _summary(ai_processing_enabled=True))
    assert not ok and "AI is running" in detail


def test_operator_ai_confirmation_requires_the_exact_phrase():
    ok, _ = collector_stage.ai_processing_evidence(
        _summary(), operator_confirmation="yes please")
    assert not ok
    ok, detail = collector_stage.ai_processing_evidence(
        _summary(), operator_confirmation=collector_stage.AI_CONFIRMATION_PHRASE)
    assert ok and "operator confirmed" in detail


def test_unconfirmed_ai_refuses_execution_before_any_trigger():
    with pytest.raises(SafetyRefusal, match="AI processing is not confirmed disabled"):
        collector_stage.enforce_execution_gates(
            **_gates(ai_disabled=False, ai_detail="no evidence"))


@pytest.mark.asyncio
async def test_dry_run_issues_no_trigger_and_no_ai_or_scheduler_call():
    """The whole point: a default invocation must not mutate anything."""
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        path = request.url.path
        if path == auth_tokens.ADMIN_LOGIN_PATH:
            return httpx.Response(200, json={
                "access_token": FAKE_JWT, "token_type": "bearer", "expires_in": 60,
                "user": {"id": 1, "email": "a@b.co", "role": "admin", "is_active": True}})
        if path == "/api/v1/sources":
            return httpx.Response(200, json=[{"id": 1, "name": "SEC Press Releases"}])
        if path == auth_tokens.ADMIN_VERIFY_PATH_POST_DEPLOY:
            return httpx.Response(200, json=_summary())
        if path.endswith("/health"):
            return httpx.Response(200, json={
                "health": _health_record(), "recent_runs": [
                    {"id": 7, "run_started_at": "2026-08-02T10:00:00Z", "status": "success",
                     "items_skipped_external": 0}]})
        if path.endswith("/runs"):
            return httpx.Response(200, json=[
                {"id": 7, "run_started_at": "2026-08-02T10:00:00Z", "status": "success",
                 "items_fetched": 0, "items_new": 0, "items_skipped_url": 0,
                 "items_skipped_content": 0, "items_skipped_invalid": 0,
                 "items_skipped_external": 0}])
        return httpx.Response(404, json={})

    config = _config()
    transport = httpx.MockTransport(handler)
    import scripts.e2e.common as common_module

    original = common_module.make_client
    common_module.make_client = lambda cfg, **kw: httpx.AsyncClient(
        base_url=cfg.api_base_url, transport=transport
    )
    collector_stage.make_client = common_module.make_client
    try:
        results, context = await collector_stage.run_stage(
            config, source_id=1, expected_name="SEC Press Releases", execute=False,
            confirmation="", max_unseen=None, max_new_raw_items=None,
            stage=None, stage_confirmation=None, preview_report=None,
            ai_confirmation=None, check_409=False,
        )
    finally:
        common_module.make_client = original
        collector_stage.make_client = original

    assert context.executed is False
    assert context.trigger_status is None
    assert not any(method == "POST" and "trigger" in path for method, path in calls)
    assert not any("process" in path or "scheduler" in path for _, path in calls)


def test_terminal_statuses_and_required_revision_are_explicit():
    assert "success" in collector_stage.TERMINAL_STATUSES
    assert "failed" in collector_stage.TERMINAL_STATUSES
    assert collector_stage.REQUIRED_REVISION == "0013"


def test_stage_report_distinguishes_raw_items_from_alerts():
    results = ResultSet("t")
    results.record("x", True)
    context = collector_stage.StageContext(
        source_id=1, source_name="SEC", executed=True,
        new_run={"status": "success", "items_fetched": 5, "items_new": 2,
                 "items_skipped_url": 3, "items_skipped_content": 0,
                 "items_skipped_invalid": 0, "items_skipped_external": 0},
    )
    body = collector_stage.stage_markdown(results, context)
    assert "RawItems are not published alerts" in body
    assert "items_new (RawItems)" in body


def test_exit_codes_are_stable():
    assert (Exit.OK, Exit.ASSERTION_FAILED, Exit.CONFIG_ERROR, Exit.AUTH_FAILED,
            Exit.SAFETY_REFUSED, Exit.COLLECTOR_TIMEOUT, Exit.STOP_CONDITION) == (
        0, 1, 2, 3, 4, 5, 6)


def test_post_requests_are_never_retried():
    from scripts.e2e.common import _RETRYABLE_METHODS

    assert "POST" not in _RETRYABLE_METHODS
    assert _RETRYABLE_METHODS == frozenset({"GET", "HEAD"})


def test_supabase_transport_failure_becomes_an_auth_error_not_a_crash():
    """A network failure reaching Supabase must not abort a whole smoke run."""
    import asyncio

    config = _config()

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("name or service not known")

    transport = httpx.MockTransport(handler)
    import scripts.e2e.auth_tokens as module

    async def go():
        original = httpx.AsyncClient
        module.httpx.AsyncClient = lambda *a, **k: original(*a, **{**k, "transport": transport})
        try:
            async with original(base_url=config.api_base_url, transport=transport) as client:
                with pytest.raises(AuthError, match="could not reach the Supabase"):
                    await module.get_subscriber_access_token(config, client)
        finally:
            module.httpx.AsyncClient = original

    asyncio.run(go())


# ---------------------------------------------------------------------------
# Refinement · preview-report validation
# ---------------------------------------------------------------------------


def _preview_document(**overrides):
    base = {
        "tool": "source_recovery_preview",
        "read_only": True,
        "read_only_transaction_enforced": True,
        "database_counts_match": True,
        "database_revision": "0013",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "errors": [],
        "warnings": [],
        "branch": "dev-collector-health-backend-cleanup",
        "commit": "6293fad",
        "sources": [{
            "source_id": 1, "name": "SEC Press Releases", "status": "listing_ready",
            "prospective_unseen": 5, "config_changed": False,
        }],
    }
    base.update(overrides)
    return base


def _write_preview(tmp_path, **overrides):
    path = tmp_path / "preview.json"
    path.write_text(json.dumps(_preview_document(**overrides)))
    return path


def _load(tmp_path, *, source_id=1, name="SEC Press Releases", max_unseen=10, **overrides):
    return collector_stage.load_preview_evidence(
        _write_preview(tmp_path, **overrides),
        source_id=source_id, expected_name=name, max_unseen=max_unseen,
    )


def test_fresh_valid_preview_authorizes_the_gate(tmp_path):
    evidence = _load(tmp_path)
    assert evidence.prospective_unseen == 5
    assert evidence.database_revision == "0013"
    assert evidence.commit == "6293fad"
    collector_stage.enforce_execution_gates(**_gates(preview=evidence))


def test_stale_preview_refuses(tmp_path):
    old = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()
    with pytest.raises(SafetyRefusal, match="minutes old"):
        _load(tmp_path, generated_at=old)


def test_preview_from_revision_0011_refuses(tmp_path):
    with pytest.raises(SafetyRefusal, match="different schema"):
        _load(tmp_path, database_revision="0011")


def test_non_read_only_preview_refuses(tmp_path):
    with pytest.raises(SafetyRefusal, match="not marked read_only"):
        _load(tmp_path, read_only=False)
    with pytest.raises(SafetyRefusal, match="read-only transaction"):
        _load(tmp_path, read_only_transaction_enforced=False)
    with pytest.raises(SafetyRefusal, match="row counts changed"):
        _load(tmp_path, database_counts_match=False)


def test_preview_from_another_tool_refuses(tmp_path):
    with pytest.raises(SafetyRefusal, match="expected 'source_recovery_preview'"):
        _load(tmp_path, tool="something_else")


def test_preview_with_errors_refuses(tmp_path):
    with pytest.raises(SafetyRefusal, match="error"):
        _load(tmp_path, errors=["upstream failed"])


def test_preview_source_id_mismatch_refuses(tmp_path):
    with pytest.raises(SafetyRefusal, match="no record for source id 9"):
        _load(tmp_path, source_id=9, name="SEC Press Releases")


def test_preview_exact_name_mismatch_refuses(tmp_path):
    with pytest.raises(SafetyRefusal, match="no record for source id 1"):
        _load(tmp_path, name="SEC")


def test_ambiguous_multi_source_preview_refuses(tmp_path):
    duplicated = _preview_document()["sources"] * 2
    with pytest.raises(SafetyRefusal, match="ambiguous"):
        _load(tmp_path, sources=duplicated)


def test_preview_count_above_maximum_refuses(tmp_path):
    with pytest.raises(SafetyRefusal, match="above the supplied maximum"):
        _load(tmp_path, max_unseen=2)


def test_preview_with_config_overlay_refuses(tmp_path):
    """Volume measured under a simulated config does not describe production."""
    overlaid = [dict(_preview_document()["sources"][0], config_changed=True)]
    with pytest.raises(SafetyRefusal, match="configuration overlay"):
        _load(tmp_path, sources=overlaid)


def test_preview_unaccepted_status_refuses(tmp_path):
    bad = [dict(_preview_document()["sources"][0], status="failed")]
    with pytest.raises(SafetyRefusal, match="preview status"):
        _load(tmp_path, sources=bad)


def test_preview_malformed_json_and_missing_file_refuse(tmp_path):
    broken = tmp_path / "broken.json"
    broken.write_text("{not json")
    with pytest.raises(SafetyRefusal, match="not valid JSON"):
        collector_stage.load_preview_evidence(
            broken, source_id=1, expected_name="SEC Press Releases", max_unseen=10)
    with pytest.raises(SafetyRefusal, match="cannot read preview report"):
        collector_stage.load_preview_evidence(
            tmp_path / "absent.json", source_id=1,
            expected_name="SEC Press Releases", max_unseen=10)


def test_unparseable_generated_at_refuses(tmp_path):
    with pytest.raises(SafetyRefusal, match="not a parseable timestamp"):
        _load(tmp_path, generated_at="yesterday")


def test_hand_entered_preview_unseen_cannot_authorize_execution(monkeypatch, tmp_path):
    """`--preview-unseen` is display-only; with --execute it is rejected outright."""
    env = tmp_path / "e2e.env"
    env.write_text(
        "E2E_API_BASE_URL=https://api.hiddenalerts.com\n"
        "ADMIN_EMAIL=a@b.co\nADMIN_PASSWORD=pw\n"
    )
    for name in ("ADMIN_EMAIL", "ADMIN_PASSWORD", "E2E_API_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    code = collector_stage.main([
        "--source-id", "1", "--expected-source-name", "SEC Press Releases",
        "--execute", "--confirmation", collector_stage.CONFIRMATION_PHRASE,
        "--max-unseen", "10", "--max-new-raw-items", "10",
        "--preview-unseen", "5", "--env-file", str(env),
    ])
    assert code == int(Exit.SAFETY_REFUSED)


# ---------------------------------------------------------------------------
# Refinement · credential scopes
# ---------------------------------------------------------------------------


def _scoped_env(tmp_path, *, admin=True, subscriber=True):
    lines = ["E2E_API_BASE_URL=https://api.hiddenalerts.com", "E2E_TARGET_ENV=production"]
    if admin:
        lines += ["ADMIN_EMAIL=a@b.co", "ADMIN_PASSWORD=pw"]
    if subscriber:
        lines += ["TEST_SUBSCRIBER_EMAIL=s@b.co", "TEST_SUBSCRIBER_PASSWORD=pw",
                  "SUPABASE_PROJECT_URL=https://p.supabase.co",
                  "SUPABASE_PUBLISHABLE_KEY=anon"]
    path = tmp_path / "scoped.env"
    path.write_text("\n".join(lines) + "\n")
    return path


@pytest.fixture
def _clean_env(monkeypatch):
    for name in ("E2E_API_BASE_URL", "E2E_TARGET_ENV", "ADMIN_EMAIL", "ADMIN_PASSWORD",
                 "TEST_SUBSCRIBER_EMAIL", "TEST_SUBSCRIBER_PASSWORD",
                 "SUPABASE_PROJECT_URL", "SUPABASE_PUBLISHABLE_KEY"):
        monkeypatch.delenv(name, raising=False)


def test_admin_only_command_needs_no_subscriber_credentials(tmp_path, _clean_env):
    config = load_config(_scoped_env(tmp_path, subscriber=False),
                         require_admin=True, require_subscriber=False)
    assert config.has_admin_credentials
    assert not config.has_subscriber_credentials
    assert config.loaded_scopes == ("admin",)
    # Target validation still runs.
    assert config.is_production


def test_subscriber_only_command_needs_no_admin_credentials(tmp_path, _clean_env):
    config = load_config(_scoped_env(tmp_path, admin=False),
                         require_admin=False, require_subscriber=True)
    assert config.has_subscriber_credentials
    assert not config.has_admin_credentials
    assert config.loaded_scopes == ("subscriber",)


def test_production_smoke_still_requires_both(tmp_path, _clean_env):
    with pytest.raises(ConfigError, match="TEST_SUBSCRIBER_EMAIL"):
        load_config(_scoped_env(tmp_path, subscriber=False))
    with pytest.raises(ConfigError, match="ADMIN_EMAIL"):
        load_config(_scoped_env(tmp_path, admin=False))
    config = load_config(_scoped_env(tmp_path))
    assert config.loaded_scopes == ("admin", "subscriber")


def test_unloaded_scope_refuses_rather_than_faking_credentials(tmp_path, _clean_env):
    config = load_config(_scoped_env(tmp_path, subscriber=False),
                         require_admin=True, require_subscriber=False)
    with pytest.raises(ConfigError, match="subscriber credentials were not loaded"):
        config.require_subscriber_credentials()
    config.require_admin_credentials()  # does not raise


def test_public_summary_omits_unloaded_scopes(tmp_path, _clean_env):
    config = load_config(_scoped_env(tmp_path, subscriber=False),
                         require_admin=True, require_subscriber=False)
    summary = config.public_summary()
    assert "subscriber_email_fingerprint" not in summary
    assert summary["credential_scopes"] == ["admin"]


# ---------------------------------------------------------------------------
# Refinement · report path and token output
# ---------------------------------------------------------------------------


def test_default_report_dir_resolves_to_backend_reports(tmp_path, _clean_env, monkeypatch):
    """Reports land beside the backend package, not beside the caller's cwd.

    The property under test is that the path derives from this module's location
    rather than `os.getcwd()` — so a command run from `backend/` and one run from
    the repository root write to the same directory. The literal directory *name*
    is not asserted: under the test harness the backend tree is mounted at /src.
    """
    monkeypatch.delenv("E2E_REPORT_DIR", raising=False)
    config = load_config(_scoped_env(tmp_path))

    assert config.report_dir.is_absolute()
    assert config.report_dir.name == "reports"
    assert config.report_dir == common_module.BACKEND_ROOT / "reports"
    # BACKEND_ROOT is the directory that contains the scripts package.
    assert (common_module.BACKEND_ROOT / "scripts" / "e2e" / "common.py").exists()

    # Changing the working directory must not move the report directory.
    monkeypatch.chdir(tmp_path)
    assert load_config(_scoped_env(tmp_path)).report_dir == config.report_dir


def test_token_summary_contains_no_token_substring():
    bundle = auth_tokens.TokenBundle(kind="admin", access_token=FAKE_JWT)
    summary = bundle.safe_summary()
    assert "masked" not in summary
    blob = json.dumps(summary)
    for size in (12, 20, 30):
        assert FAKE_JWT[:size] not in blob
    assert set(summary) >= {
        "kind", "token_type", "fingerprint", "expires_at", "verified_endpoint",
        "verified_status",
    }


# ---------------------------------------------------------------------------
# Refinement · before/after count reconciliation
# ---------------------------------------------------------------------------


def test_raw_item_delta_reconciles_with_items_new():
    before = {"raw_items_total": 100, "processed_alerts_total": 50, "published_alerts_total": 10}
    after = {"raw_items_total": 103, "processed_alerts_total": 50, "published_alerts_total": 10}
    deltas, stop = collector_stage.reconcile_counts(before, after, 3, ai_disabled=True)
    assert deltas["raw_items_total"] == 3
    assert stop == ""


def test_raw_item_delta_mismatch_is_a_stop_condition():
    before = {"raw_items_total": 100, "processed_alerts_total": 50, "published_alerts_total": 10}
    after = {"raw_items_total": 110, "processed_alerts_total": 50, "published_alerts_total": 10}
    _, stop = collector_stage.reconcile_counts(before, after, 3, ai_disabled=True)
    assert "items_new=3" in stop


def test_processed_or_published_movement_while_ai_disabled_is_a_stop_condition():
    before = {"raw_items_total": 100, "processed_alerts_total": 50, "published_alerts_total": 10}
    after = {"raw_items_total": 103, "processed_alerts_total": 52, "published_alerts_total": 11}
    _, stop = collector_stage.reconcile_counts(before, after, 3, ai_disabled=True)
    assert "processed_alerts_total changed by 2" in stop
    assert "published_alerts_total changed by 1" in stop

    # With AI running, movement is expected and not a stop condition.
    _, stop_ai_on = collector_stage.reconcile_counts(before, after, 3, ai_disabled=False)
    assert stop_ai_on == ""


def test_stop_condition_maps_to_its_own_exit_code():
    assert int(Exit.STOP_CONDITION) == 6


# ---------------------------------------------------------------------------
# Refinement · post-deploy endpoint enforcement
# ---------------------------------------------------------------------------

from scripts.e2e import production_smoke  # noqa: E402

#: A real alert row, so the removed public-detail check can use a known id
#: rather than an invented one that would 404 regardless.
KNOWN_ALERT_ID = 4242
KNOWN_ALERT = {
    "id": KNOWN_ALERT_ID, "title": "Known alert", "risk_level": "high",
    "signal_score": 80, "published_at": "2026-08-01T00:00:00Z",
    "source_published_at": None,
}

#: A distinct Supabase token. Reusing the admin JWT would make the
#: "Supabase token must not authorize an admin route" check vacuous.
FAKE_SUPABASE_JWT = (
    "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJzdWIiOiJzdXBhLXVzZXItMSIsImV4cCI6NDEwMjQ0NDgwMH0"
    ".c3VwYWJhc2Utc2lnbmF0dXJl"
)

#: Endpoints that ship in the pending release: optional before, required after.
PENDING_RELEASE_ENDPOINTS = (
    production_smoke.ADMIN_SOURCE_HEALTH_PATH,
    "/api/v1/admin/sources/1/health",
    production_smoke.ADMIN_SYSTEM_SUMMARY_PATH,
    production_smoke.ADMIN_CATEGORIES_PATH,
    production_smoke.SUBSCRIBER_TOP_PATH,
    production_smoke.SUBSCRIBER_CATEGORIES_PATH,
)


def _smoke_handler(missing: tuple[str, ...] = ()):
    """A backend where `missing` paths 404 and everything else behaves.

    Authenticated paths accept only the fixture token, the way a real backend
    would — a mock that honours any Authorization header cannot tell a valid
    token from a malformed one, and the negative checks would pass vacuously.
    """

    def _admin_authed(request: httpx.Request) -> bool:
        """Internal JWT only — a Supabase token must not pass here."""
        return request.headers.get("authorization") == f"Bearer {FAKE_JWT}"

    def _subscriber_authed(request: httpx.Request) -> bool:
        return request.headers.get("authorization") == f"Bearer {FAKE_SUPABASE_JWT}"

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        unauthenticated = httpx.Response(401, json={"detail": "Not authenticated"})
        # Supabase password grant, so the subscriber sections actually run.
        if path == auth_tokens.SUPABASE_TOKEN_PATH:
            return httpx.Response(200, json={
                "access_token": FAKE_SUPABASE_JWT, "token_type": "bearer",
                "refresh_token": "REFRESH-SECRET-VALUE", "expires_in": 3600})
        if path in missing:
            return httpx.Response(404, json={"detail": "Not Found"})
        if path == auth_tokens.ADMIN_LOGIN_PATH:
            return httpx.Response(200, json={
                "access_token": FAKE_JWT, "token_type": "bearer", "expires_in": 60,
                "user": {"id": 1, "email": "a@b.co", "role": "admin", "is_active": True}})
        if path == production_smoke.HEALTH_PATH:
            return httpx.Response(200, json={"status": "ok"})
        if path == production_smoke.PUBLIC_ALERTS_PATH:
            return httpx.Response(200, json={"alerts": [KNOWN_ALERT]})
        if path == f"/api/v1/subscriber/alerts/{KNOWN_ALERT_ID}":
            if not _subscriber_authed(request):
                return unauthenticated
            return httpx.Response(200, json=KNOWN_ALERT)
        # Slice 3B.2P removed these; the mock models the cleaned-up release.
        if path in (*production_smoke.REMOVED_JINJA_PATHS,
                    *production_smoke.REMOVED_PUBLIC_PATHS):
            return httpx.Response(404, json={"detail": "Not Found"})
        if path == f"/api/alerts/{KNOWN_ALERT_ID}":
            return httpx.Response(404, json={"detail": "Not Found"})
        if path == production_smoke.ADMIN_SOURCES_PATH:
            if not _admin_authed(request):
                return unauthenticated
            return httpx.Response(200, json=[{"id": 1, "name": "SEC Press Releases"}])
        if path == production_smoke.ADMIN_SOURCE_HEALTH_PATH:
            return httpx.Response(200, json=[_health_record()])
        if path == "/api/v1/admin/sources/1/health":
            return httpx.Response(200, json={
                "health": _health_record(),
                "recent_runs": [{"id": 1, "run_started_at": "2026-08-02T10:00:00Z",
                                 "items_skipped_external": 0}]})
        if path == "/api/v1/sources/1/runs":
            return httpx.Response(200, json=[{
                "id": 1, "run_started_at": "2026-08-02T10:00:00Z", "status": "success",
                "items_fetched": 0, "items_new": 0, "items_skipped_url": 0,
                "items_skipped_content": 0, "items_skipped_invalid": 0,
                "items_skipped_external": 0}])
        if path == production_smoke.ADMIN_SYSTEM_SUMMARY_PATH:
            return httpx.Response(200, json=_summary(by_state={"healthy": 10},
                                                     sources_total=10))
        if path in (production_smoke.ADMIN_CATEGORIES_PATH,
                    production_smoke.SUBSCRIBER_CATEGORIES_PATH):
            return httpx.Response(200, json=_categories_payload())
        if path == production_smoke.ADMIN_ALERTS_PATH:
            return httpx.Response(200, json=[KNOWN_ALERT])
        if path == production_smoke.SUBSCRIBER_ALERTS_PATH:
            if not _subscriber_authed(request):
                return unauthenticated
            return httpx.Response(200, json={"alerts": [KNOWN_ALERT]})
        if path == production_smoke.SUBSCRIBER_STATS_PATH:
            return httpx.Response(200, json={"total": 0})
        if path == production_smoke.SUBSCRIBER_SEARCH_PATH:
            return httpx.Response(200, json={"alerts": []})
        if path == production_smoke.SUBSCRIBER_TOP_PATH:
            return httpx.Response(
                200, json={"alerts": [], "is_fallback": False, "message": None}
            )
        if path == production_smoke.CLIENT_ALERTS_PATH:
            if not _admin_authed(request):
                return unauthenticated
            return httpx.Response(200, json=[{"id": 7, "title": "x"}])
        if path == "/api/v1/client/alerts/7":
            if not _admin_authed(request):
                return unauthenticated
            return httpx.Response(200, json={"id": 7, "title": "x"})
        return httpx.Response(404, json={"detail": "Not Found"})

    return handler


async def _run_smoke(handler, *, post_deploy: bool):
    config = _config(target_env="local", api_base_url="http://api.test")
    transport = httpx.MockTransport(handler)
    original = common_module.make_client
    patched = lambda cfg, **kw: httpx.AsyncClient(  # noqa: E731
        base_url=cfg.api_base_url, transport=transport)
    common_module.make_client = patched
    production_smoke.make_client = patched
    auth_tokens.make_client = patched

    # The Supabase client is constructed directly inside
    # get_subscriber_access_token, so it does not go through make_client; route
    # it through the same transport or the subscriber sections never run.
    real_async_client = httpx.AsyncClient
    auth_tokens.httpx.AsyncClient = lambda *a, **kw: real_async_client(
        *a, **{**kw, "transport": transport})
    try:
        return await production_smoke.run_smoke(config, post_deploy=post_deploy)
    finally:
        common_module.make_client = original
        production_smoke.make_client = original
        auth_tokens.make_client = original
        auth_tokens.httpx.AsyncClient = real_async_client


@pytest.mark.asyncio
async def test_pre_deploy_404_skips_only_pending_endpoints():
    results = await _run_smoke(_smoke_handler(PENDING_RELEASE_ENDPOINTS), post_deploy=False)
    skipped = {r.name for r in results.results if r.skipped}
    assert "source health list" in skipped
    assert "subscriber top alerts" in skipped
    # Endpoints that already exist are still required and still pass.
    assert not [r for r in results.failed if r.name == "admin sources list"]


@pytest.mark.asyncio
async def test_post_deploy_404_fails_and_exits_one():
    """With the whole pending release absent, post-deploy mode must fail.

    Note which check fails first: post-deploy admin verification targets
    /api/v1/admin/system/health-summary, so when that endpoint is missing the
    admin token cannot be verified and the admin section never runs. That is the
    correct ordering — the run still fails, and nothing pending is skipped.
    """
    results = await _run_smoke(_smoke_handler(PENDING_RELEASE_ENDPOINTS), post_deploy=True)

    assert results.failed
    assert int(results.exit_code()) == int(Exit.ASSERTION_FAILED) == 1

    failed = {r.name for r in results.failed}
    assert "subscriber top alerts" in failed
    assert "subscriber categories" in failed

    # Nothing belonging to the pending release may be skipped in post-deploy mode.
    skipped_pending = [
        r for r in results.results if r.skipped and r.endpoint in PENDING_RELEASE_ENDPOINTS
    ]
    assert not skipped_pending, [r.name for r in skipped_pending]


@pytest.mark.asyncio
async def test_post_deploy_fails_when_only_source_health_is_missing():
    """Source Health absent, everything else present: the admin section runs and fails."""
    results = await _run_smoke(
        _smoke_handler((production_smoke.ADMIN_SOURCE_HEALTH_PATH,)), post_deploy=True
    )
    assert "source health list" in {r.name for r in results.failed}
    assert int(results.exit_code()) == 1


@pytest.mark.parametrize("missing", PENDING_RELEASE_ENDPOINTS)
@pytest.mark.asyncio
async def test_every_required_post_deploy_endpoint_is_enforced(missing):
    """Dropping any one required endpoint must fail the post-deploy run."""
    results = await _run_smoke(_smoke_handler((missing,)), post_deploy=True)
    assert results.failed, f"{missing} 404 did not fail the post-deploy run"
    assert not any(r.skipped and r.endpoint == missing for r in results.results)


@pytest.mark.asyncio
async def test_clean_backend_passes_post_deploy():
    results = await _run_smoke(_smoke_handler(), post_deploy=True)
    admin_failures = [
        r for r in results.failed if "subscriber authentication" not in r.name
    ]
    assert not admin_failures, [r.name for r in admin_failures]


@pytest.mark.asyncio
async def test_both_client_routes_are_covered():
    results = await _run_smoke(_smoke_handler(), post_deploy=True)
    names = {r.name for r in results.results}
    assert {"client list without token → 401", "client list with admin token → 200",
            "client detail without token → 401", "client detail with admin token → 200",
            "client detail schema"} <= names
    endpoints = {r.endpoint for r in results.results}
    assert production_smoke.CLIENT_ALERTS_PATH in endpoints
    assert production_smoke.CLIENT_ALERT_DETAIL_PATH in endpoints


@pytest.mark.asyncio
async def test_category_round_trip_uses_a_returned_value_against_the_real_filter():
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path in (production_smoke.ADMIN_ALERTS_PATH,
                                production_smoke.SUBSCRIBER_ALERTS_PATH):
            category = request.url.params.get("category")
            if category:
                seen.append(category)
                if category not in ALERT_CATEGORIES:
                    return httpx.Response(422, json={"detail": "bad category"})
        return _smoke_handler()(request)

    results = await _run_smoke(handler, post_deploy=True)
    assert seen, "no category filter request was made"
    assert all(value in ALERT_CATEGORIES for value in seen)
    round_trips = [r for r in results.results if "category round-trip" in r.name]
    assert round_trips and all(r.passed for r in round_trips)


@pytest.mark.asyncio
async def test_source_published_date_filter_check_skips_without_a_dated_sample():
    """KNOWN_ALERT has source_published_at=None — the default mock has nothing
    to build a boundary from, so the check must skip, not fail or error."""
    results = await _run_smoke(_smoke_handler(), post_deploy=True)
    checks_run = [r for r in results.results if "source date filters" in r.name]
    assert checks_run and all(r.skipped for r in checks_run)
    assert not any(
        "source_published_from" in r.name or "source_published_to" in r.name
        or "exact boundary" in r.name
        for r in results.results
    )


@pytest.mark.asyncio
async def test_source_published_date_filter_check_passes_with_a_dated_sample():
    """A published row with a real source_published_at lets the check build a
    Z boundary and a non-UTC-offset boundary for the same instant, exercise
    both source_published_from (lower bound) and source_published_to (upper
    bound), call both Admin and Subscriber, confirm every returned row is
    inside the range, and confirm the sample itself is still returned at the
    exact inclusive boundary — proving the hotfix's own E2E addition actually
    exercises its logic end to end."""
    dated_alert = {**KNOWN_ALERT, "id": 9001, "source_published_at": "2026-06-01T00:00:00Z"}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == production_smoke.ADMIN_ALERTS_PATH:
            return httpx.Response(200, json=[dated_alert])
        if path == production_smoke.SUBSCRIBER_ALERTS_PATH:
            if request.headers.get("authorization") != f"Bearer {FAKE_SUPABASE_JWT}":
                return httpx.Response(401, json={"detail": "Not authenticated"})
            return httpx.Response(200, json={"alerts": [dated_alert]})
        return _smoke_handler()(request)

    results = await _run_smoke(handler, post_deploy=True)
    checks_run = [
        r for r in results.results
        if "source_published_from" in r.name or "source_published_to" in r.name
        or "exact boundary" in r.name
    ]
    # admin+subscriber x (from/to x z/offset) = 8, plus one exact-boundary
    # check per surface = 10.
    assert len(checks_run) == 10, [r.name for r in checks_run]
    assert all(r.passed and not r.skipped for r in checks_run), [
        (r.name, r.detail) for r in checks_run
    ]

    names = {r.name for r in checks_run}
    for label in ("admin", "subscriber"):
        assert f"{label} source_published_at exact boundary (inclusive)" in names
        for param in ("source_published_from", "source_published_to"):
            for bound_repr in ("z", "offset"):
                assert f"{label} {param} ({bound_repr})" in names, names


@pytest.mark.asyncio
async def test_source_published_date_filter_check_fails_loudly_on_a_from_500():
    """If source_published_from itself 500s, the check must FAIL — not skip,
    not silently pass — so a post-deploy run cannot go green over the bug."""
    dated_alert = {**KNOWN_ALERT, "id": 9002, "source_published_at": "2026-06-01T00:00:00Z"}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        params = request.url.params
        if path == production_smoke.ADMIN_ALERTS_PATH and "source_published_from" in params:
            return httpx.Response(500, text="Internal Server Error")
        if path == production_smoke.ADMIN_ALERTS_PATH:
            return httpx.Response(200, json=[dated_alert])
        return _smoke_handler()(request)

    results = await _run_smoke(handler, post_deploy=True)
    checks_run = [r for r in results.results if r.name.startswith("admin source_published_from")]
    assert checks_run and all(not r.passed and not r.skipped for r in checks_run), [
        (r.name, r.detail) for r in checks_run
    ]


@pytest.mark.asyncio
async def test_source_published_date_filter_check_fails_loudly_on_a_to_500():
    """If source_published_to itself 500s, the check must FAIL — not skip, not
    silently pass — so a post-deploy run cannot go green over the bug."""
    dated_alert = {**KNOWN_ALERT, "id": 9005, "source_published_at": "2026-06-01T00:00:00Z"}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        params = request.url.params
        if path == production_smoke.ADMIN_ALERTS_PATH and "source_published_to" in params:
            return httpx.Response(500, text="Internal Server Error")
        if path == production_smoke.ADMIN_ALERTS_PATH:
            return httpx.Response(200, json=[dated_alert])
        return _smoke_handler()(request)

    results = await _run_smoke(handler, post_deploy=True)
    checks_run = [r for r in results.results if r.name.startswith("admin source_published_to")]
    assert checks_run and all(not r.passed and not r.skipped for r in checks_run), [
        (r.name, r.detail) for r in checks_run
    ]


@pytest.mark.asyncio
async def test_source_published_date_filter_check_fails_when_a_returned_row_is_out_of_range():
    """If the backend returns a row whose source_published_at instant falls
    outside the requested source_published_from range, the check must FAIL —
    proving the assertion actually parses and compares real datetime instants
    rather than trusting whatever the backend sends back."""
    dated_alert = {**KNOWN_ALERT, "id": 9003, "source_published_at": "2026-06-01T00:00:00Z"}
    stale_alert = {**KNOWN_ALERT, "id": 9004, "source_published_at": "2025-01-01T00:00:00Z"}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        params = request.url.params
        if path == production_smoke.ADMIN_ALERTS_PATH:
            if "source_published_from" in params and "source_published_to" not in params:
                # A from-only request: the backend wrongly includes a row
                # that predates the requested lower bound.
                return httpx.Response(200, json=[dated_alert, stale_alert])
            return httpx.Response(200, json=[dated_alert])
        return _smoke_handler()(request)

    results = await _run_smoke(handler, post_deploy=True)
    from_checks = [r for r in results.results if r.name.startswith("admin source_published_from")]
    assert from_checks and all(not r.passed for r in from_checks), [
        (r.name, r.detail) for r in from_checks
    ]


@pytest.mark.asyncio
async def test_backend_transport_failure_becomes_one_recorded_failure():
    """A dead backend must not abort the run with a traceback."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == auth_tokens.ADMIN_LOGIN_PATH:
            raise httpx.ConnectError("connection refused")
        return _smoke_handler()(request)

    results = await _run_smoke(handler, post_deploy=False)
    auth_failures = [r for r in results.failed if r.name == "admin authentication verified"]
    assert len(auth_failures) == 1
    # Independent read-only sections still ran.
    assert any(r.name == "health endpoint responds" and r.passed for r in results.results)
    assert FAKE_JWT not in json.dumps(results.summary())
    assert FAKE_SUPABASE_JWT not in json.dumps(results.summary())


# ---------------------------------------------------------------------------
# Release-aware semantics (found by the first real production run, 2026-08-02)
#
# Two endpoints exist in BOTH releases but behave differently, so a 404-based
# skip cannot distinguish them. Asserting the new contract against the deployed
# old one produced two false failures against a perfectly healthy production API.
# ---------------------------------------------------------------------------

#: Exactly what production returned pre-deploy: the legacy all-time selection,
#: platform publication date, much older source dates.
PRODUCTION_LEGACY_TOP_ALERTS = {
    "alerts": [
        {"id": 180, "risk_level": "critical", "signal_score": 92,
         "published_at": "2026-06-20T15:41:24.733979Z",
         "source_published_at": "2026-01-14T10:30:00Z"},
        {"id": 163, "risk_level": "critical", "signal_score": 92,
         "published_at": "2026-06-20T15:41:24.733979Z",
         "source_published_at": "2025-12-08T01:00:00Z"},
        {"id": 258, "risk_level": "critical", "signal_score": 92,
         "published_at": "2026-06-20T15:41:24.733979Z",
         "source_published_at": "2025-06-13T14:48:00Z"},
    ]
}

#: Exactly what production returned pre-deploy for a RunLog: migrations 0012 and
#: 0013 have not run, so the split skip counters do not exist yet.
PRODUCTION_LEGACY_RUN = {
    "id": 3971, "run_started_at": "2026-08-02T16:10:41Z", "status": "success",
    "items_fetched": 10, "items_new": 2, "items_duplicate": 8,
}


def test_legacy_run_log_shape_passes_pre_deploy():
    """Pre-deploy, run_logs has no split counters — that is not a defect."""
    assert checks.check_run_log_counters(PRODUCTION_LEGACY_RUN, require_split=False) == []


def test_legacy_run_log_shape_fails_post_deploy():
    problems = checks.check_run_log_counters(PRODUCTION_LEGACY_RUN, require_split=True)
    assert any("migrations 0012 and 0013" in p for p in problems)


def test_split_counter_identity_still_enforced_when_present():
    run = {"items_fetched": 10, "items_new": 3, "items_skipped_url": 5,
           "items_skipped_content": 1, "items_skipped_invalid": 1,
           "items_skipped_external": 0}
    assert checks.check_run_log_counters(run) == []
    run["items_skipped_external"] = 4
    assert any("does not balance" in p for p in checks.check_run_log_counters(run))


def test_partial_split_counters_are_rejected():
    """A half-migrated shape is a real problem, not a legacy one."""
    run = dict(PRODUCTION_LEGACY_RUN, items_skipped_url=1)
    assert any("partial split counters" in p
               for p in checks.check_run_log_counters(run, require_split=False))


def test_items_new_cannot_exceed_items_fetched_in_either_shape():
    run = dict(PRODUCTION_LEGACY_RUN, items_new=99)
    assert any("exceeds items_fetched" in p
               for p in checks.check_run_log_counters(run, require_split=False))


def test_legacy_top_alerts_pass_pre_deploy():
    """The old all-time endpoint reports the platform date — not a violation."""
    assert checks.check_top_alerts(
        PRODUCTION_LEGACY_TOP_ALERTS, weekly_contract=False) == []


def test_legacy_top_alerts_fail_post_deploy():
    """Legacy payloads have no risk_band or is_fallback/message — the final
    contract's fields, not the (removed) date-equality rule."""
    problems = checks.check_top_alerts(
        PRODUCTION_LEGACY_TOP_ALERTS, weekly_contract=True)
    assert any("is_fallback is not present" in p for p in problems)
    assert all("risk_band" in p and "neither critical nor high" in p
               for p in problems if "risk_band" in p)
    assert sum("risk_band" in p for p in problems) == 3
    assert not any("should equal source_published_at" in p for p in problems)


def test_shape_rules_apply_in_both_modes():
    """Cap of three, and source_published_at present, hold either way."""
    too_many = {"alerts": PRODUCTION_LEGACY_TOP_ALERTS["alerts"] * 2}
    for weekly in (True, False):
        assert any("maximum is 3" in p
                   for p in checks.check_top_alerts(too_many, weekly_contract=weekly))

    missing_field = {"alerts": [{"id": 1, "published_at": "2026-08-01T00:00:00Z"}]}
    for weekly in (True, False):
        assert any("separately present" in p
                   for p in checks.check_top_alerts(missing_field, weekly_contract=weekly))


def test_medium_risk_allowed_pre_deploy_rejected_post_deploy():
    """The legacy implementation admits Medium; the weekly contract does not."""
    medium = {"alerts": [{"risk_band": "medium",
                          "published_at": "2026-08-01T00:00:00Z",
                          "source_published_at": "2026-08-01T00:00:00Z"}]}
    assert checks.check_top_alerts(medium, weekly_contract=False) == []
    assert any("neither critical nor high" in p
               for p in checks.check_top_alerts(medium, weekly_contract=True))


# ---------------------------------------------------------------------------
# Slice 3B.2P — removed surface expectations
# ---------------------------------------------------------------------------


def test_harness_no_longer_expects_the_jinja_interface():
    """The old 'stays protected' / 'route retained' expectations are gone."""
    import inspect

    src = inspect.getsource(production_smoke)
    assert "legacy dashboard stays protected" not in src
    assert "legacy login route retained" not in src


def test_removed_surface_constants_cover_the_cleanup():
    assert set(production_smoke.REMOVED_JINJA_PATHS) >= {"/login", "/logout", "/dashboard"}
    assert set(production_smoke.REMOVED_PUBLIC_PATHS) == {
        "/api/alerts/top", "/api/alerts/stats", "/api/search/alerts"
    }
    # Only GETs — the harness must never POST at production to prove a 404.
    assert all(p.startswith("/") for p in production_smoke.REMOVED_JINJA_PATHS)


@pytest.mark.asyncio
async def test_post_deploy_requires_removed_paths_to_be_404():
    """A release that still serves a removed path must fail post-deploy."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/dashboard":
            return httpx.Response(302, headers={"location": "/login"})  # not removed
        return _smoke_handler()(request)

    results = await _run_smoke(handler, post_deploy=True)
    failed = {r.name for r in results.failed}
    assert "removed: /dashboard" in failed


@pytest.mark.asyncio
async def test_pre_deploy_does_not_fail_on_a_still_present_removed_path():
    """Before deployment the old release still serves them — that is not a failure."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/dashboard":
            return httpx.Response(302, headers={"location": "/login"})
        return _smoke_handler()(request)

    results = await _run_smoke(handler, post_deploy=False)
    assert "removed: /dashboard" not in {r.name for r in results.failed}
    assert any(r.name == "removed: /dashboard" and r.skipped for r in results.results)


@pytest.mark.asyncio
async def test_retained_landing_feed_is_asserted_in_both_modes():
    for post_deploy in (False, True):
        results = await _run_smoke(_smoke_handler(), post_deploy=post_deploy)
        hit = [r for r in results.results if r.name == "retained: /api/alerts still 200"]
        assert hit and hit[0].passed, f"post_deploy={post_deploy}"


# ---------------------------------------------------------------------------
# Slice 3B.2P refinement — all four Public removals, with a known-existing id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_deploy_covers_all_four_public_removals():
    """Every removed Public route is checked, including the detail route."""
    results = await _run_smoke(_smoke_handler(), post_deploy=True)
    checked = {r.endpoint for r in results.results if r.name.startswith("removed: ")}
    assert {"/api/alerts/top", "/api/alerts/stats", "/api/search/alerts"} <= checked
    assert f"/api/alerts/{KNOWN_ALERT_ID}" in checked, (
        "the parameterised public detail route must be verified too"
    )
    assert not [r for r in results.failed if r.name.startswith("removed: ")]


@pytest.mark.asyncio
async def test_detail_check_uses_a_known_existing_id_from_a_retained_endpoint():
    results = await _run_smoke(_smoke_handler(), post_deploy=True)
    assert results.context["known_alert_id"] == KNOWN_ALERT_ID
    # Subscriber alerts is the preferred source.
    assert results.context["known_alert_id_source"] == "subscriber alerts"
    assert any(r.name == "known alert id discovered" and r.passed
               for r in results.results)


@pytest.mark.asyncio
async def test_old_public_detail_returning_200_fails_post_deploy():
    """A release that still serves the detail route must not pass."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == f"/api/alerts/{KNOWN_ALERT_ID}":
            return httpx.Response(200, json=KNOWN_ALERT)   # not yet removed
        return _smoke_handler()(request)

    results = await _run_smoke(handler, post_deploy=True)
    failed = {r.name for r in results.failed}
    assert f"removed: /api/alerts/{KNOWN_ALERT_ID}" in failed


@pytest.mark.asyncio
async def test_cleaned_public_detail_returning_404_passes_post_deploy():
    results = await _run_smoke(_smoke_handler(), post_deploy=True)
    hit = [r for r in results.results
           if r.name == f"removed: /api/alerts/{KNOWN_ALERT_ID}"]
    assert hit and hit[0].passed and hit[0].status_code == 404


@pytest.mark.asyncio
async def test_unavailable_id_cannot_produce_a_false_pass():
    """With no id obtainable, post-deploy must fail rather than skip silently."""

    def handler(request: httpx.Request) -> httpx.Response:
        # Every listing is empty, so no id can be discovered.
        if request.url.path in (production_smoke.SUBSCRIBER_ALERTS_PATH,
                                production_smoke.PUBLIC_ALERTS_PATH):
            return httpx.Response(200, json={"alerts": []})
        if request.url.path == production_smoke.ADMIN_ALERTS_PATH:
            return httpx.Response(200, json=[])
        return _smoke_handler()(request)

    results = await _run_smoke(handler, post_deploy=True)
    failed = {r.name for r in results.failed}
    assert "removed: /api/alerts/{known_id}" in failed
    assert int(results.exit_code()) == int(Exit.ASSERTION_FAILED)

    # Pre-deploy the same situation is a skip, not a failure.
    pre = await _run_smoke(handler, post_deploy=False)
    assert "removed: /api/alerts/{known_id}" not in {r.name for r in pre.failed}


@pytest.mark.asyncio
async def test_retained_subscriber_detail_is_verified_alongside_the_removal():
    results = await _run_smoke(_smoke_handler(), post_deploy=True)
    hit = [r for r in results.results if r.name == "retained: subscriber alert detail"]
    assert hit and hit[0].passed and hit[0].status_code == 200


@pytest.mark.asyncio
async def test_pre_deploy_records_the_old_detail_route_without_failing():
    """Before deployment the old release still serves it — not a failure."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == f"/api/alerts/{KNOWN_ALERT_ID}":
            return httpx.Response(200, json=KNOWN_ALERT)
        return _smoke_handler()(request)

    results = await _run_smoke(handler, post_deploy=False)
    assert not [r for r in results.failed if r.name.startswith("removed: ")]
    assert any(r.skipped and r.name == f"removed: /api/alerts/{KNOWN_ALERT_ID}"
               for r in results.results)
