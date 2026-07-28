"""Guard preventing overlapping collection runs for the same source.

Claimed by ``app.pipeline.collector.collect_source``, the single entry point for
both scheduled and manual collection, so the two cannot overlap on one source.
Different sources are independent.

Process-local: the claim set is not shared across workers or containers, which is
sufficient for the current single-worker deployment. A multi-worker or multi-host
deployment would need a PostgreSQL advisory lock or a database lease instead.
"""
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
