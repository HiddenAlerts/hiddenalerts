"""Source recovery preview — read-only estimate of prospective collection volume.

Answers, before anything is collected: *if we ran these sources now, how many new
items would we get, and how many of them would actually carry usable content?*

The tool is read-only by construction. It never touches the collector, never
creates a ``RawItem`` or ``RunLog``, never mutates a loaded ``Source``, never calls
``add``/``delete``/``flush``/``commit``, and imports no AI module. On PostgreSQL it
runs inside a ``SET TRANSACTION READ ONLY`` transaction that is rolled back, and it
verifies row counts before and after — a mismatch is a hard failure (exit 4).

Configuration changes are simulated: an overlay JSON describes a proposed
``base_url``/``rss_url``/``source_type`` per source, which is applied to a detached
copy so the real row is never altered. That is how a corrected listing URL can be
evaluated before anyone updates the database.

Run from the backend directory::

    python -m app.tools.source_recovery_preview --all-enabled \\
        --output-json reports/preview.json --output-markdown reports/preview.md

    python -m app.tools.source_recovery_preview --source-id 8 --mode content \\
        --overlay reports/proposed_config.json --max-unseen-per-source 10

Exit codes: 0 completed · 2 invalid arguments or overlay · 3 a source preview
failed · 4 read-only verification failed.
"""
import argparse
import asyncio
import hashlib
import json
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.processed_alert import ProcessedAlert
from app.models.raw_item import RawItem
from app.models.run_log import RunLog
from app.models.source import Source
from app.pipeline.normalizer import compute_content_hash, compute_url_hash
from app.services.source_url_decisions import get_suppressing_decisions
from app.sources.http_errors import (
    DestinationExcluded,
    SourceFetchError,
    redact_url,
)
from app.sources.registry import get_adapter

EXIT_OK = 0
EXIT_BAD_INPUT = 2
EXIT_SOURCE_FAILED = 3
EXIT_READ_ONLY_VIOLATION = 4

DEFAULT_MAX_UNSEEN = 25

#: The only fields an overlay may propose. ``adapter_class`` and ``id`` are
#: excluded on purpose: changing which code runs is a code review, not a preview.
OVERRIDABLE_FIELDS = ("base_url", "rss_url", "source_type")

#: Fields copied onto the detached preview source. Adapters read these and
#: nothing else.
_SOURCE_FIELDS = (
    "id", "name", "base_url", "source_type", "rss_url", "adapter_class",
    "is_active", "credibility_score", "polling_frequency_minutes",
)

# Item outcomes, in report order.
ARTICLE_READY = "article_ready"
SUMMARY_READY = "summary_ready"
CONTENT_DUPLICATE = "content_duplicate"
EXTERNAL_DESTINATION_EXCLUDED = "external_destination_excluded"
INVALID_CONTENT = "invalid_content"
UNAVAILABLE = "unavailable"
UNEXPECTED_ERROR = "unexpected_error"
NOT_CHECKED_DUE_TO_LIMIT = "not_checked_due_to_limit"

OUTCOMES = (
    ARTICLE_READY, SUMMARY_READY, CONTENT_DUPLICATE,
    EXTERNAL_DESTINATION_EXCLUDED, INVALID_CONTENT, UNAVAILABLE,
    UNEXPECTED_ERROR, NOT_CHECKED_DUE_TO_LIMIT,
)

# Source statuses.
LISTING_READY = "listing_ready"
CONTENT_READY = "content_ready"
PARTIALLY_CHECKED = "partially_checked"
EMPTY_UPSTREAM = "empty_upstream"
CONFIGURATION_BLOCKED = "configuration_blocked"
SOURCE_FAILED = "source_failed"

_COUNTED_TABLES = {
    "sources": Source,
    "raw_items": RawItem,
    "run_logs": RunLog,
    "processed_alerts": ProcessedAlert,
}


class PreviewConfigError(Exception):
    """The request or the overlay cannot be honoured."""


class ReadOnlyViolation(Exception):
    """The database changed while the preview was running."""


# ---------------------------------------------------------------------------
# Detached configuration
# ---------------------------------------------------------------------------


