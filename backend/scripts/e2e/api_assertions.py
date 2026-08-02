"""Reusable response assertions.

Pure functions over already-parsed payloads: no HTTP, no config, no I/O. That
keeps them testable without a network and lets the smoke runner and the collector
stage runner share exactly the same notion of "correct".

Category values are **imported** from `app.domain.alert_categories`, never
retyped. A copy here could drift from the API and the test would keep passing.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from app.domain.alert_categories import ALERT_CATEGORIES

#: Health states the Source Health API may report.
VALID_HEALTH_STATES = frozenset({"healthy", "warning", "error", "disabled"})

#: External-exclusion telemetry on a `SourceHealthRead`. These are windowed and
#: named differently from the raw per-run `items_skipped_external` on a RunLog —
#: asserting the RunLog name against a health record silently passes nothing.
HEALTH_EXTERNAL_COUNTERS = (
    "latest_run_items_skipped_external",
    "items_skipped_external_24h",
    "items_skipped_external_7d",
)

#: Invalid-content telemetry on a `SourceHealthRead`, kept deliberately separate.
HEALTH_INVALID_COUNTER = "items_skipped_invalid_24h"

#: Subscriber Top Alerts shows at most three, Critical and High only.
TOP_ALERTS_MAX = 3
HIGH_MIN_SCORE_100 = 72  # public payloads expose the 0–100 scale


class Problem(str):
    """A human-readable assertion failure. Empty string means 'no problem'."""


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _parse_iso(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# Source Health
# ---------------------------------------------------------------------------


def check_source_health_list(
    payload: Any, *, expected_source_ids: Iterable[int] | None = None
) -> list[str]:
    """Validate `GET /api/v1/admin/sources/health`. Returns a list of problems."""
    problems: list[str] = []
    if not isinstance(payload, list):
        return [f"expected a list, got {type(payload).__name__}"]
    if not payload:
        return ["source health list is empty"]

    seen_ids: set[int] = set()
    for index, record in enumerate(payload):
        where = f"record[{index}]"
        if not isinstance(record, dict):
            problems.append(f"{where}: not an object")
            continue

        source_id = record.get("source_id")
        if not _is_int(source_id):
            problems.append(f"{where}: source_id is not an integer")
        else:
            seen_ids.add(source_id)

        state = record.get("state")
        if state not in VALID_HEALTH_STATES:
            problems.append(f"{where}: state {state!r} not in {sorted(VALID_HEALTH_STATES)}")

        if not str(record.get("reason_code") or "").strip():
            problems.append(f"{where}: reason_code is empty")

        # Invalid content and deliberate external exclusion must stay separate
        # fields — conflating them is exactly the confusion the telemetry work
        # existed to remove. On a health record they are windowed and named
        # accordingly (`SourceHealthRead`); the raw per-run counters live on
        # `recent_runs` and are checked in check_source_health_detail.
        for counter in HEALTH_EXTERNAL_COUNTERS:
            if counter not in record:
                problems.append(f"{where}: {counter} is missing")
            elif not _is_int(record[counter]):
                problems.append(f"{where}: {counter} is not an integer")

        if HEALTH_INVALID_COUNTER not in record:
            problems.append(f"{where}: {HEALTH_INVALID_COUNTER} is missing")
        elif not _is_int(record[HEALTH_INVALID_COUNTER]):
            problems.append(f"{where}: {HEALTH_INVALID_COUNTER} is not an integer")

        # The distinction is structural, not incidental: no single field may
        # stand in for both.
        if HEALTH_INVALID_COUNTER in record and "items_skipped_external_24h" in record:
            if HEALTH_INVALID_COUNTER == "items_skipped_external_24h":  # pragma: no cover
                problems.append(f"{where}: invalid and external counters collapsed")

        for field in ("last_run_at", "last_success_at", "last_new_item_at"):
            value = record.get(field)
            if value is not None and _parse_iso(str(value)) is None:
                problems.append(f"{where}: {field}={value!r} is not an ISO timestamp")

    if expected_source_ids is not None:
        missing = sorted(set(expected_source_ids) - seen_ids)
        if missing:
            problems.append(f"source health list is missing source ids {missing}")

    return problems


def check_source_health_detail(payload: Any) -> list[str]:
    """Validate `GET /api/v1/admin/sources/{id}/health`, including run ordering."""
    problems: list[str] = []
    if not isinstance(payload, dict):
        return [f"expected an object, got {type(payload).__name__}"]

    health = payload.get("health")
    if not isinstance(health, dict):
        problems.append("health object missing")
    else:
        problems.extend(f"health.{p}" for p in check_source_health_list([health]))

    runs = payload.get("recent_runs")
    if not isinstance(runs, list):
        problems.append("recent_runs is not a list")
        return problems

    timestamps: list[datetime] = []
    for index, run in enumerate(runs):
        if not isinstance(run, dict):
            problems.append(f"recent_runs[{index}]: not an object")
            continue
        if "items_skipped_external" not in run:
            problems.append(f"recent_runs[{index}]: items_skipped_external missing")
        started = _parse_iso(str(run.get("run_started_at", "")))
        if started is None:
            problems.append(f"recent_runs[{index}]: run_started_at unparseable")
        else:
            timestamps.append(started)

    if timestamps != sorted(timestamps, reverse=True):
        problems.append("recent_runs are not newest-first")

    return problems


def check_system_health_summary(payload: Any) -> list[str]:
    """Validate the summary, including that by_state totals reconcile."""
    problems: list[str] = []
    if not isinstance(payload, dict):
        return [f"expected an object, got {type(payload).__name__}"]

    total = payload.get("sources_total")
    if not _is_int(total):
        problems.append("sources_total is not an integer")

    by_state = payload.get("by_state")
    if not isinstance(by_state, dict):
        problems.append("by_state is not an object")
    else:
        unknown = sorted(set(by_state) - VALID_HEALTH_STATES)
        if unknown:
            problems.append(f"by_state has unknown states {unknown}")
        counts = [v for v in by_state.values() if _is_int(v)]
        if len(counts) != len(by_state):
            problems.append("by_state has non-integer counts")
        elif _is_int(total) and sum(counts) != total:
            problems.append(f"by_state totals {sum(counts)} != sources_total {total}")

    if "scheduler_running" not in payload:
        problems.append("scheduler_running is not reported")
    elif not isinstance(payload["scheduler_running"], bool):
        problems.append("scheduler_running is not a boolean")

    for counter in ("items_skipped_external_24h", "items_skipped_external_7d"):
        if counter in payload and not _is_int(payload[counter]):
            problems.append(f"{counter} is not an integer")

    return problems


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


def check_categories(payload: Any, *, scope: str) -> list[str]:
    """Validate a category metadata response against the canonical vocabulary.

    Admin and subscriber counts are scoped differently by design, so this never
    compares the two responses' counts — only their shape and vocabulary.
    """
    problems: list[str] = []
    if not isinstance(payload, dict):
        return [f"{scope}: expected an object, got {type(payload).__name__}"]

    categories = payload.get("categories")
    if not isinstance(categories, list):
        return [f"{scope}: categories is not a list"]

    values = [c.get("value") for c in categories if isinstance(c, dict)]

    if len(values) != len(set(values)):
        problems.append(f"{scope}: duplicate category values")

    if tuple(values) != tuple(ALERT_CATEGORIES):
        problems.append(
            f"{scope}: categories are not the canonical list in canonical order; "
            f"got {values}, expected {list(ALERT_CATEGORIES)}"
        )

    for index, entry in enumerate(categories):
        where = f"{scope}: categories[{index}]"
        if not isinstance(entry, dict):
            problems.append(f"{where}: not an object")
            continue
        if not str(entry.get("label") or "").strip():
            problems.append(f"{where}: label is empty")
        count = entry.get("count")
        if not _is_int(count):
            problems.append(f"{where}: count is not an integer")
        elif count < 0:
            problems.append(f"{where}: count is negative")

    total = payload.get("total")
    if not _is_int(total):
        problems.append(f"{scope}: total is not an integer")
    elif total < 0:
        problems.append(f"{scope}: total is negative")

    return problems


def missing_zero_count_categories(payload: Any) -> list[str]:
    """Canonical categories absent from the response — zero-count ones must stay."""
    if not isinstance(payload, dict) or not isinstance(payload.get("categories"), list):
        return list(ALERT_CATEGORIES)
    present = {c.get("value") for c in payload["categories"] if isinstance(c, dict)}
    return [value for value in ALERT_CATEGORIES if value not in present]


# ---------------------------------------------------------------------------
# Top Alerts
# ---------------------------------------------------------------------------


def check_top_alerts(payload: Any, *, weekly_contract: bool = True) -> list[str]:
    """Validate Subscriber Top Alerts.

    An **empty list is a valid result**, not a failure: the window is the last
    seven days and a genuinely quiet week qualifies nothing. The contract
    deliberately has no fallback to older alerts.

    ``weekly_contract`` selects which release's semantics apply. The endpoint
    path exists in both, so presence alone cannot tell them apart:

    * **True** (post-deploy) — the Slice 3B.2J contract: Critical/High only, and
      ``published_at`` mirrors ``source_published_at`` when the source date is
      known.
    * **False** (pre-deploy) — the legacy all-time implementation, which admits
      Medium and reports the platform publication date. Only the shape-level
      rules are asserted, so a correct pre-deployment API does not read as broken.
    """
    problems: list[str] = []
    if isinstance(payload, dict):
        alerts = payload.get("alerts")
    else:
        alerts = payload
    if not isinstance(alerts, list):
        return [f"expected an alerts list, got {type(payload).__name__}"]

    # Both implementations cap at three.
    if len(alerts) > TOP_ALERTS_MAX:
        problems.append(f"returned {len(alerts)} alerts, maximum is {TOP_ALERTS_MAX}")

    for index, alert in enumerate(alerts):
        where = f"alerts[{index}]"
        if not isinstance(alert, dict):
            problems.append(f"{where}: not an object")
            continue

        # The field must be exposed in both releases.
        if "source_published_at" not in alert:
            problems.append(f"{where}: source_published_at is not separately present")

        published_at = alert.get("published_at")
        if published_at is None:
            problems.append(f"{where}: published_at is missing")

        if not weekly_contract:
            continue

        # Critical and High only. Public payloads carry the 0–100 scale.
        risk = str(alert.get("risk_level") or "").lower()
        score = alert.get("signal_score")
        if risk and risk not in ("critical", "high"):
            problems.append(f"{where}: risk_level {risk!r} is neither critical nor high")
        elif not risk and _is_int(score) and score < HIGH_MIN_SCORE_100:
            problems.append(f"{where}: signal_score {score} is below the High floor")

        source_published_at = alert.get("source_published_at")
        if (
            published_at is not None
            and source_published_at is not None
            and published_at != source_published_at
        ):
            problems.append(
                f"{where}: published_at should equal source_published_at when "
                f"available ({published_at!r} != {source_published_at!r})"
            )

    return problems


# ---------------------------------------------------------------------------
# Generic shapes
# ---------------------------------------------------------------------------

#: The skip counters introduced by migrations 0012 and 0013. Absent in earlier
#: releases, so their presence is what distinguishes the two RunLog shapes.
SPLIT_SKIP_COUNTERS = (
    "items_skipped_url", "items_skipped_content",
    "items_skipped_invalid", "items_skipped_external",
)

#: Fields that must never appear in an unauthenticated public payload.
PRIVATE_FIELDS = frozenset(
    {
        "published_by_user_id", "publication_state_source", "pending_review_reason",
        "internal_notes", "raw_html", "reviewed_by", "admin_notes",
    }
)


def check_public_alerts(payload: Any) -> list[str]:
    """Validate the unauthenticated public feed: shape, and no private leakage."""
    problems: list[str] = []
    alerts = payload.get("alerts") if isinstance(payload, dict) else payload
    if not isinstance(alerts, list):
        return [f"expected an alerts list, got {type(payload).__name__}"]

    for index, alert in enumerate(alerts[:25]):
        if not isinstance(alert, dict):
            problems.append(f"alerts[{index}]: not an object")
            continue
        leaked = sorted(PRIVATE_FIELDS & set(alert))
        if leaked:
            problems.append(f"alerts[{index}]: exposes private fields {leaked}")
    return problems


def check_run_log_counters(run: dict[str, Any], *, require_split: bool = True) -> list[str]:
    """Validate a RunLog's item counters.

    The five-way split is **not** present in every release: migration 0012 splits
    the skip telemetry into url/content/invalid and 0013 adds
    ``items_skipped_external``. Before those land, `run_logs` carries only
    ``items_fetched``/``items_new``/``items_duplicate``, and demanding the full
    identity would fail a perfectly healthy pre-deployment API.

    So the identity is checked when the split counters are present, and required
    outright only when ``require_split`` says this release should have them.
    """
    problems: list[str] = []

    if not _is_int(run.get("items_fetched")):
        return ["items_fetched is not an integer"]
    if not _is_int(run.get("items_new")):
        problems.append("items_new is not an integer")
    elif run["items_new"] > run["items_fetched"]:
        problems.append(
            f"items_new={run['items_new']} exceeds items_fetched={run['items_fetched']}"
        )

    present = [name for name in SPLIT_SKIP_COUNTERS if name in run]
    if not present:
        if require_split:
            problems.append(
                "split skip counters are missing: this release should expose "
                f"{list(SPLIT_SKIP_COUNTERS)} (migrations 0012 and 0013)"
            )
        return problems

    missing = [name for name in SPLIT_SKIP_COUNTERS if name not in run]
    if missing:
        problems.append(f"partial split counters — missing {missing}")
        return problems

    non_integer = [name for name in SPLIT_SKIP_COUNTERS if not _is_int(run[name])]
    if non_integer:
        problems.append(f"non-integer counters: {non_integer}")
        return problems

    total = int(run["items_new"]) + sum(int(run[name]) for name in SPLIT_SKIP_COUNTERS)
    if total != int(run["items_fetched"]):
        problems.append(
            f"counter identity does not balance: items_fetched="
            f"{run['items_fetched']} but parts sum to {total}"
        )
    return problems
