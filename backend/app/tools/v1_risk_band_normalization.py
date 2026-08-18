"""V1 ``risk_band`` normalization — one-time materialization tool.

Some ``processed_alerts`` rows have ``signal_score_total`` populated but
``risk_band`` left ``NULL`` — pre-V1 rows the live pipeline never touched, and
legacy candidate-backfill rows created before the ``risk_band`` column
existed. Because the Admin API's Critical/High filter reads the stored
``risk_band`` column directly while the Subscriber API used to recompute a
band from ``signal_score_total`` at query time, these NULL rows were invisible
to Admin's Critical/High filters but visible to Subscriber's. The canonical
risk-band alignment (``app/services/alert_query.py``) removes that query-time
recomputation everywhere — which means these existing rows need their
``risk_band`` materialized once, deterministically, from the score they
already have, or they simply disappear from *every* Critical/High view rather
than just Admin's.

Scope, by design:
  * Writes ONLY ``ProcessedAlert.risk_band``. Never touches
    ``signal_score_total`` or its five components, ``is_relevant``,
    ``is_published``, ``publish_decision``, ``published_at``, or any other
    publication-state field.
  * Never calls AI, never re-scores, never re-runs the pipeline, never creates
    an ``AlertReview`` row — this is a data-completeness fix, not a review
    decision, so it doesn't participate in the review audit trail. The JSON
    report this tool writes is the audit record.
  * Selection is deterministic: every ``risk_band IS NULL`` row, banded via
    the exact same ``compute_risk_band()`` the live pipeline uses today — no
    new thresholds, no new logic invented for this tool.
  * Unscored rows (``signal_score_total IS NULL``) are included by default,
    assigned ``below_60``. This matches confirmed current pipeline behavior:
    every live terminal path that completes with no score
    (``app/pipeline/alert_pipeline.py::_apply_terminal_state``) already writes
    exactly ``risk_band = below_60`` for a NULL score, so normalizing the
    equivalent legacy rows the same way keeps the domain internally
    consistent — it does not invent new semantics. Pass ``--exclude-unscored``
    to stage the two categories separately if that's ever preferable.

Concurrency: dry-run is pure SELECT, never opens a write transaction. Apply
locks each candidate row (``SELECT ... FOR UPDATE``, the same guarded pattern
``v1_candidate_backfill_apply.py`` uses) before its defensive re-check and
mutation, all inside one transaction — see ``run()`` for why this closes the
race a plain re-select-then-check cannot.

Run as a module from the backend directory. Default (no ``--apply``) is a
read-only dry-run that never opens a write transaction:

    python -m app.tools.v1_risk_band_normalization

Apply requires an explicit confirmation token:

    python -m app.tools.v1_risk_band_normalization \\
      --apply --confirm APPLY_V1_RISK_BAND_NORMALIZATION

Idempotent by construction: the selection predicate is ``risk_band IS NULL``,
so a second run (dry or apply) after a successful apply finds nothing left in
scope and reports zero proposed/applied rows — safe to re-run at any time. A
full default run drives ``COUNT(*) WHERE risk_band IS NULL`` to zero.
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

from app.models.processed_alert import ProcessedAlert
from app.pipeline.publishing.risk_bands import compute_risk_band

CONFIRM_TOKEN = "APPLY_V1_RISK_BAND_NORMALIZATION"

_BANDS = ("critical", "high", "medium", "below_60")


def _proposed_band(score: int | None) -> str:
    return compute_risk_band(score).value


def _maybe_lock(stmt, session: AsyncSession):
    """Add FOR UPDATE only on dialects that support it (skip SQLite tests).

    Mirrors the identical guard in ``app/tools/v1_candidate_backfill_apply.py``
    — same stack, same reason: SQLite (the isolated test DB) has no row-level
    locking, and the tests never run concurrently against it, so the guard is
    a no-op there and a real lock against production Postgres.
    """
    try:
        name = session.get_bind().dialect.name
    except Exception:
        name = ""
    if name and name != "sqlite":
        return stmt.with_for_update()
    return stmt


async def _select_candidates(
    session: AsyncSession,
) -> list[tuple[int, int | None, bool]]:
    """Every risk_band IS NULL row, scored or not, unlocked — this is the
    planning read used by both the dry-run and the pre-apply plan. It is
    deliberately not the read apply mutates from; see ``run()``."""
    stmt = select(
        ProcessedAlert.id, ProcessedAlert.signal_score_total, ProcessedAlert.is_published
    ).where(ProcessedAlert.risk_band.is_(None))
    return list((await session.execute(stmt)).all())


async def run(
    session: AsyncSession,
    *,
    apply: bool = False,
    confirm: str | None = None,
    include_unscored: bool = True,
) -> dict:
    """Dry-run (default) or guarded apply. Always returns a full report dict —
    the dry-run report and the pre-apply plan are the same computation, so
    there's no separate "preview" code path that could disagree with what
    apply actually does.
    """
    now = datetime.now(timezone.utc)
    rows = await _select_candidates(session)

    by_band: dict[str, list[int]] = {b: [] for b in _BANDS}
    published_by_band: dict[str, int] = dict.fromkeys(_BANDS, 0)
    unscored_candidates = 0
    unscored_included = 0

    for alert_id, score, is_published in rows:
        if score is None:
            unscored_candidates += 1
            if not include_unscored:
                continue
            unscored_included += 1
        band = _proposed_band(score)
        by_band[band].append(alert_id)
        if is_published:
            published_by_band[band] += 1

    total = sum(len(v) for v in by_band.values())
    null_count_before = len(rows)
    # Purely arithmetic — no extra query. Rows this run would leave untouched
    # are exactly the unscored ones excluded by --exclude-unscored.
    null_count_after_expected = null_count_before - total

    report: dict = {
        "mode": "apply" if apply else "dry_run",
        "generated_at": now.isoformat(),
        "include_unscored": include_unscored,
        "candidates_considered": len(rows),
        "risk_band_null_count_before": null_count_before,
        "risk_band_null_count_after_expected": null_count_after_expected,
        "proposed_assignments": {b: len(ids) for b, ids in by_band.items()},
        "proposed_assignments_total": total,
        "proposed_published_by_band": published_by_band,
        # unscored_candidates: rows with signal_score_total IS NULL among the
        # risk_band IS NULL set, regardless of what this run does with them.
        # unscored_included: how many of those this run actually assigned
        # below_60 (all of them when include_unscored=True, the default).
        # unscored_excluded: how many this run deliberately left NULL.
        "unscored_candidates": unscored_candidates,
        "unscored_included": unscored_included,
        "unscored_excluded": unscored_candidates - unscored_included,
        "alert_ids_by_band": by_band,
        "applied": False,
    }

    if not apply:
        return report

    if confirm != CONFIRM_TOKEN:
        report["mode"] = "apply_refused"
        report["errors"] = [f"confirm_required: pass --confirm {CONFIRM_TOKEN}"]
        return report

    if total == 0:
        report["applied"] = True
        report["note"] = "nothing to do — no matching risk_band IS NULL rows"
        return report

    try:
        all_ids = [i for ids in by_band.values() for i in ids]

        # The row-locking read apply actually mutates from. SELECT ... FOR
        # UPDATE takes an exclusive lock on each of these rows for the rest of
        # this transaction: any concurrent writer trying to UPDATE (or also
        # SELECT ... FOR UPDATE) the same row blocks until this transaction
        # commits or rolls back. That closes the race a plain re-select could
        # not — under the earlier plain-SELECT approach, a concurrent manual
        # approval or a second normalization run could commit a change to a
        # row *between* our re-check and our commit, and we would silently
        # overwrite it. With the lock held from this SELECT through our own
        # commit, nothing can change these specific rows underneath us: the
        # values we validate below are guaranteed to be the values still
        # there when we write.
        stmt = _maybe_lock(
            select(ProcessedAlert).where(ProcessedAlert.id.in_(all_ids)), session
        )
        alerts = {a.id: a for a in (await session.execute(stmt)).scalars().all()}
        missing = [i for i in all_ids if i not in alerts]
        if missing:
            raise RuntimeError(f"alerts vanished since selection: {missing}")

        for band, ids in by_band.items():
            for alert_id in ids:
                alert = alerts[alert_id]
                # Defensive re-check against the locked read: catches a
                # change that already committed before we acquired the lock
                # (the lock itself only prevents changes *after* this point).
                if alert.risk_band is not None:
                    raise RuntimeError(
                        f"alert {alert_id} risk_band was set concurrently "
                        f"(now {alert.risk_band!r}) — refusing to overwrite"
                    )
                recomputed = _proposed_band(alert.signal_score_total)
                if recomputed != band:
                    raise RuntimeError(
                        f"alert {alert_id} score changed since selection "
                        f"({band} -> {recomputed}) — refusing to apply a stale band"
                    )
                alert.risk_band = band

        await session.commit()
    except Exception as exc:
        await session.rollback()
        report["mode"] = "apply_refused"
        report["errors"] = [f"apply_failed_rolled_back: {exc}"]
        return report

    report["applied"] = True
    return report


def console_summary(report: dict) -> str:
    lines = [f"V1 Risk Band Normalization — {report['mode']}"]
    if report["mode"] == "apply_refused":
        lines.append("REFUSED — no database changes were made:")
        for e in report.get("errors", []):
            lines.append(f"  - {e}")
        return "\n".join(lines)

    lines.append(f"Candidates considered (risk_band IS NULL): {report['candidates_considered']}")
    lines.append(f"  risk_band NULL before: {report['risk_band_null_count_before']}")
    lines.append(f"  risk_band NULL after (expected): {report['risk_band_null_count_after_expected']}")
    lines.append(
        f"Include unscored (signal_score_total IS NULL -> below_60): "
        f"{report['include_unscored']}"
    )
    lines.append(
        f"  unscored candidates: {report['unscored_candidates']} "
        f"(included: {report['unscored_included']}, excluded: {report['unscored_excluded']})"
    )
    for band in _BANDS:
        lines.append(
            f"  {band:>9}: {report['proposed_assignments'][band]:4d} rows "
            f"({report['proposed_published_by_band'][band]} already published)"
        )
    lines.append(f"  Total proposed: {report['proposed_assignments_total']}")
    lines.append(f"Applied: {report['applied']}")
    if report.get("note"):
        lines.append(f"Note: {report['note']}")
    return "\n".join(lines)


async def _main_async(args: argparse.Namespace) -> int:
    from app.database import AsyncSessionLocal  # local import keeps module test-friendly

    async with AsyncSessionLocal() as session:
        report = await run(
            session,
            apply=args.apply,
            confirm=args.confirm,
            include_unscored=not args.exclude_unscored,
        )

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(console_summary(report))
    if args.output:
        print(f"\nJSON report written to: {args.output}")
    return 0 if report["mode"] != "apply_refused" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="One-time materialization of processed_alerts.risk_band from "
        "the existing signal_score_total, for legacy rows the V1 pipeline never "
        "touched. Never rescores, never calls AI, never changes publication "
        "state. Default is a read-only dry-run."
    )
    parser.add_argument("--apply", action="store_true", help="Apply (default: dry-run).")
    parser.add_argument("--confirm", help=f"Must equal {CONFIRM_TOKEN} for --apply.")
    parser.add_argument(
        "--exclude-unscored",
        action="store_true",
        help="Do NOT assign below_60 to rows with signal_score_total IS NULL "
        "(they are included by default — this matches confirmed current "
        "pipeline behavior for equivalent live terminal states).",
    )
    parser.add_argument("--output", help="Path to write the JSON report.")
    args = parser.parse_args(argv)
    return asyncio.run(_main_async(args))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