@dataclass
class EffectiveSource:
    """A detached stand-in for a ``Source`` row, carrying overlay values.

    Adapters read attributes off ``self.source``; they neither know nor care that
    this is not the ORM object. Keeping it detached is what guarantees an overlay
    can never reach the database — there is nothing here for SQLAlchemy to flush.
    """

    id: int
    name: str
    base_url: str | None
    source_type: str | None
    rss_url: str | None
    adapter_class: str | None
    is_active: bool = True
    credibility_score: int | None = None
    polling_frequency_minutes: int | None = None

    @classmethod
    def from_row(cls, row: Source, overrides: dict[str, Any] | None = None) -> "EffectiveSource":
        values = {name: getattr(row, name, None) for name in _SOURCE_FIELDS}
        values.update(overrides or {})
        return cls(**values)


def _config_snapshot(obj: Any) -> dict[str, Any]:
    """The configuration fields worth reporting, current or effective."""
    return {
        "base_url": getattr(obj, "base_url", None),
        "rss_url": getattr(obj, "rss_url", None),
        "source_type": getattr(obj, "source_type", None),
        "adapter_class": getattr(obj, "adapter_class", None),
    }


def load_overlay(path: Path) -> tuple[dict[int, dict[str, Any]], str]:
    """Parse and validate an overlay file. Returns ``({id: entry}, sha256)``.

    Structural validation only — comparing ``expect`` against the database happens
    once the rows are loaded.
    """
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise PreviewConfigError(f"cannot read overlay {path}: {exc}") from exc

    digest = hashlib.sha256(raw).hexdigest()
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PreviewConfigError(f"overlay is not valid JSON: {exc}") from exc

    if not isinstance(document, dict) or not isinstance(document.get("sources"), list):
        raise PreviewConfigError('overlay must be an object with a "sources" list')

    entries: dict[int, dict[str, Any]] = {}
    for index, entry in enumerate(document["sources"]):
        if not isinstance(entry, dict):
            raise PreviewConfigError(f"overlay sources[{index}] must be an object")

        source_id = entry.get("id")
        if not isinstance(source_id, int) or isinstance(source_id, bool):
            raise PreviewConfigError(f"overlay sources[{index}] needs an integer id")
        if source_id in entries:
            raise PreviewConfigError(f"overlay lists source {source_id} more than once")

        expect = entry.get("expect") or {}
        override = entry.get("override") or {}
        if not isinstance(expect, dict) or not isinstance(override, dict):
            raise PreviewConfigError(
                f"overlay source {source_id}: expect and override must be objects"
            )
        if not override:
            raise PreviewConfigError(f"overlay source {source_id} overrides nothing")

        for key in override:
            if key not in OVERRIDABLE_FIELDS:
                raise PreviewConfigError(
                    f"overlay source {source_id}: {key!r} may not be overridden "
                    f"(allowed: {', '.join(OVERRIDABLE_FIELDS)})"
                )

        entries[source_id] = {"expect": expect, "override": override}

    return entries, digest


def check_expectations(row: Source, expect: dict[str, Any]) -> list[str]:
    """Field-by-field mismatches between the overlay's ``expect`` and the row."""
    mismatches = []
    for key, expected in expect.items():
        if not hasattr(row, key):
            mismatches.append(f"{key}: unknown field")
            continue
        actual = getattr(row, key)
        if actual != expected:
            mismatches.append(f"{key}: expected {expected!r}, found {actual!r}")
    return mismatches


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


@dataclass
class ItemRecord:
    """One prospective item. Carries no content, ever."""

    url: str
    url_hash: str
    title: str
    published_at: str | None
    outcome: str
    content_origin: str | None = None
    error_class: str | None = None
    error_message: str | None = None
    destination: str | None = None


@dataclass
class SourcePreview:
    source_id: int
    name: str
    adapter_class: str | None
    status: str
    current_config: dict[str, Any] = field(default_factory=dict)
    effective_config: dict[str, Any] = field(default_factory=dict)
    config_changed: bool = False
    config_differences: dict[str, Any] = field(default_factory=dict)

    stubs_fetched: int = 0
    invalid_urls: int = 0
    batch_duplicates: int = 0
    unique_urls: int = 0
    known_urls: int = 0
    #: URLs this source has already ruled out — recorded decisions, not backlog.
    previously_excluded_external: int = 0
    prospective_unseen: int = 0
    missing_titles: int = 0
    missing_dates: int = 0
    oldest_prospective: str | None = None
    newest_prospective: str | None = None
    empty_upstream: bool = False

    checked_unseen: int = 0
    unchecked_unseen: int = 0
    predicted_storable: int = 0
    outcome_counts: dict[str, int] = field(default_factory=dict)
    items: list[ItemRecord] = field(default_factory=list)

    error_class: str | None = None
    error_message: str | None = None


