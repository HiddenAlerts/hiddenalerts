#!/usr/bin/env python3
"""Audit script — flag (and optionally unpublish) published alerts that
violate Ken's fraud-relevance criteria.

Heuristic: a published alert is flagged if its title+summary contains any
"off-topic" term (CSAM, terrorism, weapons, drug trafficking, …) AND no
"positive" fraud-mechanism term (fraud, scam, laundering, …). Older alerts
were classified before the prompt + auto-publish guard were tightened, so
some non-fraud cases are still in the live feed and need cleanup.

Modes:
  --report (default)         Print flagged alerts in a human-readable table.
  --json                     Print flagged alerts as JSON (piped into jq, etc.).
  --apply --ids ID1 ID2 ...  Unpublish the specified IDs (sets is_published=False
                             and clears published_at). Requires explicit IDs —
                             never bulk-unpublishes the entire flagged set.

Run from the backend directory:
    python scripts/audit_offtopic_alerts.py
    python scripts/audit_offtopic_alerts.py --json
    python scripts/audit_offtopic_alerts.py --apply --ids 302 294
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select  # noqa: E402

from app.database import AsyncSessionLocal  # noqa: E402
from app.models.processed_alert import ProcessedAlert  # noqa: E402
from app.models.raw_item import RawItem  # noqa: E402
from app.models.source import Source  # noqa: E402


# Lowercase substrings — presence in title+summary suggests the alert is
# outside HiddenAlerts' fraud / financial-risk scope. Kept narrow on purpose:
# false positives are worse than false negatives because admins still review.
OFF_TOPIC_TERMS: tuple[str, ...] = (
    "child sexual abuse",
    "child sex",
    "csam",
    "child exploitation",
    "child abuse",
    "child pornography",
    "sex offender",
    "sex trafficking",
    "human trafficking",
    "terrorism",
    "terrorist",
    "domestic terrorism",
    "violent extremism",
    "weapons trafficking",
    "weapons charge",
    "explosives",
    "national security",
    "attack drones",
    "coup attempt",
    "military contractor",
    "energy facilities",
    "destruction of",
    "drug trafficking",
    "narcotics trafficking",
    "narcotics conspiracy",
    "fugitive",
    "murder",
    "homicide",
    "kidnap",
    "hostage",
    "bombing",
    "shooting",
    "sniper",
    "school shooting",
    "armed robbery",
    "violent crime",
    "irgc",
    "islamic revolutionary guard",
    "hamas",
    "hezbollah",
    "isis",
)

# If any of these appear, the alert is NOT flagged — there's a clear
# fraud / financial-risk mechanism even if an off-topic term also appears
# (e.g. an article about terrorism financing belongs in the feed).
POSITIVE_FRAUD_TERMS: tuple[str, ...] = (
    "fraud",
    "fraudulent",
    "scam",
    "laundering",
    "money laundering",
    "embezzle",
    "bribery",
    "kickback",
    "ponzi",
    "pyramid scheme",
    "wire fraud",
    "mail fraud",
    "bank fraud",
    "investment fraud",
    "securities fraud",
    "tax evasion",
    "tax fraud",
    "identity theft",
    "credit card",
    "insider trading",
    "market manipulation",
    "phishing",
    "ransomware",
    "extortion",
    "racketeering",
    "rico",
    "fcpa",
    "foreign corrupt practices",
    "ofac",
    "sanctions",
    "illicit finance",
    "shell company",
    "false claims",
    "ponzi",
    "medicare fraud",
    "medicaid fraud",
    "healthcare fraud",
    "investor harm",
    "market abuse",
    "money mule",
    "stolen funds",
    "blocked entit",
    "designated entit",
    "embezzlement",
    "swindl",
    "skimm",
    "spoofing",
    "wash trading",
    "rug pull",
)


def _evaluate(text: str) -> tuple[bool, list[str], list[str]]:
    """Return (is_flagged, off_topic_hits, fraud_hits)."""
    lower = text.lower()
    off = sorted({t for t in OFF_TOPIC_TERMS if t in lower})
    pos = sorted({t for t in POSITIVE_FRAUD_TERMS if t in lower})
    return (bool(off) and not pos, off, pos)


async def _fetch_published_alerts() -> list[tuple[ProcessedAlert, str | None, str | None, str | None]]:
    async with AsyncSessionLocal() as session:
        stmt = (
            select(ProcessedAlert, RawItem.title, Source.name, RawItem.item_url)
            .join(RawItem, ProcessedAlert.raw_item_id == RawItem.id)
            .join(Source, RawItem.source_id == Source.id)
            .where(ProcessedAlert.is_published.is_(True))
            .order_by(ProcessedAlert.id)
        )
        rows = (await session.execute(stmt)).all()
        return [(a, t, s, u) for a, t, s, u in rows]


def _flag(rows) -> list[dict]:
    flagged: list[dict] = []
    for alert, title, source_name, source_url in rows:
        text = " ".join(filter(None, [title or "", alert.summary or ""]))
        is_off, off_hits, pos_hits = _evaluate(text)
        if not is_off:
            continue
        flagged.append({
            "id": alert.id,
            "title": title,
            "category": alert.primary_category,
            "score": alert.signal_score_total,
            "source_name": source_name,
            "source_url": source_url,
            "off_topic_terms": off_hits,
            "summary_snippet": (alert.summary or "")[:200],
        })
    return flagged


def _print_report(flagged: list[dict]) -> None:
    if not flagged:
        print("No off-topic published alerts found. Feed is clean.")
        return
    print(f"Found {len(flagged)} off-topic published alert(s):\n")
    for entry in flagged:
        print(
            f"ID: {entry['id']} | "
            f"Category: {entry['category']} | "
            f"Score: {entry['score']}\n"
            f"Title: {entry['title']}\n"
            f"Source: {entry['source_name']}\n"
            f"URL: {entry['source_url']}\n"
            f"Off-topic terms: {', '.join(entry['off_topic_terms'])}\n"
            f"Snippet: {entry['summary_snippet']}\n"
            f"{'-' * 80}"
        )
    print(
        "\nTo unpublish specific alerts, re-run with --apply and --ids:\n"
        f"  python scripts/audit_offtopic_alerts.py --apply --ids "
        + " ".join(str(e["id"]) for e in flagged[:10])
    )


async def _apply_unpublish(ids: list[int]) -> None:
    async with AsyncSessionLocal() as session:
        stmt = select(ProcessedAlert).where(ProcessedAlert.id.in_(ids))
        alerts = (await session.execute(stmt)).scalars().all()
        found_ids: set[int] = set()
        for alert in alerts:
            found_ids.add(alert.id)
            if alert.is_published:
                alert.is_published = False
                alert.published_at = None
                print(f"Unpublished alert {alert.id}: {alert.summary[:80] if alert.summary else ''}…")
            else:
                print(f"Alert {alert.id} was already unpublished — no change")
        missing = set(ids) - found_ids
        if missing:
            print(f"WARNING: could not find IDs {sorted(missing)}")
        await session.commit()
        print(f"\nDone. Modified {len(found_ids)} alert(s).")


async def main(args: argparse.Namespace) -> None:
    if args.apply:
        if not args.ids:
            print(
                "Error: --apply requires --ids ID1 ID2 ...\n"
                "Run without --apply first to see what would be flagged.",
                file=sys.stderr,
            )
            sys.exit(2)
        await _apply_unpublish(args.ids)
        return

    rows = await _fetch_published_alerts()
    flagged = _flag(rows)

    if args.json:
        print(json.dumps(flagged, default=str, indent=2))
    else:
        _print_report(flagged)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Flag off-topic published alerts; optionally unpublish by ID.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output flagged alerts as JSON (default: human-readable report)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Unpublish the specified --ids (requires --ids)",
    )
    parser.add_argument(
        "--ids",
        type=int,
        nargs="+",
        help="Alert IDs to unpublish when --apply is set",
    )
    asyncio.run(main(parser.parse_args()))
