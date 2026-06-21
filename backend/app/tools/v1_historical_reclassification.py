"""V1 Historical Re-classification — DRY-RUN + guarded APPLY tool (OPEN-4).

Populates V1 publication state on the **pre-V1 backlog** — alerts that were
processed before V1 deployed and therefore have ``publish_decision IS NULL`` —
so they surface in the admin review queue. Unlike the candidate backfill (which
applies a human-reviewed decision FILE), this tool *computes* each decision from
the database by re-running the current V1 logic, then classifies the alert into
**review / exclude / hold**.

Hard guarantee — it **NEVER auto-publishes a historical alert.** A re-evaluated
``auto_publish`` is redirected to ``review`` (held for a human). The classify-only
writer here has no ``is_published = True`` path at all.

Per alert it re-uses the live decision path:
  1. ``evaluate_source_rule`` → effective credibility (Krebs floor / Bleeping
     conditional — OPEN-1), applied retroactively.
  2. Distinct-outlet **cross-source** recompute from the alert's current event
     membership (corrects pre-fix same-outlet inflation). Financial / victim /
     trend factors are kept from the stored score (trend can't be replayed).
  3. ``evaluate_v1_publish_decision`` on the re-scored total.
  4. OPEN-5 topic veto (``should_route_to_review_by_topic``) → forces review.
  5. ``auto_publish`` → **redirect to review**.

Selection is idempotent: once classified, ``publish_decision`` is non-NULL, so a
re-run skips the row. Default is a read-only dry-run; mutation needs the full
guard set (confirm token + a prior dry-run report + a fresh-dry-run drift check),
and runs in a single transaction that rolls back on any error.

    # dry-run (read-only) for the first in-scope High/Medium batch:
    python -m app.tools.v1_historical_reclassification \
      --in-scope-only --min-internal-score 15 \
      --output reports/v1_historical_dry_run.json

    # guarded apply of that exact batch:
    python -m app.tools.v1_historical_reclassification \
      --in-scope-only --min-internal-score 15 \
      --dry-run-report reports/v1_historical_dry_run.json \
      --batch-id v1-historical-2026-06-21 \
      --apply --confirm APPLY_V1_HISTORICAL_RECLASSIFICATION
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.event import EventSource
from app.models.processed_alert import ProcessedAlert
from app.models.raw_item import RawItem
from app.models.review import AlertReview
from app.pipeline.event_grouper import _distinct_outlet_count
from app.pipeline.publishing.constants import (
    DecisionSource,
    PendingReviewReason,
    PublishDecisionValue,
)
from app.pipeline.publishing.publishing_policy import DEFAULT_V1_POLICY
from app.pipeline.publishing.risk_bands import compute_risk_band
from app.pipeline.publishing.source_rules import (
    evaluate_source_rule,
    evaluate_v1_publish_decision,
)
from app.pipeline.publishing.topic_veto import should_route_to_review_by_topic
from app.pipeline.signal_scorer import compute_cross_source_score

CONFIRM_TOKEN = "APPLY_V1_HISTORICAL_RECLASSIFICATION"
_BUCKETS = ("review", "exclude", "hold")

# bucket -> AlertReview.review_status (clearly a migration marker; free-text col).
_REVIEW_STATUS = {
    "review": "historical_review",
    "exclude": "historical_exclude",
    "hold": "historical_hold",
}

# Reason strings used by THIS tool (distinct from the live-pipeline reasons so the
# audit trail shows a historical reclassification produced the state).
_REASON_REDIRECTED = "historical_reclassified_publishable"  # would auto-publish → review
_REASON_PREFIX = "historical_"


@dataclass
class Classification:
    """The V1 state this tool would write for one backlog alert. Pure data."""

    alert_id: int
    bucket: str  # review | exclude | hold
    risk_band: str
    publish_decision: str
    publish_decision_reason: str
    pending_review_reason: str | None
    is_excluded: bool
    excluded_reason: str | None
    is_manual_hold: bool
    # --- diagnostics (report-only; never written) ---
    source_name: str | None
    primary_category: str | None
    stored_score: int | None
    new_score: int | None
    stored_band: str | None
    new_band: str
    would_auto_publish: bool
    topic_vetoed: bool
    rescored: bool


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


def _select_backlog_stmt(
    *, in_scope_only: bool, min_internal_score: int | None, limit: int | None
):
    """The pre-V1 relevant-unclassified backlog, with optional batch filters."""
    stmt = (
        select(ProcessedAlert)
        .where(
            ProcessedAlert.is_relevant.is_(True),
            ProcessedAlert.publish_decision.is_(None),
            ProcessedAlert.is_published.is_(False),
        )
        .options(selectinload(ProcessedAlert.raw_item).selectinload(RawItem.source))
    )
    if in_scope_only:
        stmt = stmt.where(
            ProcessedAlert.primary_category.in_(sorted(DEFAULT_V1_POLICY.approved_categories))
        )
    if min_internal_score is not None:
        stmt = stmt.where(ProcessedAlert.signal_score_total >= min_internal_score)
    # Deterministic order so batches are stable (highest score first, then id).
    return stmt.order_by(
        ProcessedAlert.signal_score_total.desc(), ProcessedAlert.id
    )


# ---------------------------------------------------------------------------
# Re-score (effective credibility + distinct-outlet cross-source)
# ---------------------------------------------------------------------------


async def _distinct_outlets_for_alert(session: AsyncSession, alert_id: int) -> int:
    """Distinct independent outlets across the alert's current event(s); >=1."""
    rows = (
        await session.execute(select(EventSource).where(EventSource.alert_id == alert_id))
    ).scalars().all()
    event_ids = {r.event_id for r in rows if r.event_id is not None}
    if not event_ids:
        return 1
    all_rows = (
        await session.execute(select(EventSource).where(EventSource.event_id.in_(event_ids)))
    ).scalars().all()
    return max(1, _distinct_outlet_count(all_rows))