# ---------------------------------------------------------------------------
# Read-only database boundary
# ---------------------------------------------------------------------------


async def begin_read_only(session: AsyncSession) -> bool:
    """Put the session's transaction in read-only mode where supported.

    Returns True when the database enforced it. PostgreSQL rejects any write for
    the rest of the transaction; SQLite (tests) has no equivalent, so the
    before/after count check is what covers it there.
    """
    dialect = session.bind.dialect.name if session.bind is not None else ""
    if dialect != "postgresql":
        return False
    await session.execute(text("SET TRANSACTION READ ONLY"))
    return True


async def table_counts(session: AsyncSession) -> dict[str, int]:
    counts = {}
    for label, model in _COUNTED_TABLES.items():
        result = await session.execute(select(func.count()).select_from(model))
        counts[label] = int(result.scalar_one())
    return counts


# ---------------------------------------------------------------------------
# Listing mode
# ---------------------------------------------------------------------------


def _iso(value: Any) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


async def classify_stubs(
    session: AsyncSession, stubs: list, source_id: int | None = None
) -> dict[str, Any]:
    """Split fetched stubs the way the collector's pre-filter does.

    Uses production ``compute_url_hash``, the same batch known-hash query and the
    same source-scoped decision lookup, so the unseen count here is the count the
    collector would act on. A URL this source has already excluded is reported
    under ``previously_excluded_external`` and is *not* prospective backlog.

    Read-only: the lookup never advances ``occurrence_count`` or ``last_seen_at``.
    """
    invalid = 0
    batch: dict[str, Any] = {}
    duplicates = 0

    for stub in stubs:
        url = (getattr(stub, "item_url", "") or "").strip()
        if not url:
            invalid += 1
            continue
        try:
            url_hash = compute_url_hash(url)
        except Exception:
            invalid += 1
            continue
        if url_hash in batch:
            duplicates += 1
        batch[url_hash] = stub

    from app.pipeline.deduplicator import get_known_url_hashes

    known = await get_known_url_hashes(session, set(batch))
    unstored = [(h, s) for h, s in batch.items() if h not in known]

    decisions = (
        await get_suppressing_decisions(session, source_id, {h for h, _ in unstored})
        if source_id is not None
        else {}
    )
    unseen = [(h, s) for h, s in unstored if h not in decisions]

    dates = [s.published_at for _, s in unseen if getattr(s, "published_at", None)]
    return {
        "invalid_urls": invalid,
        "batch_duplicates": duplicates,
        "unique_urls": len(batch),
        "known_urls": len(batch) - len(unstored),
        "previously_excluded_external": len(unstored) - len(unseen),
        "unseen": unseen,
        "missing_titles": sum(1 for _, s in unseen if not (getattr(s, "title", "") or "").strip()),
        "missing_dates": sum(1 for _, s in unseen if not getattr(s, "published_at", None)),
        "oldest": _iso(min(dates)) if dates else None,
        "newest": _iso(max(dates)) if dates else None,
    }


# ---------------------------------------------------------------------------
# Content mode
# ---------------------------------------------------------------------------


