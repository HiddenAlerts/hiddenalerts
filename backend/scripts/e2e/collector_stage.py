"""Controlled, one-source-at-a-time collector stage runner.

This is the only script in the harness that can change production state, and it
is built so that doing so by accident is very hard: **dry-run is the default**,
and execution requires eight independent conditions to hold at once. Any one of
them failing refuses the run rather than proceeding with a warning.

It triggers exactly one source per invocation and never advances to the next by
itself. Deciding to continue is a human step, taken after reading the report.

A stored RawItem is **not** a published alert. Reports here count RawItems and
say so explicitly, because the difference is the difference between "we collected
an article" and "a subscriber was shown an alert".
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from scripts.e2e import api_assertions as checks
from scripts.e2e.auth_tokens import (
    ADMIN_VERIFY_PATH_POST_DEPLOY,
    TokenBundle,
    get_admin_access_token,
)
from scripts.e2e.common import (
    AssertionFailure,
    AuthError,
    ConfigError,
    E2EConfig,
    Exit,
    ResultSet,
    SafetyRefusal,
    load_config,
    make_client,
    parse_json,
    redact,
    request_with_retry,
    results_markdown,
    timestamp_slug,
    utc_now,
    write_reports,
)

#: The phrase an operator must type to confirm they understand the state of the
#: system. Deliberately describes the precondition, not the action.
CONFIRMATION_PHRASE = "DEPLOYED_SCHEDULER_PAUSED"

#: The migration revision this release requires.
REQUIRED_REVISION = "0013"

#: Second confirmation, required when the API cannot prove AI is disabled. The
#: operator must check the deployed container's environment before supplying it.
AI_CONFIRMATION_PHRASE = "AI_PROCESSING_DISABLED_CONFIRMED"

#: RunLog statuses that mean the run is over.
TERMINAL_STATUSES = frozenset({"success", "failed", "partial", "error"})

#: How old a recovery preview may be and still authorize a trigger. Upstream
#: listings change continuously, so a stale preview is evidence about a different
#: state of the world than the one about to be collected.
MAX_PREVIEW_AGE_SECONDS = 15 * 60

#: Preview tool identity. Anything else is not a report this harness trusts.
PREVIEW_TOOL_NAME = "source_recovery_preview"

#: Per-source preview statuses that describe a source ready to be collected.
ACCEPTED_PREVIEW_STATUSES = frozenset({"listing_ready", "empty_upstream"})

#: Named stage plans. Sources are resolved to production ids **by name** at
#: runtime — ids are not hardcoded, because they differ between environments.
#: Every stage lists its sources individually: each is triggered on its own
#: invocation, and nothing here loops over them.
STAGE_PLANS: dict[str, tuple[str, ...]] = {
    "A": ("SEC Press Releases", "BleepingComputer"),
    "B": ("FTC RSS Feeds", "DOJ Press Releases"),
    "C": ("FinCEN Press Releases", "IC3 Press Releases",
          "KrebsOnSecurity", "FBI News Blog RSS"),
    "D": ("FBI National Press Releases",),
    "E": ("FBI in the News RSS",),
}

#: Stages whose volume profile needs its own acknowledgement before execution.
STAGE_EXTRA_CONFIRMATION = {
    "D": "FBI_NATIONAL_VOLUME_ACKNOWLEDGED",
    "E": "FBI_IN_THE_NEWS_LOW_YIELD_ACKNOWLEDGED",
}


@dataclass
class StageContext:
    """Everything observed before and after a stage, for the report."""

    source_id: int
    source_name: str
    executed: bool = False
    before_health: dict[str, Any] = field(default_factory=dict)
    after_health: dict[str, Any] = field(default_factory=dict)
    latest_run_before: dict[str, Any] = field(default_factory=dict)
    new_run: dict[str, Any] = field(default_factory=dict)
    preview: dict[str, Any] = field(default_factory=dict)
    trigger_status: int | None = None
    second_trigger_status: int | None = None
    poll_seconds: float = 0.0
    summary_before: dict[str, Any] = field(default_factory=dict)
    summary_after: dict[str, Any] = field(default_factory=dict)
    count_deltas: dict[str, int] = field(default_factory=dict)
    stop_condition: str = ""


# ---------------------------------------------------------------------------
# Read-only observation
# ---------------------------------------------------------------------------


async def fetch_sources(client: httpx.AsyncClient, header: dict[str, str]) -> list[dict]:
    response, _ = await request_with_retry(client, "GET", "/api/v1/sources", headers=header)
    if response.status_code != 200:
        raise SafetyRefusal(f"cannot list sources (HTTP {response.status_code})")
    payload = parse_json(response, "sources")
    return [s for s in payload if isinstance(s, dict)] if isinstance(payload, list) else []


async def fetch_source_health(
    client: httpx.AsyncClient, header: dict[str, str], source_id: int
) -> dict[str, Any]:
    path = f"/api/v1/admin/sources/{source_id}/health"
    response, _ = await request_with_retry(client, "GET", path, headers=header)
    if response.status_code != 200:
        raise SafetyRefusal(
            f"Source Health unavailable for source {source_id} "
            f"(HTTP {response.status_code}) — refusing to proceed blind"
        )
    return parse_json(response, "source health detail")


async def fetch_system_summary(
    client: httpx.AsyncClient, header: dict[str, str]
) -> dict[str, Any]:
    response, _ = await request_with_retry(
        client, "GET", ADMIN_VERIFY_PATH_POST_DEPLOY, headers=header
    )
    if response.status_code != 200:
        raise SafetyRefusal(
            f"system health summary unavailable (HTTP {response.status_code}) — "
            f"refusing to proceed without release identity and scheduler state"
        )
    return parse_json(response, "system health summary")


async def fetch_runs(
    client: httpx.AsyncClient, header: dict[str, str], source_id: int, limit: int = 5
) -> list[dict]:
    response, _ = await request_with_retry(
        client, "GET", f"/api/v1/sources/{source_id}/runs",
        headers=header, params={"limit": limit},
    )
    if response.status_code != 200:
        raise SafetyRefusal(f"cannot read run history (HTTP {response.status_code})")
    payload = parse_json(response, "runs")
    return [r for r in payload if isinstance(r, dict)] if isinstance(payload, list) else []


# ---------------------------------------------------------------------------
# Safety gates
# ---------------------------------------------------------------------------


def resolve_source(sources: list[dict], source_id: int, expected_name: str) -> dict:
    """Find the source and refuse if the supplied name does not match the id.

    The id/name cross-check exists because ids differ between environments and a
    stale runbook is the most likely way to trigger the wrong source.
    """
    match = next((s for s in sources if s.get("id") == source_id), None)
    if match is None:
        raise SafetyRefusal(f"source id {source_id} does not exist")

    actual = str(match.get("name", ""))
    if not names_match(actual, expected_name):
        raise SafetyRefusal(
            f"source id {source_id} is {actual!r}, which does not exactly match "
            f"the expected name {expected_name!r} — refusing to trigger the wrong "
            f"source. Use the complete production source name."
        )
    return match


def names_match(actual: str, expected: str) -> bool:
    """Normalized **exact** comparison, not a substring test.

    Substring matching would let ``"SEC"`` authorize a run against any source
    whose name happens to contain it, which is precisely the class of mistake the
    id/name cross-check exists to prevent. Whitespace and case are normalized;
    nothing else is.
    """
    return actual.strip().casefold() == expected.strip().casefold()


# ---------------------------------------------------------------------------
# Preview report — the only trusted source of expected volume
# ---------------------------------------------------------------------------


@dataclass
class PreviewEvidence:
    """A validated recovery-preview record for exactly one source."""

    prospective_unseen: int
    source_name: str
    status: str
    generated_at: datetime
    age_seconds: float
    database_revision: str
    config_changed: bool
    branch: str = ""
    commit: str = ""

    def summary(self) -> dict[str, Any]:
        return {
            "prospective_unseen": self.prospective_unseen,
            "source_name": self.source_name,
            "status": self.status,
            "generated_at": self.generated_at.isoformat(),
            "age_seconds": round(self.age_seconds, 1),
            "database_revision": self.database_revision,
            "config_changed": self.config_changed,
            "branch": self.branch,
            "commit": self.commit,
        }


def load_preview_evidence(
    path: str | Path,
    *,
    source_id: int,
    expected_name: str,
    max_unseen: int,
    now: datetime | None = None,
    max_age_seconds: float = MAX_PREVIEW_AGE_SECONDS,
) -> PreviewEvidence:
    """Validate a `source_recovery_preview` JSON report and extract one source.

    The expected volume for a trigger must come from a **machine-produced,
    freshly-generated, read-only** observation — not from a number an operator
    typed. A typo in a hand-entered `--max-unseen` is invisible; a stale or
    mismatched report is not, because everything about it is checked here.

    Raises SafetyRefusal on anything that makes the report untrustworthy.
    """
    now = now or datetime.now(timezone.utc)
    path = Path(path)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SafetyRefusal(f"cannot read preview report {path}: {exc.strerror}") from None
    except json.JSONDecodeError as exc:
        raise SafetyRefusal(f"preview report is not valid JSON: {exc.msg}") from None

    if not isinstance(document, dict):
        raise SafetyRefusal("preview report must be a JSON object")

    if document.get("tool") != PREVIEW_TOOL_NAME:
        raise SafetyRefusal(
            f"preview report tool is {document.get('tool')!r}, expected "
            f"{PREVIEW_TOOL_NAME!r}"
        )
    if document.get("read_only") is not True:
        raise SafetyRefusal("preview report is not marked read_only")
    if document.get("read_only_transaction_enforced") is not True:
        raise SafetyRefusal("preview report did not enforce a read-only transaction")
    if document.get("database_counts_match") is not True:
        raise SafetyRefusal("preview report row counts changed during the preview")

    revision = str(document.get("database_revision", ""))
    if revision != REQUIRED_REVISION:
        raise SafetyRefusal(
            f"preview was taken at migration revision {revision or '<unknown>'}, "
            f"expected {REQUIRED_REVISION} — it describes a different schema"
        )

    errors = document.get("errors") or []
    if errors:
        raise SafetyRefusal(f"preview report contains {len(errors)} error(s)")

    raw_generated = str(document.get("generated_at", ""))
    try:
        generated_at = datetime.fromisoformat(raw_generated.replace("Z", "+00:00"))
    except ValueError:
        raise SafetyRefusal(
            f"preview generated_at {raw_generated!r} is not a parseable timestamp"
        ) from None
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc)

    age = (now - generated_at).total_seconds()
    if age > max_age_seconds:
        raise SafetyRefusal(
            f"preview is {age / 60:.1f} minutes old, maximum is "
            f"{max_age_seconds / 60:.0f} — regenerate it immediately before executing"
        )
    if age < -60:
        raise SafetyRefusal("preview generated_at is in the future; check clocks")

    sources = document.get("sources")
    if not isinstance(sources, list):
        raise SafetyRefusal("preview report has no sources list")

    matches = [
        s for s in sources
        if isinstance(s, dict) and s.get("source_id") == source_id
        and names_match(str(s.get("name", "")), expected_name)
    ]
    if not matches:
        present = [
            f"{s.get('source_id')}:{s.get('name')}" for s in sources
            if isinstance(s, dict)
        ][:6]
        raise SafetyRefusal(
            f"preview report has no record for source id {source_id} named "
            f"{expected_name!r} (contains: {present})"
        )
    if len(matches) > 1:
        raise SafetyRefusal(
            f"preview report is ambiguous: {len(matches)} records match source "
            f"id {source_id}"
        )

    record = matches[0]
    status = str(record.get("status", ""))
    if status not in ACCEPTED_PREVIEW_STATUSES:
        raise SafetyRefusal(
            f"preview status for this source is {status!r}, not one of "
            f"{sorted(ACCEPTED_PREVIEW_STATUSES)}"
        )

    unseen = record.get("prospective_unseen")
    if not isinstance(unseen, int) or isinstance(unseen, bool):
        raise SafetyRefusal("preview prospective_unseen is not an integer")
    if unseen > max_unseen:
        raise SafetyRefusal(
            f"preview reports {unseen} unseen entries for this source, above the "
            f"supplied maximum of {max_unseen}"
        )

    # An overlay simulates configuration that production does not actually have.
    # Volume measured under a simulated config does not describe what a real
    # trigger will collect.
    config_changed = bool(record.get("config_changed"))
    if config_changed:
        raise SafetyRefusal(
            "preview for this source was taken with a configuration overlay; it "
            "does not describe the deployed configuration. Re-run the preview "
            "without an overlay once the configuration change is applied."
        )

    return PreviewEvidence(
        prospective_unseen=unseen,
        source_name=str(record.get("name", "")),
        status=status,
        generated_at=generated_at,
        age_seconds=age,
        database_revision=revision,
        config_changed=config_changed,
        branch=str(document.get("branch") or ""),
        commit=str(document.get("commit") or ""),
    )


def enforce_execution_gates(
    *,
    execute: bool,
    confirmation: str,
    config: E2EConfig,
    summary: dict[str, Any],
    health: dict[str, Any],
    preview: PreviewEvidence | None,
    max_unseen: int | None,
    max_new_raw_items: int | None,
    stage: str | None,
    stage_confirmation: str | None,
    ai_disabled: bool,
    ai_detail: str,
) -> None:
    """Every condition that must hold before a trigger is allowed.

    Raises SafetyRefusal on the first failure. Order is deliberate: cheapest and
    most likely misconfiguration first, so an operator fixes the obvious thing
    before being told about the subtle one.
    """
    if not execute:
        raise SafetyRefusal("--execute not supplied (dry-run is the default)")

    if confirmation != CONFIRMATION_PHRASE:
        raise SafetyRefusal(
            f"confirmation phrase mismatch — expected {CONFIRMATION_PHRASE!r}"
        )

    if not config.is_production:
        raise SafetyRefusal(
            f"target env is {config.target_env!r}; collector execution is only "
            f"defined for a validated production target"
        )

    if max_unseen is None:
        raise SafetyRefusal("--max-unseen is required for execution")
    if max_new_raw_items is None:
        raise SafetyRefusal("--max-new-raw-items is required for execution")

    if preview is None:
        raise SafetyRefusal(
            "--preview-report is required for execution: expected volume must come "
            "from a fresh source_recovery_preview run, never from a hand-entered "
            "number"
        )

    if summary.get("scheduler_running") is not False:
        raise SafetyRefusal(
            f"scheduler_running={summary.get('scheduler_running')!r}; the scheduler "
            f"must be paused before a manual collection run"
        )

    if not ai_disabled:
        raise SafetyRefusal(f"AI processing is not confirmed disabled: {ai_detail}")

    revision = str(summary.get("alembic_revision", ""))
    if revision != REQUIRED_REVISION:
        raise SafetyRefusal(
            f"migration revision is {revision or '<unknown>'}, expected "
            f"{REQUIRED_REVISION}"
        )

    if not revision or not summary.get("sources_total"):
        raise SafetyRefusal("working release identity is unknown — refusing to execute")

    state = (health.get("health") or {}).get("state")
    if state == "disabled":
        raise SafetyRefusal("source is disabled; enable it deliberately or pick another")

    if stage and stage in STAGE_EXTRA_CONFIRMATION:
        required = STAGE_EXTRA_CONFIRMATION[stage]
        if stage_confirmation != required:
            raise SafetyRefusal(
                f"stage {stage} needs --stage-confirmation {required}"
            )


def ai_processing_evidence(
    summary: dict[str, Any], *, operator_confirmation: str | None = None
) -> tuple[bool, str]:
    """Decide whether AI processing is confirmed disabled.

    A paused collection scheduler is **not** evidence that AI is disabled. The
    standalone `process_new_alerts` job runs on its own 30-minute interval and is
    gated by `AI_PROCESSING_ENABLED`, not by whether `collect_all_sources` is
    registered — so inferring one from the other would let a staged collection
    feed the AI pipeline exactly when the point was to hold the backlog.

    Two things count as evidence:

    1. the API explicitly reporting ``ai_processing_enabled=false``;
    2. failing that, the operator supplying :data:`AI_CONFIRMATION_PHRASE` after
       checking the deployed container's environment themselves.
    """
    if "ai_processing_enabled" in summary:
        enabled = bool(summary["ai_processing_enabled"])
        if enabled:
            return False, "API reports ai_processing_enabled=true — AI is running"
        return True, "API reports ai_processing_enabled=false"

    if operator_confirmation == AI_CONFIRMATION_PHRASE:
        return True, (
            "operator confirmed AI_PROCESSING_DISABLED_CONFIRMED after checking the "
            "deployed container environment; the API does not expose the flag"
        )

    return False, (
        "the API does not expose ai_processing_enabled, and a paused collection "
        "scheduler is not evidence about the standalone 30-minute AI job. Verify "
        f"AI_PROCESSING_ENABLED=false in the deployed container, then pass "
        f"--ai-confirmation {AI_CONFIRMATION_PHRASE}"
    )


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


async def trigger_source(
    client: httpx.AsyncClient, header: dict[str, str], source_id: int
) -> httpx.Response:
    """POST the trigger exactly once. Never retried."""
    response, _ = await request_with_retry(
        client, "POST", f"/api/v1/sources/{source_id}/trigger",
        headers=header, attempts=1,
    )
    return response


async def poll_for_new_run(
    client: httpx.AsyncClient,
    header: dict[str, str],
    source_id: int,
    *,
    previous_run_id: int | None,
    timeout_seconds: float,
    interval_seconds: float,
) -> dict[str, Any] | None:
    """Poll run history until a new terminal run appears, or time out."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        runs = await fetch_runs(client, header, source_id)
        for run in runs:
            run_id = run.get("id")
            if previous_run_id is not None and isinstance(run_id, int) and run_id <= previous_run_id:
                continue
            if str(run.get("status", "")).lower() in TERMINAL_STATUSES:
                return run
        await asyncio.sleep(interval_seconds)
    return None


