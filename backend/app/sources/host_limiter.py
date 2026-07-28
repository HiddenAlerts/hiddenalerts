"""Process-local minimum spacing between requests to the same hostname.

Every network attempt in the shared fetch layer passes through here, including
each retry and each redirect hop, so a chain that crosses hosts is spaced under
both. Hosts are independent: waiting on one never blocks another, because the
only shared structure is a plain dict touched without awaiting.

Scope: **this process only.** The state is in memory and is not shared across
uvicorn workers, containers or hosts — the same limitation the collection guard
carries. Multiple workers would each keep their own spacing, so the effective
rate against an upstream would multiply by the worker count.

Intervals are the pace we choose to request at. Sites that publish a preferred
crawl delay are configured to match it.
"""
import asyncio
import logging
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

# Bound on tracked hosts; stale entries are dropped once this is exceeded.
_MAX_TRACKED_HOSTS = 512


def normalize_host(host: str | None) -> str:
    return (host or "").strip().lower()


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
        self._default = default_interval
        self._intervals = dict(intervals) if intervals is not None else dict(HOST_INTERVAL_SECONDS)
        self._monotonic = monotonic
        self._sleep = sleep
        self._locks: dict[str, asyncio.Lock] = {}
        self._next_allowed: dict[str, float] = {}

    def interval_for(self, host: str) -> float:
        return self._intervals.get(normalize_host(host), self._default)

    def set_interval(self, host: str, seconds: float) -> None:
        self._intervals[normalize_host(host)] = seconds

    def _lock_for(self, host: str) -> asyncio.Lock:
        # No await between the check and the insert, so this is atomic under
        # asyncio and needs no global lock of its own.
        lock = self._locks.get(host)
        if lock is None:
            self._prune()
            lock = self._locks[host] = asyncio.Lock()
        return lock

    def _prune(self) -> None:
        if len(self._locks) <= _MAX_TRACKED_HOSTS:
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