async def _recompute_total(
    session: AsyncSession, alert: ProcessedAlert, effective_credibility: int | None
) -> tuple[int | None, bool]:
    """Re-score by swapping ONLY the credibility + cross-source factors on top of
    the stored total (financial / victim / trend are preserved exactly). Returns
    (new_total, rescored). rescored is False when the stored factors are missing."""
    stored_total = alert.signal_score_total
    stored_cred = alert.score_source_credibility
    stored_cross = alert.score_cross_source
    if stored_total is None or stored_cred is None or stored_cross is None:
        return stored_total, False

    new_cred = max(1, min(5, effective_credibility if effective_credibility is not None else stored_cred))
    outlet_count = await _distinct_outlets_for_alert(session, alert.id)
    new_cross = compute_cross_source_score(outlet_count)

    new_total = stored_total - stored_cred - stored_cross + new_cred + new_cross
    return max(5, min(25, new_total)), True


# ---------------------------------------------------------------------------
# Classification (compute the decision; never mutates)
# ---------------------------------------------------------------------------


async def _classify(session: AsyncSession, alert: ProcessedAlert) -> Classification:
    source = alert.raw_item.source if alert.raw_item else None
    source_name = source.name if source else None
    stored_credibility = source.credibility_score if source else None
    title = alert.raw_item.title if alert.raw_item else None

    stored_band = (
        compute_risk_band(alert.signal_score_total).value
        if alert.signal_score_total is not None
        else None
    )

    rule = evaluate_source_rule(
        source_name=source_name,
        stored_credibility=stored_credibility,
        title=title,
        summary=alert.summary,
        matched_keywords=alert.matched_keywords,
        entities_json=alert.entities_json,
        primary_category=alert.primary_category,
    )
    new_total, rescored = await _recompute_total(session, alert, rule.effective_credibility)

    decision = evaluate_v1_publish_decision(
        signal_score_total=new_total,
        primary_category=alert.primary_category,
        source_name=source_name,
        source_credibility=stored_credibility,
        title=title,
        summary=alert.summary,
        matched_keywords=alert.matched_keywords,
        entities_json=alert.entities_json,
    )
    new_band = decision.risk_band.value

    topic_vetoed = should_route_to_review_by_topic(
        title=title,
        summary=alert.summary,
        primary_category=alert.primary_category,
        matched_keywords=alert.matched_keywords,
    )
    would_auto_publish = decision.action is PublishDecisionValue.AUTO_PUBLISH

    # --- Resolve the final classify-only state (never publishes) ---
    # Precedence (historical re-classification policy):
    #   1. would-auto-publish  -> NEVER publish history; hold for review (flag the
    #      topic reason if it is also out-of-scope).
    #   2. below-60 (EXCLUDE)  -> exclude wins over the topic veto: an out-of-scope
    #      item that would not be published anyway is just queue noise in review.
    #   3. out-of-scope (medium/high that didn't auto-publish) -> review.
    # This differs from the live OPEN-5 veto (which routes ALL out-of-scope to
    # review) on purpose, to keep the one-time historical review queue clean.
    if would_auto_publish:
        # Never auto-publish history. Surface the topic reason when out-of-scope.
        bucket, pd = "review", PublishDecisionValue.REVIEW.value
        if topic_vetoed:
            reason = "blocked_by_topic_scope"
            pending = PendingReviewReason.BLOCKED_BY_TOPIC_SCOPE.value
        else:
            reason = _REASON_REDIRECTED
            pending = PendingReviewReason.MANUAL_REVIEW_ONLY.value
    elif decision.action is PublishDecisionValue.EXCLUDE:
        bucket, pd, reason, pending = (
            "exclude", PublishDecisionValue.EXCLUDE.value,
            _REASON_PREFIX + decision.reason,
            decision.pending_review_reason.value if decision.pending_review_reason else None,
        )
    elif topic_vetoed:
        bucket, pd, reason, pending = (
            "review", PublishDecisionValue.REVIEW.value,
            "blocked_by_topic_scope", PendingReviewReason.BLOCKED_BY_TOPIC_SCOPE.value,
        )
    elif decision.action is PublishDecisionValue.HOLD:
        bucket, pd, reason, pending = (
            "hold", PublishDecisionValue.HOLD.value,
            _REASON_PREFIX + decision.reason,
            decision.pending_review_reason.value if decision.pending_review_reason else None,
        )
    else:  # REVIEW
        bucket, pd, reason, pending = (
            "review", PublishDecisionValue.REVIEW.value,
            _REASON_PREFIX + decision.reason,
            decision.pending_review_reason.value if decision.pending_review_reason else None,
        )

    return Classification(
        alert_id=alert.id,
        bucket=bucket,
        risk_band=new_band,
        publish_decision=pd,
        publish_decision_reason=reason,
        pending_review_reason=pending,
        is_excluded=(bucket == "exclude"),
        excluded_reason=(reason if bucket == "exclude" else None),
        is_manual_hold=(bucket == "hold"),
        source_name=source_name,
        primary_category=alert.primary_category,
        stored_score=alert.signal_score_total,
        new_score=new_total,
        stored_band=stored_band,
        new_band=new_band,
        would_auto_publish=would_auto_publish,
        topic_vetoed=topic_vetoed,
        rescored=rescored,
    )