def reconcile_counts(
    before: dict[str, Any], after: dict[str, Any], items_new: int | None,
    *, ai_disabled: bool,
) -> tuple[dict[str, int], str]:
    """Compare instance totals across a run. Returns (deltas, stop_condition).

    With AI confirmed disabled the expectation is exact and worth asserting:
    the collector stores RawItems and nothing else moves. A processed or
    published total that changed anyway means something ran that was supposed to
    be paused — a stop condition, not a warning.

    RawItems are **not** alerts; the two are reported as separate quantities and
    never summed or substituted.
    """
    fields = ("raw_items_total", "processed_alerts_total", "published_alerts_total")
    deltas: dict[str, int] = {}
    for field_name in fields:
        start, end = before.get(field_name), after.get(field_name)
        if isinstance(start, int) and isinstance(end, int):
            deltas[field_name] = end - start

    problems: list[str] = []

    raw_delta = deltas.get("raw_items_total")
    if raw_delta is not None and isinstance(items_new, int) and raw_delta != items_new:
        problems.append(
            f"raw_items_total moved by {raw_delta} but the run reported "
            f"items_new={items_new}"
        )

    if ai_disabled:
        for field_name in ("processed_alerts_total", "published_alerts_total"):
            moved = deltas.get(field_name)
            if moved:
                problems.append(
                    f"{field_name} changed by {moved} while AI processing was "
                    f"confirmed disabled"
                )

    return deltas, "; ".join(problems)


