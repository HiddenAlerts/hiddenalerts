"""In-process guard preventing overlapping manual collection runs per source.

Mirrors the locking approach already used for the AI pipeline
(``app.pipeline.alert_pipeline.is_processing``): a single asyncio primitive held
for the lifetime of a run, consulted before starting another.

Scope and limits — both deliberate:

* The claim set lives in this process only. The app runs as a single uvicorn
  worker, so it is authoritative for manual triggers today. It would not cover a
  multi-worker or multi-container deployment.
* It tracks *manual* triggers only. The scheduled collection job calls
  ``run_all_sources`` directly and does not claim a slot, so a manual trigger can
  still overlap a scheduled run. Closing that requires the guard to move into the
  collector itself.

Both limits are safe: overlapping runs waste work but cannot corrupt data — the
``uq_raw_items_url_hash`` constraint and the per-item ``IntegrityError`` handling
in ``app.pipeline.collector`` already make concurrent collection idempotent.
"""
from __future__ import annotations

import asyncio

_active_source_runs: set[int] = set()
_claim_lock = asyncio.Lock()


async def claim_source_run(source_id: int) -> bool:
    """Reserve the manual-collection slot for a source.

    Returns True when the slot was free and is now held by the caller, False when
    a manual run for this source is already in flight. Callers that receive True
    must pair it with :func:`release_source_run`.
    """
    async with _claim_lock:
        if source_id in _active_source_runs:
            return False
        _active_source_runs.add(source_id)
        return True


async def release_source_run(source_id: int) -> None:
    """Release a slot claimed by :func:`claim_source_run`. Safe to call twice."""
    async with _claim_lock:
        _active_source_runs.discard(source_id)


def is_source_collecting(source_id: int) -> bool:
    """Return True while a manual collection run for this source is in flight."""
    return source_id in _active_source_runs