async def _check_item(session: AsyncSession, adapter, stub, url_hash: str) -> ItemRecord:
    """Decide what the collector *would* store for this item, without storing it.

    Mirrors ``run_source`` stage 2 exactly — the same hooks, in the same order —
    minus every write.
    """
    record = ItemRecord(
        url=redact_url(stub.item_url),
        url_hash=url_hash,
        title=(getattr(stub, "title", "") or "").strip(),
        published_at=_iso(getattr(stub, "published_at", None)),
        outcome=INVALID_CONTENT,
    )

    raw_text = ""
    try:
        if adapter.should_fetch_article(stub):
            try:
                raw_text, _ = await adapter.fetch_full_article(stub.item_url)
                record.content_origin = "article"
            except DestinationExcluded as exc:
                # Another source is canonical for this item. No summary is
                # consulted, exactly as the collector does it.
                record.outcome = EXTERNAL_DESTINATION_EXCLUDED
                record.error_class = type(exc).__name__
                record.destination = exc.destination
                return record
            except SourceFetchError as exc:
                from app.sources.base import summary_fallback_allowed

                record.error_class = type(exc).__name__
                record.error_message = _safe_message(exc)
                if summary_fallback_allowed(exc):
                    raw_text = adapter.summary_fallback(stub, exc) or ""
                    if raw_text:
                        record.content_origin = "summary"
                if not raw_text:
                    record.outcome = UNAVAILABLE
                    return record
        else:
            raw_text = adapter.summary_fallback(stub, None) or ""
            record.content_origin = "summary" if raw_text else None
    except Exception as exc:  # noqa: BLE001 — a bug here fails the source, not the item
        record.outcome = UNEXPECTED_ERROR
        record.error_class = type(exc).__name__
        record.error_message = _safe_message(exc)
        raise PreviewItemError(record) from exc

    if not raw_text.strip():
        record.outcome = INVALID_CONTENT
        record.content_origin = None
        return record

    from app.pipeline.deduplicator import is_content_duplicate

    if await is_content_duplicate(session, compute_content_hash(raw_text)):
        record.outcome = CONTENT_DUPLICATE
        return record

    record.outcome = ARTICLE_READY if record.content_origin == "article" else SUMMARY_READY
    return record


class PreviewItemError(Exception):
    """An unexpected error while checking one item — fails the whole source."""

    def __init__(self, record: ItemRecord) -> None:
        super().__init__(record.error_message or "unexpected error")
        self.record = record


def _safe_message(exc: Exception) -> str:
    """A short error message with no URL query string and no body."""
    message = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
    if "?" in message:
        message = message.split("?", 1)[0] + " …"
    return message[:200]


# ---------------------------------------------------------------------------
# Per-source preview
# ---------------------------------------------------------------------------


async def preview_source(
    session: AsyncSession,
    row: Source,
    *,
    overlay_entry: dict[str, Any] | None,
    mode: str,
    max_unseen: int,
) -> SourcePreview:
    """Preview one source. Never writes, never mutates ``row``."""
    current = _config_snapshot(row)
    preview = SourcePreview(
        source_id=row.id, name=row.name, adapter_class=row.adapter_class,
        status=LISTING_READY, current_config=current, effective_config=dict(current),
    )

    overrides: dict[str, Any] = {}
    if overlay_entry:
        mismatches = check_expectations(row, overlay_entry.get("expect") or {})
        if mismatches:
            preview.status = CONFIGURATION_BLOCKED
            preview.error_class = "ExpectationMismatch"
            preview.error_message = "; ".join(mismatches)[:200]
            return preview
        overrides = dict(overlay_entry.get("override") or {})

    effective = EffectiveSource.from_row(row, overrides)
    preview.effective_config = _config_snapshot(effective)
    preview.config_differences = {
        key: {"current": current[key], "effective": preview.effective_config[key]}
        for key in preview.effective_config
        if current[key] != preview.effective_config[key]
    }
    preview.config_changed = bool(preview.config_differences)

    try:
        adapter = get_adapter(effective)
    except Exception as exc:  # noqa: BLE001 — an unusable adapter blocks this source
        preview.status = CONFIGURATION_BLOCKED
        preview.error_class = type(exc).__name__
        preview.error_message = _safe_message(exc)
        return preview

    try:
        stubs = await adapter.fetch_item_stubs()
    except Exception as exc:  # noqa: BLE001 — typed or not, this source is out
        preview.status = SOURCE_FAILED
        preview.error_class = type(exc).__name__
        preview.error_message = _safe_message(exc)
        return preview

    preview.stubs_fetched = len(stubs)
    classified = await classify_stubs(session, stubs, row.id)
    preview.invalid_urls = classified["invalid_urls"]
    preview.batch_duplicates = classified["batch_duplicates"]
    preview.unique_urls = classified["unique_urls"]
    preview.known_urls = classified["known_urls"]
    preview.previously_excluded_external = classified["previously_excluded_external"]
    preview.missing_titles = classified["missing_titles"]
    preview.missing_dates = classified["missing_dates"]
    preview.oldest_prospective = classified["oldest"]
    preview.newest_prospective = classified["newest"]

    unseen = classified["unseen"]
    preview.prospective_unseen = len(unseen)

    # A feed that parsed cleanly and holds nothing is healthy, not broken.
    if not stubs:
        preview.empty_upstream = True
        preview.status = EMPTY_UPSTREAM
        return preview

    if mode != "content":
        return preview

    counts = dict.fromkeys(OUTCOMES, 0)
    for index, (url_hash, stub) in enumerate(unseen):
        if index >= max_unseen:
            counts[NOT_CHECKED_DUE_TO_LIMIT] += 1
            preview.items.append(ItemRecord(
                url=redact_url(stub.item_url), url_hash=url_hash,
                title=(getattr(stub, "title", "") or "").strip(),
                published_at=_iso(getattr(stub, "published_at", None)),
                outcome=NOT_CHECKED_DUE_TO_LIMIT,
            ))
            continue
        try:
            record = await _check_item(session, adapter, stub, url_hash)
        except PreviewItemError as exc:
            preview.items.append(exc.record)
            counts[UNEXPECTED_ERROR] += 1
            preview.outcome_counts = counts
            preview.checked_unseen = index
            preview.unchecked_unseen = len(unseen) - index
            preview.status = SOURCE_FAILED
            preview.error_class = exc.record.error_class
            preview.error_message = exc.record.error_message
            return preview
        counts[record.outcome] += 1
        preview.items.append(record)

    preview.outcome_counts = counts
    preview.unchecked_unseen = counts[NOT_CHECKED_DUE_TO_LIMIT]
    preview.checked_unseen = len(unseen) - preview.unchecked_unseen
    preview.predicted_storable = counts[ARTICLE_READY] + counts[SUMMARY_READY]
    # Content duplicates are already excluded: an item classified as a duplicate
    # never lands in article_ready or summary_ready.
    preview.status = PARTIALLY_CHECKED if preview.unchecked_unseen else CONTENT_READY
    return preview


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], capture_output=True, text=True, timeout=10, check=False,
        ).stdout.strip()
    except Exception:  # noqa: BLE001 — provenance is best-effort metadata
        return ""