async def run_stage(
    config: E2EConfig,
    *,
    source_id: int,
    expected_name: str,
    execute: bool,
    confirmation: str,
    max_unseen: int | None,
    max_new_raw_items: int | None,
    stage: str | None,
    stage_confirmation: str | None,
    preview_report: str | None,
    ai_confirmation: str | None,
    check_409: bool,
) -> tuple[ResultSet, StageContext]:
    results = ResultSet(f"Collector stage — source {source_id}")
    results.context.update(config.public_summary())
    context = StageContext(source_id=source_id, source_name=expected_name)

    client = make_client(config)
    try:
        admin = await get_admin_access_token(
            config, client, verify_path=ADMIN_VERIFY_PATH_POST_DEPLOY
        )
        header = admin.header
        results.record("admin authentication verified", True,
                       endpoint=admin.verified_endpoint, status_code=admin.verified_status)

        sources = await fetch_sources(client, header)
        source = resolve_source(sources, source_id, expected_name)
        context.source_name = str(source.get("name", expected_name))
        results.record("source id matches expected name", True,
                       f"id {source_id} is {context.source_name!r}")

        summary = await fetch_system_summary(client, header)
        context.summary_before = summary
        results.context["scheduler_running"] = summary.get("scheduler_running")
        results.context["alembic_revision"] = summary.get("alembic_revision")

        ai_ok, ai_detail = ai_processing_evidence(
            summary, operator_confirmation=ai_confirmation
        )
        results.record("AI processing confirmed disabled", ai_ok, ai_detail)

        context.before_health = await fetch_source_health(client, header, source_id)
        problems = checks.check_source_health_detail(context.before_health)
        results.record("source health readable before run", not problems,
                       "; ".join(problems[:4]))

        runs_before = await fetch_runs(client, header, source_id)
        context.latest_run_before = runs_before[0] if runs_before else {}
        previous_run_id = context.latest_run_before.get("id")
        results.context["latest_run_id_before"] = previous_run_id

        preview: PreviewEvidence | None = None
        if preview_report:
            preview = load_preview_evidence(
                preview_report, source_id=source_id, expected_name=expected_name,
                max_unseen=max_unseen if max_unseen is not None else 10**9,
            )
            context.preview = preview.summary()
            results.record(
                "preview report verified", True,
                f"{preview.prospective_unseen} unseen, "
                f"{preview.age_seconds / 60:.1f} min old, revision "
                f"{preview.database_revision}",
            )

        try:
            enforce_execution_gates(
                execute=execute, confirmation=confirmation, config=config,
                summary=summary, health=context.before_health,
                preview=preview, max_unseen=max_unseen,
                max_new_raw_items=max_new_raw_items, stage=stage,
                stage_confirmation=stage_confirmation,
                ai_disabled=ai_ok, ai_detail=ai_detail,
            )
        except SafetyRefusal as refusal:
            results.record(
                "execution gates", not execute,
                f"dry run: {refusal}" if not execute else str(refusal),
            )
            if execute:
                raise
            print("\nDry run complete — no trigger was issued.")
            return results, context

        results.record("execution gates", True, "all gates satisfied")

        response = await trigger_source(client, header, source_id)
        context.trigger_status = response.status_code
        context.executed = True
        results.record(
            "trigger accepted (202)", response.status_code == 202,
            f"expected 202, got {response.status_code}",
            endpoint=f"/api/v1/sources/{source_id}/trigger", method="POST",
            status_code=response.status_code,
        )
        if response.status_code != 202:
            return results, context

        if check_409:
            second = await trigger_source(client, header, source_id)
            context.second_trigger_status = second.status_code
            results.record(
                "immediate re-trigger rejected (409)", second.status_code == 409,
                f"expected 409 claim protection, got {second.status_code}",
                endpoint=f"/api/v1/sources/{source_id}/trigger", method="POST",
                status_code=second.status_code,
            )

        started = time.monotonic()
        new_run = await poll_for_new_run(
            client, header, source_id,
            previous_run_id=previous_run_id if isinstance(previous_run_id, int) else None,
            timeout_seconds=config.run_timeout_seconds,
            interval_seconds=config.poll_interval_seconds,
        )
        context.poll_seconds = time.monotonic() - started

        if new_run is None:
            results.record("new terminal run observed", False,
                           f"no terminal run within {config.run_timeout_seconds:.0f}s")
            return results, context

        context.new_run = new_run
        results.record("new terminal run observed", True,
                       f"status={new_run.get('status')} after {context.poll_seconds:.0f}s")

        counter_problems = checks.check_run_log_counters(new_run)
        results.record("run counter identity balances", not counter_problems,
                       "; ".join(counter_problems))

        new_items = new_run.get("items_new")
        if isinstance(new_items, int) and max_new_raw_items is not None:
            results.record(
                "new RawItems within supplied maximum", new_items <= max_new_raw_items,
                f"{new_items} new RawItems (not published alerts), maximum "
                f"{max_new_raw_items}",
            )

        context.after_health = await fetch_source_health(client, header, source_id)
        results.record("source health readable after run", True,
                       f"state={(context.after_health.get('health') or {}).get('state')}")

        context.summary_after = await fetch_system_summary(client, header)
        deltas, stop = reconcile_counts(
            context.summary_before, context.summary_after,
            new_run.get("items_new"), ai_disabled=ai_ok,
        )
        context.count_deltas = deltas
        context.stop_condition = stop
        results.record(
            "instance counts reconcile", not stop,
            stop or (
                f"raw_items +{deltas.get('raw_items_total', 0)} (RawItems, not "
                f"alerts) · processed +{deltas.get('processed_alerts_total', 0)} "
                f"· published +{deltas.get('published_alerts_total', 0)}"
            ),
        )
    except (SafetyRefusal, AuthError, AssertionFailure) as exc:
        results.record("stage aborted", False, redact(str(exc)))
        raise
    finally:
        await client.aclose()

    return results, context