# ---------------------------------------------------------------------------
# Classify-only writer (THE guard: no is_published=True path)
# ---------------------------------------------------------------------------


def _apply_classification(
    alert: ProcessedAlert, cls: Classification, *, now: datetime, user_id: int | None
) -> None:
    """Write the computed V1 state for one backlog alert. Never publishes."""
    # Hard invariant — historical rows are never published by this tool.
    alert.is_published = False
    alert.published_at = None
    alert.published_by_rule = False
    alert.published_by_user_id = None

    alert.risk_band = cls.risk_band
    alert.publish_decision = cls.publish_decision
    alert.publish_decision_reason = cls.publish_decision_reason
    alert.pending_review_reason = cls.pending_review_reason
    alert.is_excluded = cls.is_excluded
    alert.excluded_reason = cls.excluded_reason
    alert.is_manual_hold = cls.is_manual_hold

    alert.publishing_policy_version = DEFAULT_V1_POLICY.version
    alert.publication_state_source = DecisionSource.SYSTEM_MIGRATION.value
    alert.publication_state_updated_at = now


def _make_review_row(
    alert_id: int, bucket: str, *, user_id: int | None, batch_id: str
) -> AlertReview:
    # reviewed_at intentionally NOT set (naive column; rely on server func.now()).
    return AlertReview(
        alert_id=alert_id,
        user_id=user_id,
        review_status=_REVIEW_STATUS[bucket],
        decision_source=DecisionSource.SYSTEM_MIGRATION.value,
        review_batch_id=batch_id,
    )


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------