def build_totals(previews: list[SourcePreview]) -> dict[str, int]:
    def total(attr: str) -> int:
        return sum(getattr(p, attr) for p in previews)

    def outcome(name: str) -> int:
        return sum(p.outcome_counts.get(name, 0) for p in previews)

    return {
        "sources_previewed": len(previews),
        "stubs_fetched": total("stubs_fetched"),
        "known_urls": total("known_urls"),
        "previously_excluded_external": total("previously_excluded_external"),
        "batch_duplicates": total("batch_duplicates"),
        "invalid_urls": total("invalid_urls"),
        "prospective_unseen": total("prospective_unseen"),
        "checked_unseen": total("checked_unseen"),
        "unchecked_unseen": total("unchecked_unseen"),
        "predicted_storable": total("predicted_storable"),
        "article_ready": outcome(ARTICLE_READY),
        "summary_ready": outcome(SUMMARY_READY),
        "content_duplicates": outcome(CONTENT_DUPLICATE),
        "external_destination_excluded": outcome(EXTERNAL_DESTINATION_EXCLUDED),
        "invalid_content": outcome(INVALID_CONTENT),
        "unavailable": outcome(UNAVAILABLE),
        "unexpected_errors": outcome(UNEXPECTED_ERROR),
        "failed_sources": sum(1 for p in previews if p.status == SOURCE_FAILED),
        "configuration_blocked": sum(
            1 for p in previews if p.status == CONFIGURATION_BLOCKED
        ),
        "healthy_empty_sources": sum(1 for p in previews if p.status == EMPTY_UPSTREAM),
    }


def build_report(
    previews: list[SourcePreview],
    *,
    mode: str,
    max_unseen: int,
    overlay_sha256: str | None,
    counts_before: dict[str, int],
    counts_after: dict[str, int],
    read_only_enforced: bool,
    db_revision: str | None,
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "tool": "source_recovery_preview",
        "read_only": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "branch": _git("branch", "--show-current"),
        "commit": _git("rev-parse", "HEAD"),
        "database_revision": db_revision,
        "mode": mode,
        "max_unseen_per_source": max_unseen,
        "overlay_sha256": overlay_sha256,
        "read_only_transaction_enforced": read_only_enforced,
        "database_counts_before": counts_before,
        "database_counts_after": counts_after,
        "database_counts_match": counts_before == counts_after,
        "totals": build_totals(previews),
        "sources": [
            {
                **{k: v for k, v in asdict(p).items() if k != "items"},
                "items": [asdict(i) for i in p.items],
            }
            for p in sorted(previews, key=lambda p: p.source_id)
        ],
        "configuration_differences": {
            str(p.source_id): p.config_differences
            for p in sorted(previews, key=lambda p: p.source_id)
            if p.config_differences
        },
        "errors": [
            {
                "source_id": p.source_id, "name": p.name, "status": p.status,
                "error_class": p.error_class, "error_message": p.error_message,
            }
            for p in sorted(previews, key=lambda p: p.source_id)
            if p.status in (SOURCE_FAILED, CONFIGURATION_BLOCKED)
        ],
        "warnings": warnings,
    }