def stage_markdown(results: ResultSet, context: StageContext) -> str:
    run = context.new_run
    notes = [
        "> **RawItems are not published alerts.** `items_new` counts articles "
        "stored by the collector. Whether any becomes a published alert is "
        "decided later by AI processing and the publishing policy, neither of "
        "which this script runs or enables.",
    ]
    body = results_markdown(
        results, heading=f"Collector stage — {context.source_name}", notes=notes
    )
    if run:
        body += "\n".join([
            "## Resulting RunLog",
            "",
            "| Field | Value |",
            "|---|---:|",
            f"| status | {run.get('status')} |",
            f"| items_fetched | {run.get('items_fetched')} |",
            f"| items_new (RawItems) | {run.get('items_new')} |",
            f"| items_skipped_url | {run.get('items_skipped_url')} |",
            f"| items_skipped_content | {run.get('items_skipped_content')} |",
            f"| items_skipped_invalid | {run.get('items_skipped_invalid')} |",
            f"| items_skipped_external | {run.get('items_skipped_external')} |",
            f"| error_message | {redact(str(run.get('error_message') or '—'))} |",
            "",
        ])
    return body


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.e2e.collector_stage",
        description=(
            "Observe, and optionally trigger, exactly ONE collector source. "
            "Dry-run and read-only unless every safety gate is satisfied."
        ),
    )
    parser.add_argument("--source-id", type=int, required=True)
    parser.add_argument("--expected-source-name", required=True,
                        help="must match the source's real name; guards against stale ids")
    parser.add_argument("--env-file")
    parser.add_argument("--stage", choices=sorted(STAGE_PLANS),
                        help="named stage, for its extra confirmation requirements")
    parser.add_argument("--stage-confirmation",
                        help="extra acknowledgement required by stages D and E")
    parser.add_argument("--max-unseen", type=int,
                        help="refuse if the preview reports more unseen entries than this")
    parser.add_argument("--max-new-raw-items", type=int,
                        help="maximum acceptable new RawItems for this run")
    parser.add_argument("--preview-report",
                        help="path to a fresh source_recovery_preview JSON report; "
                             "required for --execute")
    parser.add_argument("--preview-unseen", type=int,
                        help="DRY-RUN DISPLAY ONLY; rejected with --execute")
    parser.add_argument("--ai-confirmation",
                        help=f"required when the API cannot prove AI is off: "
                             f"{AI_CONFIRMATION_PHRASE}")
    parser.add_argument("--check-409", action="store_true",
                        help="issue one immediate second trigger to prove claim protection")
    parser.add_argument("--execute", action="store_true",
                        help="actually trigger the source (otherwise dry-run)")
    parser.add_argument("--confirmation", default="",
                        help=f"must be exactly {CONFIRMATION_PHRASE} to execute")
    parser.add_argument("--no-report", action="store_true")
    return parser