async def _classify_backlog(
    session: AsyncSession, *, in_scope_only: bool, min_internal_score: int | None, limit: int | None
) -> list[Classification]:
    stmt = _select_backlog_stmt(
        in_scope_only=in_scope_only, min_internal_score=min_internal_score, limit=limit
    )
    alerts = (await session.execute(stmt)).scalars().all()
    if limit is not None:
        alerts = alerts[:limit]
    return [await _classify(session, a) for a in alerts]


async def run_dry_run(
    session: AsyncSession,
    *,
    in_scope_only: bool = False,
    min_internal_score: int | None = None,
    limit: int | None = None,
) -> dict:
    """Read-only: compute the planned classification for the selected backlog."""
    classifications = await _classify_backlog(
        session,
        in_scope_only=in_scope_only,
        min_internal_score=min_internal_score,
        limit=limit,
    )
    counts = {b: sum(1 for c in classifications if c.bucket == b) for b in _BUCKETS}
    errors: list[str] = []
    # Invariant the apply also enforces: nothing in the plan ever publishes.
    if any(c.publish_decision == PublishDecisionValue.AUTO_PUBLISH.value for c in classifications):
        errors.append("plan_contains_auto_publish")  # must never happen

    return {
        "mode": "dry_run",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "filters": {
            "in_scope_only": in_scope_only,
            "min_internal_score": min_internal_score,
            "limit": limit,
        },
        "selected": len(classifications),
        "counts": {**counts, "total": len(classifications)},
        "redirected_auto_publish": sum(1 for c in classifications if c.would_auto_publish),
        "topic_vetoed": sum(1 for c in classifications if c.topic_vetoed),
        "rescored": sum(1 for c in classifications if c.rescored),
        "planned": [asdict(c) for c in classifications],
        "errors": errors,
        "passed": not errors,
    }


# ---------------------------------------------------------------------------
# Apply guard + transaction
# ---------------------------------------------------------------------------


def _planned_map(report: dict) -> dict[int, str]:
    """alert_id -> publish_decision for drift comparison."""
    return {int(p["alert_id"]): p["publish_decision"] for p in report.get("planned", [])}


