"""Shared query semantics for the Published-alert intelligence feed.

Single source of truth for the business rules Admin (``GET /api/v1/alerts``)
and Subscriber (``GET /api/v1/subscriber/alerts``) must never be allowed to
define independently:

  1. **Risk-band filtering** — always reads the stored ``ProcessedAlert.risk_band``
     column. Nothing here, or anywhere else in the codebase, recomputes a band
     from ``signal_score_total`` at query time. Before this module existed,
     the Subscriber list did exactly that recomputation while the Admin list
     read the stored column — the two surfaces silently disagreed on which
     alerts were "Critical"/"High" whenever a row's ``risk_band`` was NULL but
     its score wasn't (see ``app/tools/v1_risk_band_normalization.py`` for the
     one-time backfill that closes that gap for existing rows).

  2. **Published-alert ordering** — ``published_at DESC NULLS LAST,
     processed_at DESC, id DESC``. ``published_at`` is when HiddenAlerts
     published the intelligence; ``processed_at`` breaks ties and orders
     never-published rows (NULL ``published_at``) among themselves; ``id``
     is the final deterministic tie-breaker so equal-timestamp rows still
     have one stable, repeatable order across paginated calls. Admin uses
     this ordering only when it's actually viewing the Published subset — its
     operational states (Draft, Review, Excluded, Hold, "All Status") order
     differently, entirely within ``app/api/alerts.py``, since that's
     Admin-specific behavior with no Subscriber equivalent (those orderings
     carry their own ``id DESC`` tie-breaker too).

  3. **Date-range filtering** — two independent, non-aliased timestamps:
     ``published_at`` (HiddenAlerts' own publish time) and
     ``RawItem.published_at`` (the original source article's date, exposed to
     callers as ``source_published_at``). Neither is ever substituted for the
     other.

Both APIs accept the same ``risk_band`` query parameter with the same four
canonical values (``critical``/``high``/``medium``/``below_60``) — there is no
translation layer here, and none should be reintroduced.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Select, select
from sqlalchemy.orm import selectinload

from app.models.processed_alert import ProcessedAlert
from app.models.raw_item import RawItem
from app.models.source import Source
from app.pipeline.publishing.constants import RISK_BANDS
from app.services.alert_category_service import published_alert_filter

#: Canonical Published-alert ordering — see module docstring point 2. The
#: trailing ``id.desc()`` is a pure tie-breaker: without it, rows sharing an
#: identical (published_at, processed_at) pair have no defined relative order,
#: so equal-timestamp pages could return duplicates/gaps or reorder between
#: identical calls. ``id`` is monotonically assigned and never reused, so it's
#: a safe deterministic tie-breaker that doesn't change any real ordering.
PUBLISHED_ORDER_BY = (
    ProcessedAlert.published_at.desc().nullslast(),
    ProcessedAlert.processed_at.desc(),
    ProcessedAlert.id.desc(),
)


def risk_band_filter(risk_band: str):
    """The one canonical V1 risk-band predicate, always against the stored column.

    ``risk_band`` must be one of the four canonical stored values — both Admin
    and Subscriber validate their ``risk_band`` query parameter against
    ``RISK_BANDS`` before reaching this function, so an invalid value is
    rejected with a 422 at the route rather than raising here.
    """
    if risk_band not in RISK_BANDS:
        raise ValueError(f"Not a canonical risk band: {risk_band!r}")
    return ProcessedAlert.risk_band == risk_band


def apply_published_at_filters(
    stmt: Select,
    *,
    published_from: datetime | None,
    published_to: datetime | None,
) -> Select:
    """Filter on ``ProcessedAlert.published_at`` — when HiddenAlerts published it."""
    if published_from is not None:
        stmt = stmt.where(ProcessedAlert.published_at >= published_from)
    if published_to is not None:
        stmt = stmt.where(ProcessedAlert.published_at <= published_to)
    return stmt


def apply_category_filter(stmt: Select, *, category: str | None) -> Select:
    """Filter on ``ProcessedAlert.primary_category`` — identical predicate for
    Admin and Subscriber, so it lives here instead of being written twice."""
    if category is not None:
        stmt = stmt.where(ProcessedAlert.primary_category == category)
    return stmt


def apply_source_name_filter(
    stmt: Select,
    *,
    source: str | None,
    raw_item_joined: bool,
) -> tuple[Select, bool]:
    """Filter on the source's display name (partial, case-insensitive match).

    Joins ``raw_items``/``sources`` only when ``source`` is actually given and
    only if the caller hasn't already joined ``raw_items`` for another reason
    (Admin's ``source_id``/``keyword`` filters, for instance) —
    ``raw_item_joined`` is threaded through the same way
    ``apply_source_published_at_filters`` does, so the join is never added
    twice.
    """
    if source is None:
        return stmt, raw_item_joined
    if not raw_item_joined:
        stmt = stmt.join(RawItem, RawItem.id == ProcessedAlert.raw_item_id)
        raw_item_joined = True
    stmt = stmt.join(Source, Source.id == RawItem.source_id).where(
        Source.name.ilike(f"%{source}%")
    )
    return stmt, raw_item_joined


def _as_naive_utc(value: datetime | None) -> datetime | None:
    """Normalize a datetime for comparison against ``RawItem.published_at``.

    That column is genuinely ``TIMESTAMP WITH TIME ZONE`` in PostgreSQL, but
    ``app/models/raw_item.py`` declares it with a bare ``mapped_column(...)``
    and no explicit ``DateTime(timezone=True)`` — so SQLAlchemy compiles bind
    parameters against it as a naive ``DateTime``, and asyncpg's naive
    ``timestamp_encode`` codec raises ``TypeError: can't subtract
    offset-naive and offset-aware datetimes`` when handed the timezone-aware
    datetime FastAPI parses from an ISO 8601 query parameter (e.g.
    ``2026-08-17T12:00:00Z``). This is a model/column type-declaration
    mismatch, not a naive database column — production's Postgres session
    runs with ``TimeZone=UTC`` (verified), so a naive value sent through that
    encoder is interpreted as a UTC wall-clock instant. Converting to UTC
    before stripping ``tzinfo`` therefore preserves the exact instant
    requested, not just avoids the crash.

    ``None`` passes through unchanged. An already-naive input is assumed to
    already be UTC — the convention used everywhere else in this codebase —
    and is returned unchanged rather than re-interpreted, since re-stamping it
    to a different offset would silently shift the instant. Does not mutate
    its argument: ``astimezone``/``replace`` both return new objects.
    """
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def apply_source_published_at_filters(
    stmt: Select,
    *,
    source_published_from: datetime | None,
    source_published_to: datetime | None,
    raw_item_joined: bool,
) -> tuple[Select, bool]:
    """Filter on ``RawItem.published_at`` — the original article date.

    Joins ``raw_items`` only when a filter is actually requested and only if
    the caller hasn't already joined it for another reason (``source=`` search,
    for instance) — ``raw_item_joined`` is threaded through so the join is
    never added twice.

    Bounds are normalized through :func:`_as_naive_utc` before binding — see
    its docstring for why ``RawItem.published_at`` specifically needs this and
    ``ProcessedAlert.published_at`` (in :func:`apply_published_at_filters`)
    does not.
    """
    if source_published_from is None and source_published_to is None:
        return stmt, raw_item_joined
    if not raw_item_joined:
        stmt = stmt.join(RawItem, RawItem.id == ProcessedAlert.raw_item_id)
        raw_item_joined = True
    if source_published_from is not None:
        stmt = stmt.where(RawItem.published_at >= _as_naive_utc(source_published_from))
    if source_published_to is not None:
        stmt = stmt.where(RawItem.published_at <= _as_naive_utc(source_published_to))
    return stmt, raw_item_joined


def published_alerts_stmt(
    *,
    risk_band: str | None = None,
    category: str | None = None,
    source: str | None = None,
    published_from: datetime | None = None,
    published_to: datetime | None = None,
    source_published_from: datetime | None = None,
    source_published_to: datetime | None = None,
) -> Select:
    """The Subscriber Alerts API's Published-only query: ``is_published = True``
    plus the canonical risk-band, category, source, and date filters built from
    the primitives above. Admin's equivalent Published view
    (``GET /api/v1/alerts?is_published=true``) is built from the exact same
    ``published_alert_filter``/``risk_band_filter``/``apply_category_filter``/
    ``apply_source_name_filter``/``apply_published_at_filters``/
    ``apply_source_published_at_filters``/``PUBLISHED_ORDER_BY`` primitives
    directly in ``app/api/alerts.py`` rather than calling this function, since
    Admin also composes them with operational filters (Draft, Review, Excluded,
    Hold) this query has no notion of — the primitives are shared, not this
    assembled statement.
    """
    stmt = (
        select(ProcessedAlert)
        .where(published_alert_filter())
        .options(selectinload(ProcessedAlert.raw_item).selectinload(RawItem.source))
        .order_by(*PUBLISHED_ORDER_BY)
    )
    raw_item_joined = False

    if risk_band is not None:
        stmt = stmt.where(risk_band_filter(risk_band))
    stmt = apply_category_filter(stmt, category=category)
    stmt, raw_item_joined = apply_source_name_filter(
        stmt, source=source, raw_item_joined=raw_item_joined
    )

    stmt = apply_published_at_filters(
        stmt, published_from=published_from, published_to=published_to
    )
    stmt, raw_item_joined = apply_source_published_at_filters(
        stmt,
        source_published_from=source_published_from,
        source_published_to=source_published_to,
        raw_item_joined=raw_item_joined,
    )
    return stmt
