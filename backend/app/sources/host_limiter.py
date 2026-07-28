"""Process-local minimum spacing between requests to the same hostname.

Every network attempt in the shared fetch layer passes through here, including
each retry and each redirect hop, so a chain that crosses hosts is spaced under
both. Hosts are independent: waiting on one never blocks another, because the
only shared structure is a plain dict touched without awaiting.

Scope: **this process only.** The state is in memory and is not shared across
uvicorn workers, containers or hosts — the same limitation the collection guard
carries. Multiple workers would each keep their own spacing, so the effective
rate against an upstream would multiply by the worker count.

Memory: host state is pruned opportunistically rather than capped. See
``_SOFT_HOST_LIMIT``.

Intervals are the pace we choose to request at. Sites that publish a preferred
crawl delay are configured to match it.
"""
import asyncio
import logging
import math
import time
from collections.abc import Awaitable, Callable

log = logging.getLogger(__name__)

DEFAULT_INTERVAL_SECONDS = 1.0

# Hosts that publish a preferred crawl delay, plus anything we choose to be
# gentler with. Keys are lowercase hostnames.
HOST_INTERVAL_SECONDS: dict[str, float] = {
    "www.justice.gov": 10.0,
    "justice.gov": 10.0,
    "www.ftc.gov": 5.0,
    "ftc.gov": 5.0,
}

# Soft bound on tracked hosts. Pruning is opportunistic: it runs when a new host
# is first seen and only removes entries whose interval has elapsed and whose lock
# is free, so the map can legitimately exceed this while many hosts are in flight.
# It is not a hard cap.
_SOFT_HOST_LIMIT = 512


def normalize_host(host: str | None) -> str:
    """Lowercase, trim, and drop a trailing DNS root dot.

    ``justice.gov.`` and ``justice.gov`` are the same host and must share one
    limit, or a trailing dot would silently halve the interval.
    """
    host = (host or "").strip().lower()
    if len(host) > 1 and host.endswith("."):
        host = host.rstrip(".")
    return host


def _validate_interval(seconds: float, label: str) -> float:
    """Intervals must be real, finite and non-negative."""
    try:
        value = float(seconds)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} interval must be a number, got {seconds!r}") from exc
    if not math.isfinite(value):
        raise ValueError(f"{label} interval must be finite, got {value!r}")
    if value < 0:
        raise ValueError(f"{label} interval must be >= 0, got {value!r}")
    return value


class HostRateLimiter:
    """Enforces a minimum gap between request *starts* per hostname."""

    def __init__(
        self,
        *,
        default_interval: float = DEFAULT_INTERVAL_SECONDS,
        intervals: dict[str, float] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._default = _validate_interval(default_interval, "default")
        raw = dict(intervals) if intervals is not None else dict(HOST_INTERVAL_SECONDS)
        self._intervals = {
            normalize_host(h): _validate_interval(v, h) for h, v in raw.items()
        }
        self._monotonic = monotonic
        self._sleep = sleep
        self._locks: dict[str, asyncio.Lock] = {}
        self._next_allowed: dict[str, float] = {}

    def interval_for(self, host: str) -> float:
        return self._intervals.get(normalize_host(host), self._default)

    def set_interval(self, host: str, seconds: float) -> None:
        key = normalize_host(host)
        self._intervals[key] = _validate_interval(seconds, key)

    def _lock_for(self, host: str) -> asyncio.Lock:
        # No await between the check and the insert, so this is atomic under
        # asyncio and needs no global lock of its own.
        lock = self._locks.get(host)
        if lock is None:
            self._prune()
            lock = self._locks[host] = asyncio.Lock()
        return lock

    def _prune(self) -> None:
        """Opportunistic cleanup — best effort, not a hard bound (see module note)."""
        if len(self._locks) <= _SOFT_HOST_LIMIT:
            return
        now = self._monotonic()
        stale = [h for h, deadline in self._next_allowed.items()
                 if deadline < now and not self._locks[h].locked()]
        for host in stale:
            self._locks.pop(host, None)
            self._next_allowed.pop(host, None)

    async def acquire(self, host: str) -> float:
        """Wait until this host may be requested again. Returns seconds waited.

        The per-host lock is held across the wait so queued callers for the same
        host serialise; callers for other hosts are unaffected.
        """
        key = normalize_host(host)
        if not key:
            return 0.0
        interval = self.interval_for(key)
        async with self._lock_for(key):
            waited = 0.0
            deadline = self._next_allowed.get(key)
            if deadline is not None:
                remaining = deadline - self._monotonic()
                if remaining > 0:
                    log.debug("host limiter: waiting %.2fs before next request to %s", remaining, key)
                    await self._sleep(remaining)
                    waited = remaining
            self._next_allowed[key] = self._monotonic() + interval
            return waited


# Shared instance used by the source fetch layer.
host_limiter = HostRateLimiter()