def render_markdown(report: dict[str, Any]) -> str:
    totals = report["totals"]
    lines = [
        "# Source recovery preview",
        "",
        "Read-only estimate. No item was collected, stored, or processed.",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Branch / commit: `{report['branch'] or '?'}` / `{(report['commit'] or '?')[:12]}`",
        f"- Database revision: `{report['database_revision'] or '?'}`",
        f"- Mode: `{report['mode']}` (max {report['max_unseen_per_source']} unseen per source)",
        f"- Overlay SHA-256: `{report['overlay_sha256'] or '(none)'}`",
        f"- Read-only transaction enforced: `{report['read_only_transaction_enforced']}`",
        f"- Row counts unchanged: `{report['database_counts_match']}`",
        "",
        "## Totals",
        "",
        "| Metric | Count |",
        "|---|---:|",
    ]
    for key, value in totals.items():
        lines.append(f"| {key.replace('_', ' ')} | {value} |")

    lines += [
        "",
        "## Sources",
        "",
        "| ID | Name | Status | Fetched | Known | Prev. external | Unseen | "
        "Checked | Storable | Excluded |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for source in report["sources"]:
        lines.append(
            "| {id} | {name} | `{status}` | {fetched} | {known} | {prev} | "
            "{unseen} | {checked} | {storable} | {excluded} |".format(
                id=source["source_id"], name=source["name"], status=source["status"],
                fetched=source["stubs_fetched"], known=source["known_urls"],
                prev=source["previously_excluded_external"],
                unseen=source["prospective_unseen"], checked=source["checked_unseen"],
                storable=source["predicted_storable"],
                excluded=source["outcome_counts"].get(EXTERNAL_DESTINATION_EXCLUDED, 0),
            )
        )

    if report["configuration_differences"]:
        lines += ["", "## Configuration differences (simulated only)", "",
                  "| Source | Field | Current | Effective |", "|---|---|---|---|"]
        for source_id, diffs in report["configuration_differences"].items():
            for field_name, values in diffs.items():
                lines.append(
                    f"| {source_id} | {field_name} | `{values['current']}` | "
                    f"`{values['effective']}` |"
                )

    if report["errors"]:
        lines += ["", "## Errors", "", "| Source | Status | Error |", "|---|---|---|"]
        for err in report["errors"]:
            lines.append(
                f"| {err['source_id']} {err['name']} | `{err['status']}` | "
                f"{err['error_class']}: {err['error_message']} |"
            )

    if report["warnings"]:
        lines += ["", "## Warnings", ""]
        lines += [f"- {w}" for w in report["warnings"]]

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


async def _select_sources(
    session: AsyncSession, source_ids: list[int], all_enabled: bool, excluded: set[int]
) -> list[Source]:
    if all_enabled:
        statement = select(Source).where(Source.is_active.is_(True)).order_by(Source.id)
    else:
        statement = select(Source).where(Source.id.in_(source_ids)).order_by(Source.id)
    rows = list((await session.execute(statement)).scalars().all())

    if not all_enabled:
        found = {row.id for row in rows}
        missing = sorted(set(source_ids) - found)
        if missing:
            raise PreviewConfigError(f"unknown source id(s): {missing}")

    return [row for row in rows if row.id not in excluded]


async def run_preview(
    session: AsyncSession,
    *,
    source_ids: list[int],
    all_enabled: bool,
    excluded: set[int],
    overlay: dict[int, dict[str, Any]] | None,
    overlay_sha256: str | None,
    mode: str,
    max_unseen: int,
) -> dict[str, Any]:
    """Run the whole preview inside one read-only transaction."""
    read_only_enforced = await begin_read_only(session)
    counts_before = await table_counts(session)

    revision = None
    try:
        revision = (await session.execute(text("SELECT version_num FROM alembic_version"))).scalar()
    except Exception:  # noqa: BLE001 — absent on the test database
        revision = None

    rows = await _select_sources(session, source_ids, all_enabled, excluded)

    warnings: list[str] = []
    if overlay:
        unknown = sorted(set(overlay) - {row.id for row in rows})
        if unknown:
            raise PreviewConfigError(
                f"overlay names source id(s) not in this run: {unknown}"
            )

    previews = []
    for row in rows:
        previews.append(
            await preview_source(
                session, row,
                overlay_entry=(overlay or {}).get(row.id),
                mode=mode, max_unseen=max_unseen,
            )
        )

    for preview in previews:
        if preview.status == PARTIALLY_CHECKED:
            warnings.append(
                f"source {preview.source_id} has {preview.unchecked_unseen} unchecked "
                f"unseen item(s); totals are a lower bound"
            )

    counts_after = await table_counts(session)
    if counts_before != counts_after:
        raise ReadOnlyViolation(
            f"row counts changed during a read-only preview: "
            f"{counts_before} → {counts_after}"
        )

    return build_report(
        previews, mode=mode, max_unseen=max_unseen, overlay_sha256=overlay_sha256,
        counts_before=counts_before, counts_after=counts_after,
        read_only_enforced=read_only_enforced, db_revision=revision, warnings=warnings,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="source_recovery_preview",
        description="Read-only preview of prospective source collection volume "
                    "and content readiness. Writes nothing, collects nothing.",
    )
    parser.add_argument("--source-id", type=int, action="append", default=[],
                        help="Preview this source. Repeatable.")
    parser.add_argument("--all-enabled", action="store_true",
                        help="Preview every currently active source.")
    parser.add_argument("--exclude-source-id", type=int, action="append", default=[],
                        help="Skip this source. Repeatable.")
    parser.add_argument("--overlay", type=Path,
                        help="Source configuration overlay JSON, applied in memory only.")
    parser.add_argument("--mode", choices=("listing", "content"), default="listing",
                        help="listing: discovery counts. content: also check readiness.")
    parser.add_argument("--max-unseen-per-source", type=int, default=DEFAULT_MAX_UNSEEN,
                        help=f"Unseen items to inspect in content mode (default {DEFAULT_MAX_UNSEEN}).")
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-markdown", type=Path)
    return parser


async def main(argv: list[str] | None = None, session_factory=AsyncSessionLocal) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    overlay: dict[int, dict[str, Any]] | None = None
    overlay_sha256: str | None = None
    try:
        if not args.source_id and not args.all_enabled:
            raise PreviewConfigError("choose sources with --source-id or --all-enabled")
        if args.source_id and args.all_enabled:
            raise PreviewConfigError("--source-id and --all-enabled are mutually exclusive")
        if args.max_unseen_per_source < 0:
            raise PreviewConfigError("--max-unseen-per-source must not be negative")
        if len(set(args.source_id)) != len(args.source_id):
            raise PreviewConfigError("--source-id repeats a source")
        if args.overlay:
            overlay, overlay_sha256 = load_overlay(args.overlay)
    except PreviewConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_BAD_INPUT

    try:
        async with session_factory() as session:
            report = await run_preview(
                session,
                source_ids=list(args.source_id),
                all_enabled=args.all_enabled,
                excluded=set(args.exclude_source_id),
                overlay=overlay,
                overlay_sha256=overlay_sha256,
                mode=args.mode,
                max_unseen=args.max_unseen_per_source,
            )
            # Nothing was written, but roll back explicitly so the read-only
            # transaction ends the way it started.
            await session.rollback()
    except PreviewConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_BAD_INPUT
    except ReadOnlyViolation as exc:
        print(f"read-only verification failed: {exc}", file=sys.stderr)
        return EXIT_READ_ONLY_VIOLATION

    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(report, indent=2, sort_keys=False) + "\n")
    if args.output_markdown:
        args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.output_markdown.write_text(render_markdown(report))
    if not args.output_json and not args.output_markdown:
        print(json.dumps(report, indent=2))

    totals = report["totals"]
    if totals["failed_sources"] or totals["configuration_blocked"]:
        return EXIT_SOURCE_FAILED
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover - module entry point
    raise SystemExit(asyncio.run(main()))
