"""V1 Candidate Backfill — APPLY tool (Slice 7C).

Guarded, transactional application of Ken's reviewed Candidate decisions. It
reuses the Slice 7B read-only dry-run (``app.tools.v1_candidate_backfill_dry_run``)
and refuses to mutate anything unless a *successful full-DB* dry-run report proves
the input is safe AND a fresh dry-run against the current DB still agrees.

Run as a module from the backend directory. Default (no ``--apply``) is a
read-only dry-run; mutation requires the full guard set:

    python -m app.tools.v1_candidate_backfill_apply \
      --input "data/review_inputs/HiddenAlerts_V1_Candidate_Alerts_Review - Reviewed by Ken on 6-11-26.xlsx" \
      --dry-run-report "reports/v1_candidate_backfill_dry_run.json" \
      --batch-id "v1-candidate-2026-06-11" \
      --apply \
      --confirm "APPLY_V1_CANDIDATE_BACKFILL"

Safety: refuses parse-only dry-run reports, count mismatches, failed/blocked
reports, and any drift between the supplied report and a fresh dry-run. Applies
in a single transaction (rolls back on any error). Never calls the live pipeline
or public API; never deletes rows; only touches ``processed_alerts`` publication
state and writes ``alert_reviews`` audit rows.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.processed_alert import ProcessedAlert
from app.models.raw_item import RawItem
from app.models.review import AlertReview
from app.pipeline.publishing.constants import (
    DecisionSource,
    PendingReviewReason,
    PublishDecisionValue,
)
from app.pipeline.publishing.publishing_policy import DEFAULT_V1_POLICY
from app.pipeline.publishing.risk_bands import compute_risk_band
from app.tools.v1_candidate_backfill_dry_run import (
    EXPECTED_COUNTS,
    console_summary,
    run_dry_run,
)

CONFIRM_TOKEN = "APPLY_V1_CANDIDATE_BACKFILL"
_DECISION_GROUPS = ("approved", "rejected", "keep_later")

# Decision group -> AlertReview.review_status used for the audit row.
_REVIEW_STATUS = {
    "approved": "approved",
    "rejected": "false_positive",
    "keep_later": "manual_hold",
}


# ---------------------------------------------------------------------------
# Dry-run-report validation (the apply guard)
# ---------------------------------------------------------------------------


def validate_dry_run_report_for_apply(
    report: dict,
    fresh_report: dict,
    *,
    expected_counts: dict[str, int] | None = None,
) -> list[str]:
    """Return a list of refusal reasons; empty means safe to apply.

    Verifies the supplied (prior) report is a *full-DB* dry-run that passed with
    no blockers, that its counts match the expected set, and that a freshly-run
    dry-run against the current DB still agrees (same counts + same alert ids per
    decision group, no new blockers / missing / already-published / irrelevant).
    """
    expected = expected_counts or EXPECTED_COUNTS
    errors: list[str] = []

    # --- Prior report shape / pass state ---
    mode = report.get("mode")
    if mode == "dry_run_file_parse_only":
        errors.append("prior_report_is_parse_only (DB validation was not run)")
    elif mode != "dry_run":
        errors.append(f"prior_report_mode_invalid: {mode!r}")
    if report.get("passed") is not True:
        errors.append("prior_report_not_passed")
    if report.get("blockers"):
        errors.append(f"prior_report_has_blockers: {report.get('blockers')}")
    prior_db = report.get("db_validation") or {}
    if prior_db.get("passed") is not True:
        errors.append("prior_report_db_validation_not_passed")

    prior_counts = report.get("actual_counts") or {}
    for g in _DECISION_GROUPS:
        if prior_counts.get(g) != expected.get(g):
            errors.append(
                f"prior_count_{g}={prior_counts.get(g)} != expected {expected.get(g)}"
            )

    # --- Fresh report pass state ---
    if fresh_report.get("passed") is not True:
        errors.append("fresh_report_not_passed")
    if fresh_report.get("blockers"):
        errors.append(f"fresh_report_has_blockers: {fresh_report.get('blockers')}")
    fresh_db = fresh_report.get("db_validation") or {}
    for key in (
        "missing_ids",
        "approved_already_published_ids",
        "approved_irrelevant_ids",
        "conflicting_duplicate_ids",
    ):
        if fresh_db.get(key):
            errors.append(f"fresh_{key}: {fresh_db.get(key)}")
    if prior_db.get("conflicting_duplicate_ids"):
        errors.append(f"prior_conflicting_duplicate_ids: {prior_db.get('conflicting_duplicate_ids')}")

    fresh_counts = fresh_report.get("actual_counts") or {}
    for g in _DECISION_GROUPS:
        if fresh_counts.get(g) != expected.get(g):
            errors.append(f"fresh_count_{g}={fresh_counts.get(g)} != expected {expected.get(g)}")
        if fresh_counts.get(g) != prior_counts.get(g):
            errors.append(f"count_drift_{g}: prior={prior_counts.get(g)} fresh={fresh_counts.get(g)}")

    # --- Per-group alert-id agreement between prior and fresh ---
    for g in _DECISION_GROUPS:
        prior_ids = _planned_ids(report, g)
        fresh_ids = _planned_ids(fresh_report, g)
        if prior_ids != fresh_ids:
            errors.append(
                f"id_drift_{g}: only_in_prior={sorted(prior_ids - fresh_ids)} "
                f"only_in_fresh={sorted(fresh_ids - prior_ids)}"
            )

    return errors


def _planned_ids(report: dict, group: str) -> set[int]:
    actions = (report.get("planned_actions") or {}).get(group) or []
    return {a["alert_id"] for a in actions}


# ---------------------------------------------------------------------------
# Per-alert mutation (pure ORM writes; caller owns the transaction)
# ---------------------------------------------------------------------------


def _apply_decision_to_alert(
    alert: ProcessedAlert, decision: str, *, now: datetime, user_id: int | None
) -> None:
    """Set the V1 publication state for one alert per the candidate-backfill
    decision. Defensive: refuses to publish an irrelevant 'approved' alert.
    """
    risk_band = compute_risk_band(alert.signal_score_total).value
    alert.risk_band = risk_band
    alert.publishing_policy_version = DEFAULT_V1_POLICY.version
    alert.publication_state_source = DecisionSource.CANDIDATE_BACKFILL.value
    alert.publication_state_updated_at = now

    if decision == "approved":
        if not alert.is_relevant:
            raise ValueError(
                f"refusing to publish irrelevant alert {alert.id} (approved)"
            )
        alert.is_published = True
        if alert.published_at is None:
            alert.published_at = now
        if user_id is not None and alert.published_by_user_id is None:
            alert.published_by_user_id = user_id
        alert.published_by_rule = False
        alert.is_excluded = False
        alert.excluded_reason = None
        alert.is_manual_hold = False
        alert.publish_decision = PublishDecisionValue.AUTO_PUBLISH.value
        alert.publish_decision_reason = "candidate_backfill_approved"
        alert.pending_review_reason = None
    elif decision == "rejected":
        alert.is_published = False
        alert.published_at = None
        alert.published_by_user_id = None
        alert.published_by_rule = False
        alert.publish_decision = PublishDecisionValue.EXCLUDE.value
        alert.publish_decision_reason = "candidate_backfill_rejected"
        alert.pending_review_reason = PendingReviewReason.MANUAL_REJECTED.value
        alert.is_excluded = True
        alert.excluded_reason = "candidate_backfill_rejected"
        alert.is_manual_hold = False
    elif decision == "keep_later":
        alert.is_published = False
        alert.published_at = None
        alert.published_by_user_id = None
        alert.published_by_rule = False
        alert.publish_decision = PublishDecisionValue.HOLD.value
        alert.publish_decision_reason = "candidate_backfill_keep_later"
        alert.pending_review_reason = PendingReviewReason.MANUAL_HOLD.value
        alert.is_excluded = False
        alert.excluded_reason = None
        alert.is_manual_hold = True
    else:  # pragma: no cover - guarded by caller
        raise ValueError(f"unknown decision group {decision!r}")


def _make_review_row(
    alert_id: int, decision: str, *, user_id: int | None, batch_id: str
) -> AlertReview:
    # reviewed_at is intentionally NOT set here: AlertReview.reviewed_at is mapped
    # as a naive column (default=func.now()), so populating it from the app's
    # tz-aware ``now`` is rejected by asyncpg on Postgres. Rely on the server-side
    # func.now() default, exactly like the other AlertReview creators in the app.
    return AlertReview(
        alert_id=alert_id,
        user_id=user_id,
        review_status=_REVIEW_STATUS[decision],
        decision_source=DecisionSource.CANDIDATE_BACKFILL.value,
        review_batch_id=batch_id,
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def _refused(errors: list[str], **extra) -> dict:
    return {"mode": "apply_refused", "applied": False, "errors": errors, **extra}


async def run_apply(
    input_path: str | Path,
    *,
    session: AsyncSession,
    apply: bool = False,
    dry_run_report_path: str | Path | None = None,
    batch_id: str | None = None,
    confirm: str | None = None,
    user_id: int | None = None,
    sheet: str | None = None,
    expected_counts: dict[str, int] | None = None,
) -> dict:
    """Dry-run (default) or guarded transactional apply. Returns a report dict.

    Without ``apply`` this is a pure read-only dry-run. With ``apply`` it enforces
    every safety gate and only mutates inside a single transaction that rolls back
    on any error.
    """
    expected = expected_counts or EXPECTED_COUNTS

    if not apply:
        report = await run_dry_run(
            input_path, session=session, expected_counts=expected,
            allow_count_mismatch=False, sheet=sheet,
        )
        report["applied"] = False
        return report

    # --- Static apply-mode flag gates ---
    if confirm != CONFIRM_TOKEN:
        return _refused([f"confirm_required: pass --confirm {CONFIRM_TOKEN}"])
    if not dry_run_report_path:
        return _refused(["dry_run_report_required_for_apply"])
    if not batch_id:
        return _refused(["batch_id_required_for_apply"])

    # --- Load the prior (supplied) dry-run report ---
    try:
        prior = json.loads(Path(dry_run_report_path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _refused([f"dry_run_report_not_found: {dry_run_report_path}"])
    except json.JSONDecodeError as exc:
        return _refused([f"dry_run_report_not_json: {exc}"])

    # --- Fresh dry-run against the CURRENT DB + input (strict counts) ---
    fresh = await run_dry_run(
        input_path, session=session, expected_counts=expected,
        allow_count_mismatch=False, sheet=sheet,
    )

    errors = validate_dry_run_report_for_apply(prior, fresh, expected_counts=expected)
    if errors:
        return _refused(
            errors, input_file=str(input_path), batch_id=batch_id,
            dry_run_report=str(dry_run_report_path),
        )

    # --- Apply in a single transaction (rollback on any failure) ---
    now = datetime.now(timezone.utc)
    ids = sorted(int(a["alert_id"]) for g in _DECISION_GROUPS for a in fresh["planned_actions"][g])
    decision_by_id = {
        int(a["alert_id"]): g for g in _DECISION_GROUPS for a in fresh["planned_actions"][g]
    }
    updated: dict[str, list[int]] = {g: [] for g in _DECISION_GROUPS}
    reviews_created = 0

    try:
        stmt = (
            select(ProcessedAlert)
            .where(ProcessedAlert.id.in_(ids))
            .options(selectinload(ProcessedAlert.raw_item).selectinload(RawItem.source))
        )
        stmt = _maybe_lock(stmt, session)
        by_id = {a.id: a for a in (await session.execute(stmt)).scalars().all()}

        # Defensive re-check (the dry-run already verified this).
        missing = [i for i in ids if i not in by_id]
        if missing:
            raise RuntimeError(f"alerts vanished between dry-run and apply: {missing}")

        for alert_id in ids:
            decision = decision_by_id[alert_id]
            alert = by_id[alert_id]
            _apply_decision_to_alert(alert, decision, now=now, user_id=user_id)
            session.add(_make_review_row(alert_id, decision, user_id=user_id, batch_id=batch_id))
            updated[decision].append(alert_id)
            reviews_created += 1

        await session.commit()
    except Exception as exc:
        await session.rollback()
        return _refused(
            [f"apply_failed_rolled_back: {exc}"], input_file=str(input_path),
            batch_id=batch_id, dry_run_report=str(dry_run_report_path),
        )

    return {
        "mode": "apply",
        "applied": True,
        "batch_id": batch_id,
        "input_file": str(input_path),
        "dry_run_report": str(dry_run_report_path),
        "generated_at": now.isoformat(),
        "counts": {
            **{g: len(updated[g]) for g in _DECISION_GROUPS},
            "total": sum(len(updated[g]) for g in _DECISION_GROUPS),
        },
        "updated_alert_ids": {g: sorted(updated[g]) for g in _DECISION_GROUPS},
        "review_records_created": reviews_created,
        "publication_state_source": DecisionSource.CANDIDATE_BACKFILL.value,
        "publishing_policy_version": DEFAULT_V1_POLICY.version,
        "warnings": [],
        "passed": True,
    }


def _maybe_lock(stmt, session: AsyncSession):
    """Add FOR UPDATE only on dialects that support it (skip SQLite tests)."""
    try:
        name = session.get_bind().dialect.name
    except Exception:
        name = ""
    if name and name != "sqlite":
        return stmt.with_for_update()
    return stmt


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _apply_console_summary(report: dict) -> str:
    if report.get("mode") == "apply":
        c = report["counts"]
        return "\n".join([
            "Candidate Backfill APPLY",
            f"Batch: {report['batch_id']}",
            f"Applied: approved={c['approved']} rejected={c['rejected']} "
            f"keep_later={c['keep_later']} total={c['total']}",
            f"Review records created: {report['review_records_created']}",
            f"Passed: {report['passed']}",
        ])
    if report.get("mode") == "apply_refused":
        return "Candidate Backfill APPLY REFUSED\n" + "\n".join(
            f"  - {e}" for e in report["errors"]
        ) + "\nNo database changes were applied."
    # dry-run mode
    return console_summary(report) + "\n(apply not requested — no changes made)"


async def _main_async(args: argparse.Namespace) -> int:
    from app.database import AsyncSessionLocal  # local import keeps module test-friendly

    async with AsyncSessionLocal() as session:
        report = await run_apply(
            args.input,
            session=session,
            apply=args.apply,
            dry_run_report_path=args.dry_run_report,
            batch_id=args.batch_id,
            confirm=args.confirm,
            user_id=args.user_id,
            sheet=args.sheet,
        )

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(_apply_console_summary(report))
    if args.output:
        print(f"\nReport written to: {args.output}")
    return 0 if report.get("passed") or report.get("applied") else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Apply Ken's reviewed Candidate Alert decisions. Default is a "
        "read-only dry-run; --apply requires a passing dry-run report + confirm token."
    )
    parser.add_argument("--input", required=True, help="Reviewed decisions (.csv or .xlsx)")
    parser.add_argument("--dry-run-report", help="Path to a prior full-DB dry-run JSON (required for --apply)")
    parser.add_argument("--batch-id", help="Audit batch id (required for --apply)")
    parser.add_argument("--apply", action="store_true", help="Actually mutate the DB (otherwise dry-run only)")
    parser.add_argument("--confirm", help=f"Must equal {CONFIRM_TOKEN} when using --apply")
    parser.add_argument("--user-id", type=int, help="Optional admin/system user id for audit attribution")
    parser.add_argument("--sheet", help="Optional XLSX sheet override")
    parser.add_argument("--output", help="Optional JSON report path")
    args = parser.parse_args(argv)
    return asyncio.run(_main_async(args))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