async def _main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        # Collector staging is an Admin-only flow; it never sends a subscriber
        # token, so it must not demand Supabase credentials.
        config = load_config(args.env_file, require_admin=True, require_subscriber=False)
    except ConfigError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return int(Exit.CONFIG_ERROR)

    if args.execute and args.preview_unseen is not None:
        print(
            "refusing --preview-unseen with --execute: a hand-entered volume "
            "cannot authorize a trigger. Supply --preview-report instead.",
            file=sys.stderr,
        )
        return int(Exit.SAFETY_REFUSED)

    mode = "EXECUTE" if args.execute else "dry-run"
    print(f"Collector stage ({mode}) — source {args.source_id} on {config.api_base_url}\n")

    exit_code = Exit.OK
    try:
        results, context = await run_stage(
            config,
            source_id=args.source_id,
            expected_name=args.expected_source_name,
            execute=args.execute,
            confirmation=args.confirmation,
            max_unseen=args.max_unseen,
            max_new_raw_items=args.max_new_raw_items,
            stage=args.stage,
            stage_confirmation=args.stage_confirmation,
            preview_report=args.preview_report,
            ai_confirmation=args.ai_confirmation,
            check_409=args.check_409,
        )
    except SafetyRefusal as exc:
        print(f"\nREFUSED: {exc}", file=sys.stderr)
        return int(Exit.SAFETY_REFUSED)
    except AuthError as exc:
        print(f"\nauthentication FAILED: {redact(str(exc))}", file=sys.stderr)
        return int(Exit.AUTH_FAILED)
    except AssertionFailure as exc:
        print(f"\nFAILED: {redact(str(exc))}", file=sys.stderr)
        return int(Exit.ASSERTION_FAILED)

    if context.stop_condition:
        exit_code = Exit.STOP_CONDITION
    elif context.executed and not context.new_run:
        exit_code = Exit.COLLECTOR_TIMEOUT
    elif results.failed:
        exit_code = Exit.ASSERTION_FAILED

    if not args.no_report:
        stem = f"collector_stage_{context.source_id}_{timestamp_slug()}"
        payload = dict(results.summary())
        payload["stage"] = {
            "source_id": context.source_id,
            "source_name": context.source_name,
            "executed": context.executed,
            "trigger_status": context.trigger_status,
            "second_trigger_status": context.second_trigger_status,
            "preview": context.preview,
            "poll_seconds": round(context.poll_seconds, 1),
            "new_run": context.new_run,
            "count_deltas": context.count_deltas,
            "stop_condition": context.stop_condition,
            "note": "items_new counts RawItems, not published alerts",
            "generated_at": utc_now(),
        }
        try:
            json_path, md_path = write_reports(
                payload, stage_markdown(results, context),
                report_dir=config.report_dir, stem=stem,
            )
            print(f"\nreports: {json_path}  {md_path}")
        except AssertionFailure as exc:
            print(f"report not written: {exc}", file=sys.stderr)
            return int(Exit.ASSERTION_FAILED)

    print(f"\n{results.passed_count} passed · {len(results.failed)} failed")
    if context.stop_condition:
        print(f"STOP CONDITION: {context.stop_condition}", file=sys.stderr)
    if context.executed:
        print("This run triggered ONE source. It does not continue to the next.")
    return int(exit_code)


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_main(argv))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
