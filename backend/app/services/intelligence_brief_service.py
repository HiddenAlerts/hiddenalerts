"""Admin-side business logic for Intelligence Briefs.

Owns the non-trivial parts of creating and editing briefs so the API layer stays
thin: slug generation and uniqueness, per-day brief-code allocation, HTML
sanitisation, and the derived ``alerts_count`` / ``read_time_minutes`` values.

The service raises small domain exceptions (below) which the router maps to HTTP
responses, keeping raw database errors away from clients.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.intelligence_brief import IntelligenceBrief
from app.models.intelligence_brief_constants import (
    BRIEF_RISK_LEVELS,
    DEFAULT_BRIEF_STATUS,
    DEFAULT_BRIEF_TYPE,
    SUBSCRIBER_VISIBLE_RISK_LEVELS,
    BriefStatus,
)
from app.schemas.intelligence_brief import (
    IntelligenceBriefCreate,
    IntelligenceBriefUpdate,
)
from app.services.html_sanitizer import sanitize_html
from app.services.intelligence_brief_helpers import (
    calculate_read_time,
    count_supporting_alerts,
    generate_brief_code,
    has_text_content,
    normalize_slug,
)

logger = logging.getLogger(__name__)

# Rich-text fields whose HTML is sanitised before storage. analyst_notes is
# admin-only but still sanitised — it is rendered in the admin UI.
RICH_TEXT_FIELDS = (
    "executive_summary",
    "why_this_matters",
    "risk_assessment",
    "what_others_miss",
    "implications",
    "main_intelligence_brief",
    "analyst_notes",
)

# Subscriber-visible content used to estimate reading time. analyst_notes is
# excluded because subscribers never see it.
READ_TIME_FIELDS = (
    "executive_summary",
    "why_this_matters",
    "risk_assessment",
    "what_others_miss",
    "implications",
    "main_intelligence_brief",
)

_MAX_SLUG_LENGTH = 255
# How many numeric suffixes (-2, -3, …) to try before falling back to a random
# token. Keeps slug disambiguation bounded rather than looping indefinitely.
_SLUG_SUFFIX_SCAN_LIMIT = 1000
_BRIEF_CODE_MAX_RETRIES = 5

# Rich-text fields that must carry content before a brief can be published.
_PUBLISH_REQUIRED_TEXT = ("executive_summary", "main_intelligence_brief")

# Risk levels eligible to become the global featured brief. This is the same
# critical/high set the subscriber library exposes — only briefs a subscriber
# could actually see are allowed to be featured.
_FEATURE_ELIGIBLE_RISK_LEVELS = SUBSCRIBER_VISIBLE_RISK_LEVELS


class BriefNotFoundError(Exception):
    """Raised when a brief id does not exist."""


class InvalidSlugError(Exception):
    """Raised when a caller-supplied slug normalises to an empty value."""


class SlugConflictError(Exception):
    """Raised when a caller-supplied slug is already taken by another brief."""

    def __init__(self, slug: str) -> None:
        super().__init__(f"slug already in use: {slug!r}")
        self.slug = slug


class BriefCodeAllocationError(Exception):
    """Raised when a unique brief_code could not be allocated after retries."""


class BriefPublishValidationError(Exception):
    """Raised when a brief is missing the content required to be published.

    Carries the list of offending field names so the API can tell the admin
    exactly what to fill in.
    """

    def __init__(self, fields: list[str]) -> None:
        super().__init__(f"brief is not ready to publish: {', '.join(sorted(fields))}")
        self.fields = sorted(fields)


class BriefFeatureEligibilityError(Exception):
    """Raised when a brief does not meet the rules to become the featured brief."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


async def get_brief(db: AsyncSession, brief_id: int) -> IntelligenceBrief | None:
    """Return a brief by id, or ``None`` if it does not exist."""
    result = await db.execute(
        select(IntelligenceBrief).where(IntelligenceBrief.id == brief_id)
    )
    return result.scalar_one_or_none()