def validate_for_apply(prior: dict, fresh: dict) -> list[str]:
    """Refusal reasons; empty means safe to apply. Requires the supplied report to
    be a passing dry-run that still agrees with a fresh dry-run of the same batch."""
    errors: list[str] = []
    if prior.get("mode") != "dry_run":
        errors.append(f"prior_report_mode_invalid: {prior.get('mode')!r}")
    if prior.get("passed") is not True:
        errors.append("prior_report_not_passed")
    if prior.get("errors"):
        errors.append(f"prior_report_has_errors: {prior.get('errors')}")
    if fresh.get("passed") is not True:
        errors.append("fresh_report_not_passed")
    if fresh.get("errors"):
        errors.append(f"fresh_report_has_errors: {fresh.get('errors')}")
    if prior.get("filters") != fresh.get("filters"):
        errors.append(
            f"filter_drift: prior={prior.get('filters')} fresh={fresh.get('filters')}"
        )
    prior_map, fresh_map = _planned_map(prior), _planned_map(fresh)
    if set(prior_map) != set(fresh_map):
        errors.append(
            f"id_drift: only_prior={sorted(set(prior_map) - set(fresh_map))} "
            f"only_fresh={sorted(set(fresh_map) - set(prior_map))}"
        )
    drifted = {i: (prior_map[i], fresh_map[i]) for i in set(prior_map) & set(fresh_map)
               if prior_map[i] != fresh_map[i]}
    if drifted:
        errors.append(f"decision_drift: {drifted}")
    return errors


def _maybe_lock(stmt, session: AsyncSession):
    try:
        name = session.get_bind().dialect.name
    except Exception:
        name = ""
    return stmt.with_for_update() if name and name != "sqlite" else stmt


def _refused(errors: list[str], **extra) -> dict:
    return {"mode": "apply_refused", "applied": False, "errors": errors, **extra}


