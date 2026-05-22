from __future__ import annotations

from datetime import datetime, timedelta, timezone

ACCESS_GRANTING_STATUSES = frozenset({"active", "trialing"})


def has_active_subscription_access(
    status: str | None,
    current_period_end: datetime | None,
    now: datetime | None = None,
    grace_seconds: int = 0,
) -> bool:
    """Decide whether a (status, current_period_end) pair grants subscriber access.

    Pure function — no database, no Stripe calls. Encodes the access matrix from
    CLAUDE.md "Access rules":
        - active / trialing grant access
        - canceled grants access only while current_period_end (plus an optional
          grace window) is in the future
        - past_due, unpaid, incomplete, incomplete_expired, missing, or unknown deny access
    Naive datetimes are treated as UTC so callers cannot accidentally grant access
    via a timezone-stripped value.

    ``grace_seconds`` (default 0, fully backward compatible) extends the canceled
    window by that many seconds — e.g. to tolerate clock skew or a short post-cancel
    courtesy period. It applies only to the canceled branch.
    """
    if status is None:
        return False
    if status in ACCESS_GRANTING_STATUSES:
        return True
    if status == "canceled":
        if current_period_end is None:
            return False
        ref = now if now is not None else datetime.now(timezone.utc)
        period_end = current_period_end
        if period_end.tzinfo is None:
            period_end = period_end.replace(tzinfo=timezone.utc)
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)
        return period_end + timedelta(seconds=max(0, grace_seconds)) > ref
    return False