async def list_briefs(
    db: AsyncSession,
    *,
    q: str | None = None,
    status: str | None = None,
    category: str | None = None,
    risk_level: str | None = None,
    brief_type: str | None = None,
    is_featured: bool | None = None,
    is_premium: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[IntelligenceBrief], int]:
    """List briefs matching the given filters, newest first.

    Returns the page of rows plus the total match count (for pagination). This
    is the admin view: all statuses and risk levels are visible. ``q`` is a
    case-insensitive substring match over title, executive summary and the main
    brief body.
    """
    filters = []
    if status is not None:
        filters.append(IntelligenceBrief.status == status)
    if category is not None:
        filters.append(IntelligenceBrief.category == category)
    if risk_level is not None:
        filters.append(IntelligenceBrief.risk_level == risk_level)
    if brief_type is not None:
        filters.append(IntelligenceBrief.brief_type == brief_type)
    if is_featured is not None:
        filters.append(IntelligenceBrief.is_featured == is_featured)
    if is_premium is not None:
        filters.append(IntelligenceBrief.is_premium == is_premium)
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(
            or_(
                IntelligenceBrief.title.ilike(pattern),
                IntelligenceBrief.executive_summary.ilike(pattern),
                IntelligenceBrief.main_intelligence_brief.ilike(pattern),
            )
        )

    total = (
        await db.execute(
            select(func.count()).select_from(IntelligenceBrief).where(*filters)
        )
    ).scalar_one()

    rows = (
        (
            await db.execute(
                select(IntelligenceBrief)
                .where(*filters)
                .order_by(IntelligenceBrief.created_at.desc(), IntelligenceBrief.id.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return list(rows), total


async def create_brief(
    db: AsyncSession,
    payload: IntelligenceBriefCreate,
    *,
    user_id: int | None = None,
) -> IntelligenceBrief:
    """Create a draft brief from an admin payload.

    Generates the slug (from the title when not supplied) and a unique daily
    brief code, sanitises rich-text HTML, and derives ``alerts_count`` and
    ``read_time_minutes``. The brief is always created in the draft state;
    publishing/featuring are separate actions.
    """
    data = payload.model_dump(exclude_unset=True)

    slug = await _resolve_slug(db, provided=data.get("slug"), title=data["title"])
    _sanitize_in_place(data)

    supporting_alerts = data.get("supporting_alerts")
    is_premium = data.get("is_premium")
    values = {
        "title": data["title"],
        "slug": slug,
        "category": data.get("category"),
        "risk_score": data.get("risk_score"),
        "risk_level": data.get("risk_level"),
        "primary_entities": data.get("primary_entities"),
        "tags": data.get("tags"),
        "time_horizon": data.get("time_horizon"),
        "executive_summary": data.get("executive_summary"),
        "why_this_matters": data.get("why_this_matters"),
        "key_signals": data.get("key_signals"),
        "risk_assessment": data.get("risk_assessment"),
        "what_others_miss": data.get("what_others_miss"),
        "implications": data.get("implications"),
        "main_intelligence_brief": data.get("main_intelligence_brief"),
        "analyst_notes": data.get("analyst_notes"),
        "supporting_alerts": supporting_alerts,
        "alerts_count": count_supporting_alerts(supporting_alerts),
        "confidence_level": data.get("confidence_level"),
        "read_time_minutes": _read_time_from(data),
        "brief_type": data.get("brief_type") or DEFAULT_BRIEF_TYPE,
        "featured_order": data.get("featured_order"),
        "is_premium": True if is_premium is None else is_premium,
        "status": DEFAULT_BRIEF_STATUS,
        "is_featured": False,
        "created_by_user_id": user_id,
        "updated_by_user_id": user_id,
    }

    return await _insert_with_brief_code(db, values)


async def update_brief(
    db: AsyncSession,
    brief_id: int,
    payload: IntelligenceBriefUpdate,
    *,
    user_id: int | None = None,
) -> IntelligenceBrief:
    """Apply a partial update to an existing brief.

    Only fields present in the request are changed. Rich-text fields are
    sanitised, ``alerts_count`` is recomputed when supporting alerts change, and
    ``read_time_minutes`` is recomputed when any subscriber-visible content
    field changes. Lifecycle (status/featured) is not editable here.
    """
    brief = await get_brief(db, brief_id)
    if brief is None:
        raise BriefNotFoundError(brief_id)

    data = payload.model_dump(exclude_unset=True)

    if "title" in data:
        brief.title = data["title"]
    # Only a non-empty slug in the payload changes the stored slug. An explicit
    # ``slug: null`` (or "") is treated as "leave it as-is" rather than silently
    # regenerating from the title.
    if data.get("slug"):
        brief.slug = await _resolve_slug(
            db, provided=data["slug"], title=brief.title, exclude_id=brief.id
        )

    _sanitize_in_place(data)

    # Directly-assignable columns (everything except title/slug handled above and
    # the derived counters below).
    assignable = (
        "category",
        "risk_score",
        "risk_level",
        "primary_entities",
        "tags",
        "time_horizon",
        "confidence_level",
        "brief_type",
        "featured_order",
        "is_premium",
        "supporting_alerts",
        *RICH_TEXT_FIELDS,
    )
    for field in assignable:
        if field in data:
            setattr(brief, field, data[field])

    if "supporting_alerts" in data:
        brief.alerts_count = count_supporting_alerts(brief.supporting_alerts)

    if any(field in data for field in READ_TIME_FIELDS):
        brief.read_time_minutes = calculate_read_time(
            *(getattr(brief, field) for field in READ_TIME_FIELDS)
        )

    brief.updated_by_user_id = user_id

    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        if _violates(exc, "slug"):
            raise SlugConflictError(brief.slug) from exc
        raise
    await db.refresh(brief)
    return brief


# ---------------------------------------------------------------------------
# Lifecycle actions
# ---------------------------------------------------------------------------


async def publish_brief(
    db: AsyncSession, brief_id: int, *, user_id: int | None = None
) -> IntelligenceBrief:
    """Move a brief to the published state.

    Publishing is allowed from draft or archived. ``published_at`` is stamped on
    the first publish and preserved thereafter, so re-publishing (or publishing a
    previously-published-then-archived brief) keeps the original publication
    date. Featuring is a separate action and is never triggered here.
    """
    brief = await get_brief(db, brief_id)
    if brief is None:
        raise BriefNotFoundError(brief_id)

    _validate_publishable(brief)

    brief.status = BriefStatus.PUBLISHED.value
    if brief.published_at is None:
        brief.published_at = datetime.now(timezone.utc)
    brief.updated_by_user_id = user_id

    await db.flush()
    await db.refresh(brief)
    return brief


async def archive_brief(
    db: AsyncSession, brief_id: int, *, user_id: int | None = None
) -> IntelligenceBrief:
    """Archive a brief and drop it out of the featured slot.

    Archiving is allowed from any state (idempotent when already archived).
    ``published_at`` is intentionally left untouched to preserve publication
    history; a re-published brief keeps its original date.
    """
    brief = await get_brief(db, brief_id)
    if brief is None:
        raise BriefNotFoundError(brief_id)

    brief.status = BriefStatus.ARCHIVED.value
    brief.is_featured = False
    brief.featured_order = None
    brief.updated_by_user_id = user_id

    await db.flush()
    await db.refresh(brief)
    return brief


async def feature_brief(
    db: AsyncSession, brief_id: int, *, user_id: int | None = None
) -> IntelligenceBrief:
    """Make a brief the single global featured brief.

    Only a published critical/high brief is eligible. The one-featured-brief
    invariant is enforced here: any other featured rows are cleared and flushed
    within the same transaction before this brief is marked featured, so a
    successful commit can never leave two featured briefs.
    """
    brief = await get_brief(db, brief_id)
    if brief is None:
        raise BriefNotFoundError(brief_id)

    _validate_feature_eligible(brief)

    await db.execute(
        update(IntelligenceBrief)
        .where(
            IntelligenceBrief.id != brief.id,
            IntelligenceBrief.is_featured.is_(True),
        )
        .values(is_featured=False, featured_order=None)
        .execution_options(synchronize_session=False)
    )

    brief.is_featured = True
    brief.featured_order = 1
    brief.updated_by_user_id = user_id

    await db.flush()
    await db.refresh(brief)
    return brief


async def unfeature_brief(
    db: AsyncSession, brief_id: int, *, user_id: int | None = None
) -> IntelligenceBrief:
    """Clear the featured state of a brief. Idempotent when not featured."""
    brief = await get_brief(db, brief_id)
    if brief is None:
        raise BriefNotFoundError(brief_id)

    brief.is_featured = False
    brief.featured_order = None
    brief.updated_by_user_id = user_id

    await db.flush()
    await db.refresh(brief)
    return brief


def _validate_publishable(brief: IntelligenceBrief) -> None:
    """Check a brief carries the minimum content required to publish.

    Raises ``BriefPublishValidationError`` listing every missing/invalid field.
    Rich-text fields must contain real text once HTML is stripped, so empty
    editor markup (e.g. ``"<p><br></p>"``) does not satisfy the requirement.
    confidence_level and key_signals are deliberately not required here; tighten
    this set if the content contract changes.
    """
    missing: list[str] = []

    for field in ("title", "slug", "brief_code", "category"):
        if not (getattr(brief, field) or "").strip():
            missing.append(field)

    if brief.risk_score is None or not (0 <= brief.risk_score <= 100):
        missing.append("risk_score")
    if brief.risk_level not in BRIEF_RISK_LEVELS:
        missing.append("risk_level")

    for field in _PUBLISH_REQUIRED_TEXT:
        if not has_text_content(getattr(brief, field)):
            missing.append(field)

    if missing:
        raise BriefPublishValidationError(missing)


def _validate_feature_eligible(brief: IntelligenceBrief) -> None:
    """Enforce the featured-brief eligibility rules (published + critical/high)."""
    if brief.status != BriefStatus.PUBLISHED.value:
        raise BriefFeatureEligibilityError(
            "only a published brief can be featured"
        )
    if brief.risk_level not in _FEATURE_ELIGIBLE_RISK_LEVELS:
        raise BriefFeatureEligibilityError(
            "only critical or high risk briefs can be featured"
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sanitize_in_place(data: dict) -> None:
    """Sanitise any rich-text HTML fields present in a payload dict."""
    for field in RICH_TEXT_FIELDS:
        if field in data:
            data[field] = sanitize_html(data[field])


def _read_time_from(data: dict) -> int:
    """Estimate read time from the subscriber-visible fields present in data."""
    return calculate_read_time(*(data.get(field) for field in READ_TIME_FIELDS))


async def _resolve_slug(
    db: AsyncSession,
    *,
    provided: str | None,
    title: str,
    exclude_id: int | None = None,
) -> str:
    """Produce a stored slug.

    A caller-supplied slug is normalised and must remain non-empty and unique —
    a collision is an explicit error (409). A slug generated from the title is
    made unique automatically by appending ``-2``, ``-3``, … so drafts never
    fail to save on a title clash. All slugs are kept within the column's
    255-character limit, and the suffix always fits in that budget.
    """
    if provided:
        base = _truncate_slug(normalize_slug(provided, fallback=""), _MAX_SLUG_LENGTH)
        if not base:
            raise InvalidSlugError(provided)
        if await _slug_taken(db, base, exclude_id):
            raise SlugConflictError(base)
        return base

    base = _truncate_slug(normalize_slug(title), _MAX_SLUG_LENGTH)
    if not await _slug_taken(db, base, exclude_id):
        return base

    for suffix in range(2, _SLUG_SUFFIX_SCAN_LIMIT + 1):
        candidate = _slug_with_suffix(base, str(suffix))
        if not await _slug_taken(db, candidate, exclude_id):
            return candidate

    # Extremely unlikely fallback: a random token guarantees termination without
    # ever re-producing an already-tried candidate.
    candidate = _slug_with_suffix(base, uuid.uuid4().hex[:8])
    if await _slug_taken(db, candidate, exclude_id):
        raise SlugConflictError(candidate)
    return candidate


def _truncate_slug(slug: str, max_length: int) -> str:
    """Trim a slug to at most ``max_length`` characters, dropping any trailing
    hyphen left by the cut."""
    return slug[:max_length].rstrip("-")


def _slug_with_suffix(base: str, suffix: str) -> str:
    """Combine a base slug with a disambiguating suffix within the length limit.

    The base is trimmed first so ``<base>-<suffix>`` never exceeds
    ``_MAX_SLUG_LENGTH``.
    """
    reserved = len(suffix) + 1  # +1 for the hyphen separator
    trimmed = _truncate_slug(base, _MAX_SLUG_LENGTH - reserved)
    return f"{trimmed}-{suffix}"


async def _slug_taken(
    db: AsyncSession, slug: str, exclude_id: int | None
) -> bool:
    """Return True if another brief already uses this slug."""
    stmt = select(IntelligenceBrief.id).where(IntelligenceBrief.slug == slug)
    if exclude_id is not None:
        stmt = stmt.where(IntelligenceBrief.id != exclude_id)
    return (await db.execute(stmt.limit(1))).scalar_one_or_none() is not None


async def _next_brief_code(db: AsyncSession, on_date) -> str:
    """Compute the next ``HA-YYYYMMDD-NNN`` code for the given UTC date.

    Uses the highest existing code for the date's prefix and increments its
    sequence. The unique constraint plus the retry loop in
    ``_insert_with_brief_code`` guard against the rare concurrent-insert race.
    """
    prefix = f"HA-{on_date:%Y%m%d}-"
    highest = (
        await db.execute(
            select(func.max(IntelligenceBrief.brief_code)).where(
                IntelligenceBrief.brief_code.like(f"{prefix}%")
            )
        )
    ).scalar_one_or_none()

    next_seq = 1
    if highest:
        try:
            next_seq = int(highest.rsplit("-", 1)[1]) + 1
        except (ValueError, IndexError):
            next_seq = 1
    return generate_brief_code(next_seq, on_date=on_date)


async def _insert_with_brief_code(db: AsyncSession, values: dict) -> IntelligenceBrief:
    """Insert a brief, allocating a unique brief_code with bounded retries.

    A concurrent create can grab the same next sequence; the unique constraint
    then rejects the loser, and we recompute and retry. A slug collision here is
    surfaced as a clean conflict rather than a raw DB error.
    """
    today = datetime.now(timezone.utc).date()
    last_error: IntegrityError | None = None

    for _ in range(_BRIEF_CODE_MAX_RETRIES):
        code = await _next_brief_code(db, today)
        brief = IntelligenceBrief(brief_code=code, **values)
        db.add(brief)
        try:
            await db.flush()
        except IntegrityError as exc:
            last_error = exc
            await db.rollback()
            if _violates(exc, "slug"):
                raise SlugConflictError(values["slug"]) from exc
            if _violates(exc, "brief_code"):
                continue
            raise
        else:
            await db.refresh(brief)
            return brief

    raise BriefCodeAllocationError(
        "could not allocate a unique brief_code"
    ) from last_error


def _violates(exc: IntegrityError, column: str) -> bool:
    """Best-effort check of which unique column an IntegrityError hit.

    Works across the asyncpg (constraint name ``uq_..._<column>``) and SQLite
    (``UNIQUE constraint failed: intelligence_briefs.<column>``) messages.
    """
    return column in str(getattr(exc, "orig", exc)).lower()