async def run_apply(
    session: AsyncSession,
    *,
    apply: bool = False,
    dry_run_report_path: str | Path | None = None,
    batch_id: str | None = None,
    confirm: str | None = None,
    user_id: int | None = None,
    in_scope_only: bool = False,
    min_internal_score: int | None = None,
    limit: int | None = None,
) -> dict:
    """Dry-run (default) or guarded transactional apply. Returns a report dict."""
    if not apply:
        report = await run_dry_run(
            session, in_scope_only=in_scope_only,
            min_internal_score=min_internal_score, limit=limit,
        )
        report["applied"] = False
        return report

    if confirm != CONFIRM_TOKEN:
        return _refused([f"confirm_required: pass --confirm {CONFIRM_TOKEN}"])
    if not dry_run_report_path:
        return _refused(["dry_run_report_required_for_apply"])
    if not batch_id:
        return _refused(["batch_id_required_for_apply"])

    try:
        prior = json.loads(Path(dry_run_report_path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _refused([f"dry_run_report_not_found: {dry_run_report_path}"])
    except json.JSONDecodeError as exc:
        return _refused([f"dry_run_report_not_json: {exc}"])

    # Re-classify against the CURRENT DB and refuse on any drift vs the prior report.
    classifications = await _classify_backlog(
        session, in_scope_only=in_scope_only,
        min_internal_score=min_internal_score, limit=limit,
    )
    fresh = await run_dry_run(
        session, in_scope_only=in_scope_only,
        min_internal_score=min_internal_score, limit=limit,
    )
    errors = validate_for_apply(prior, fresh)
    if errors:
        return _refused(errors, batch_id=batch_id, dry_run_report=str(dry_run_report_path))

    now = datetime.now(timezone.utc)
    cls_by_id = {c.alert_id: c for c in classifications}
    ids = sorted(cls_by_id)
    updated = {b: [] for b in _BUCKETS}
    reviews_created = 0
    try:
        stmt = (
            select(ProcessedAlert)
            .where(ProcessedAlert.id.in_(ids))
            .options(selectinload(ProcessedAlert.raw_item).selectinload(RawItem.source))
        )
        by_id = {a.id: a for a in (await session.execute(_maybe_lock(stmt, session))).scalars().all()}
        missing = [i for i in ids if i not in by_id]
        if missing:
            raise RuntimeError(f"alerts vanished between dry-run and apply: {missing}")

        for alert_id in ids:
            cls = cls_by_id[alert_id]
            _apply_classification(by_id[alert_id], cls, now=now, user_id=user_id)
            session.add(_make_review_row(alert_id, cls.bucket, user_id=user_id, batch_id=batch_id))
            updated[cls.bucket].append(alert_id)
            reviews_created += 1

        await session.commit()
    except Exception as exc:
        await session.rollback()
        return _refused(
            [f"apply_failed_rolled_back: {exc}"], batch_id=batch_id,
            dry_run_report=str(dry_run_report_path),
        )

    return {
        "mode": "apply",
        "applied": True,
        "batch_id": batch_id,
        "dry_run_report": str(dry_run_report_path),
        "generated_at": now.isoformat(),
        "counts": {**{b: len(updated[b]) for b in _BUCKETS}, "total": reviews_created},
        "updated_alert_ids": {b: sorted(updated[b]) for b in _BUCKETS},
        "review_records_created": reviews_created,
        "publication_state_source": DecisionSource.SYSTEM_MIGRATION.value,
        "publishing_policy_version": DEFAULT_V1_POLICY.version,
        "passed": True,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def console_summary(report: dict) -> str:
    mode = report.get("mode")
    if mode == "apply":
        c = report["counts"]
        return "\n".join([
            "V1 Historical Re-classification APPLY",
            f"Batch: {report['batch_id']}",
            f"Applied: review={c['review']} exclude={c['exclude']} hold={c['hold']} total={c['total']}",
            f"Audit rows created: {report['review_records_created']}",
            f"Passed: {report['passed']}",
        ])
    if mode == "apply_refused":
        return "V1 Historical Re-classification APPLY REFUSED\n" + "\n".join(
            f"  - {e}" for e in report["errors"]
        ) + "\nNo database changes were applied."
    c = report["counts"]
    return "\n".join([
        "V1 Historical Re-classification Dry Run",
        f"Filters: {report['filters']}",
        f"Selected: {report['selected']}",
        f"Review: {c['review']}  Exclude: {c['exclude']}  Hold: {c['hold']}  Total: {c['total']}",
        f"Would-auto-publish (redirected to review): {report['redirected_auto_publish']}",
        f"Topic-vetoed: {report['topic_vetoed']}",
        f"Re-scored (effective cred + distinct cross-source): {report['rescored']}",
        f"Errors: {report['errors']}",
        f"Passed: {report['passed']}",
        "No database changes were applied.",
    ])


async def _main_async(args: argparse.Namespace) -> int:
    from app.database import AsyncSessionLocal  # local import: keep module test-friendly

    async with AsyncSessionLocal() as session:
        report = await run_apply(
            session,
            apply=args.apply,
            dry_run_report_path=args.dry_run_report,
            batch_id=args.batch_id,
            confirm=args.confirm,
            user_id=args.user_id,
            in_scope_only=args.in_scope_only,
            min_internal_score=args.min_internal_score,
            limit=args.limit,
        )

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(console_summary(report))
    if args.output:
        print(f"\nJSON report written to: {args.output}")
    return 0 if report.get("passed") else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="V1 historical re-classification of the pre-V1 backlog. "
        "Default is a read-only dry-run; --apply requires the full guard set. "
        "Never auto-publishes a historical alert."
    )
    parser.add_argument("--in-scope-only", action="store_true",
                        help="Only the 5 approved fraud categories.")
    parser.add_argument("--min-internal-score", type=int, default=None,
                        help="Only alerts with stored signal_score_total >= N (5-25 scale; 15=medium).")
    parser.add_argument("--limit", type=int, default=None, help="Cap the batch size.")
    parser.add_argument("--output", help="Path to write the JSON report.")
    parser.add_argument("--apply", action="store_true", help="Apply (default: dry-run).")
    parser.add_argument("--dry-run-report", help="Prior dry-run JSON report (required for --apply).")
    parser.add_argument("--batch-id", help="Audit batch id (required for --apply).")
    parser.add_argument("--confirm", help=f"Must equal {CONFIRM_TOKEN} for --apply.")
    parser.add_argument("--user-id", type=int, default=None, help="Optional reviewer user id for audit rows.")
    args = parser.parse_args(argv)
    return asyncio.run(_main_async(args))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
