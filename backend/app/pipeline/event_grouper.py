"""Event grouping module — clusters related alerts into events.

Matches new alerts to existing events by:
  - Same primary_category
  - Entity name overlap (case-insensitive, at least 1 common entity)
  - Event last updated within 7 days

When a match is found, links the alert via EventSource and recalculates
cross-source scores for all alerts linked to that event.
When no match is found, creates a new Event record.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.event import Event, EventSource
from app.models.processed_alert import ProcessedAlert
from app.pipeline.signal_scorer import compute_cross_source_score, derive_risk_level

log = logging.getLogger(__name__)

# How many days back to look for matching events
EVENT_MATCH_WINDOW_DAYS = 7


async def find_or_create_event(
    alert: ProcessedAlert,
    session: AsyncSession,
) -> Event:
    """Match alert to an existing event or create a new one.

    Also creates the EventSource link and recalculates cross_source scores
    on all alerts linked to the matched/created event.

    Args:
        alert: The freshly-created ProcessedAlert (must have id set via flush).
        session: Async DB session (caller is responsible for commit).

    Returns:
        The matched or newly-created Event.
    """
    category = alert.primary_category
    entities = _extract_entity_names(alert)

    # Try to find a matching event
    matched_event = await _find_matching_event(category, entities, session)

    if matched_event is not None:
        log.debug(
            f"Alert {alert.id} matched event {matched_event.id} "
            f"({matched_event.title!r})"
        )
        event = matched_event
    else:
        # Create a new event
        event = await _create_event_for_alert(alert, entities, session)
        log.debug(f"Created new event {event.id} for alert {alert.id}")

    # Link this alert to the event
    source_name = _get_source_name(alert)
    event_source = EventSource(
        event_id=event.id,
        alert_id=alert.id,
        source_name=source_name,
    )
    session.add(event_source)
    await session.flush()  # Persist EventSource so count query is accurate

    # Recalculate cross-source scores for all alerts in this event
    await _recalculate_cross_source_score(event, session)

    return event


async def _find_matching_event(
    category: str | None,
    entities: list[str],
    session: AsyncSession,
) -> Event | None:
    """Query for recent events matching category + entity overlap.

    Returns the most recently updated matching event, or None.
    """
    if not category:
        return None

    # events.last_updated_at is TIMESTAMP WITHOUT TIME ZONE — use naive UTC
    cutoff = datetime.utcnow() - timedelta(days=EVENT_MATCH_WINDOW_DAYS)

    # Load recent events in same category with their linked alert entities
    stmt = (
        select(Event)
        .where(Event.category == category)
        .where(Event.last_updated_at >= cutoff)
        .options(
            selectinload(Event.event_sources).selectinload(EventSource.alert)
        )
        .order_by(Event.last_updated_at.desc())
    )
    result = await session.execute(stmt)
    candidate_events = result.scalars().all()

    if not candidate_events:
        return None

    # If current alert has no entities, match on category + time window only
    # (pick the most recent event in the same category)
    if not entities:
        log.debug(f"Alert has no entities; matching by category '{category}' only")
        return candidate_events[0]

    entities_lower = {e.lower() for e in entities}

    # Find first event with overlapping entities (already ordered by most recent)
    for event in candidate_events:
        event_entities = _collect_event_entities(event)
        if entities_lower & event_entities:
            return event

    return None


def _collect_event_entities(event: Event) -> set[str]:
    """Gather all entity names from alerts linked to an event (lowercase)."""
    event_entities: set[str] = set()
    for es in event.event_sources:
        if es.alert and es.alert.entities_json:
            names = es.alert.entities_json.get("names", [])
            if isinstance(names, list):
                event_entities.update(n.lower() for n in names if n)
    return event_entities


def _extract_entity_names(alert: ProcessedAlert) -> list[str]:
    """Extract entity names list from alert.entities_json."""
    if not alert.entities_json:
        return []
    names = alert.entities_json.get("names", [])
    if isinstance(names, list):
        return [n for n in names if n]
    return []


def _get_source_name(alert: ProcessedAlert) -> str | None:
    """Get source name from the alert's raw_item relationship."""
    try:
        if alert.raw_item and alert.raw_item.source:
            return alert.raw_item.source.name
    except Exception:
        pass
    return None


async def _create_event_for_alert(
    alert: ProcessedAlert,
    entities: list[str],
    session: AsyncSession,
) -> Event:
    """Create a new Event record for this alert."""
    primary_entity = entities[0] if entities else None

    # Derive event title from primary entity + category or fall back to article title
    if primary_entity and alert.primary_category:
        title = f"{primary_entity}: {alert.primary_category}"
    elif alert.raw_item and alert.raw_item.title:
        title = alert.raw_item.title[:200]
    else:
        title = alert.primary_category or "Fraud Event"

    # events table uses TIMESTAMP WITHOUT TIME ZONE — store naive UTC
    now = datetime.utcnow()
    event = Event(
        title=title,
        risk_level=alert.risk_level,
        category=alert.primary_category,
        primary_entity=primary_entity,
        first_detected_at=now,
        last_updated_at=now,
    )
    session.add(event)
    await session.flush()  # Get event.id
    return event


async def _recalculate_cross_source_score(
    event: Event,
    session: AsyncSession,
) -> None:
    """Recount event_sources for this event and update cross_source scores.

    Updates score_cross_source, signal_score_total, and risk_level on ALL
    ProcessedAlerts linked to this event.
    """
    # Count distinct sources for this event
    count_result = await session.execute(
        select(EventSource).where(EventSource.event_id == event.id)
    )
    event_sources = count_result.scalars().all()
    source_count = len(event_sources)
    new_cross_score = compute_cross_source_score(source_count)

    # Update all linked ProcessedAlerts
    for es in event_sources:
        if es.alert_id is None:
            continue
        alert_result = await session.execute(
            select(ProcessedAlert).where(ProcessedAlert.id == es.alert_id)
        )
        linked_alert = alert_result.scalar_one_or_none()
        if linked_alert is None:
            continue

        old_cross = linked_alert.score_cross_source or 1
        if old_cross == new_cross_score:
            continue  # No change needed

        linked_alert.score_cross_source = new_cross_score

        # Recalculate total and risk_level
        total = (
            (linked_alert.score_source_credibility or 1)
            + (linked_alert.score_financial_impact or 1)
            + (linked_alert.score_victim_scale or 1)
            + new_cross_score
            + (linked_alert.score_trend_acceleration or 1)
        )
        linked_alert.signal_score_total = total
        linked_alert.risk_level = derive_risk_level(total)

    # Touch event.last_updated_at — use naive UTC to match TIMESTAMP WITHOUT TIME ZONE column
    event.last_updated_at = datetime.utcnow()

    # Update event's risk_level to the highest of all linked alerts
    highest_risk = "low"
    for es in event_sources:
        if es.alert_id is None:
            continue
        alert_result = await session.execute(
            select(ProcessedAlert).where(ProcessedAlert.id == es.alert_id)
        )
        linked_alert = alert_result.scalar_one_or_none()
        if linked_alert and linked_alert.risk_level == "high":
            highest_risk = "high"
            break
        elif linked_alert and linked_alert.risk_level == "medium":
            highest_risk = "medium"

    event.risk_level = highest_risk
