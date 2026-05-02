#!/usr/bin/env python3
"""Audit script to find and optionally unpublish weak 'Other' alerts.

Lists suspicious published alerts with id, title, category, risk, score, source,
source URL, and source_published_at.
Requires --apply and --ids to unpublish alerts.
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal
from app.models.processed_alert import ProcessedAlert
from app.models.raw_item import RawItem
from app.models.source import Source

ALLOWED_PUBLISH_CATEGORIES = {
    "Investment Fraud",
    "Cybercrime",
    "Consumer Scam",
    "Money Laundering",
    "Cryptocurrency Fraud",
}

async def run_audit(apply: bool, ids: list[int] | None) -> None:
    async with AsyncSessionLocal() as session:
        if apply and ids:
            print(f"Apply mode: Attempting to unpublish IDs: {ids}")
            stmt = select(ProcessedAlert).where(ProcessedAlert.id.in_(ids))
            result = await session.execute(stmt)
            alerts = result.scalars().all()
            
            found_ids = set()
            for alert in alerts:
                if alert.is_published:
                    alert.is_published = False
                    alert.published_at = None
                    print(f"Unpublished alert ID {alert.id}")
                else:
                    print(f"Alert ID {alert.id} was already unpublished")
                found_ids.add(alert.id)
            
            missing = set(ids) - found_ids
            if missing:
                print(f"Warning: Could not find IDs {missing}")
            
            await session.commit()
            print("Done applying changes.")
            return

        print("Running audit in Dry Run mode...\n")
        
        # List suspicious published alerts (categories not in ALLOWED_PUBLISH_CATEGORIES)
        stmt = (
            select(ProcessedAlert, RawItem.title, Source.name, RawItem.item_url, RawItem.fetched_at)
            .join(RawItem, ProcessedAlert.raw_item_id == RawItem.id)
            .join(Source, RawItem.source_id == Source.id)
            .where(
                ProcessedAlert.is_published == True,
                ProcessedAlert.primary_category.notin_(ALLOWED_PUBLISH_CATEGORIES)
            )
            .order_by(ProcessedAlert.id)
        )
        result = await session.execute(stmt)
        rows = result.all()
        
        print(f"Found {len(rows)} published alerts in suspicious categories (e.g., 'Other')\n")
        
        for alert, title, source_name, source_url, source_published_at in rows:
            print(
                f"ID: {alert.id} | "
                f"Category: {alert.primary_category} | "
                f"Risk: {alert.risk_level} | "
                f"Score: {alert.signal_score_total}\n"
                f"Title: {title}\n"
                f"Source: {source_name} | Published at: {source_published_at}\n"
                f"Source URL: {source_url}\n"
                f"{'-'*80}"
            )

        print("\nTo unpublish specific alerts, run this script with --apply and --ids:")
        print("python scripts/audit_public_alert_quality.py --apply --ids ID1 ID2 ...")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audit and unpublish weak alerts.")
    parser.add_argument("--apply", action="store_true", help="Actually unpublish the specified IDs")
    parser.add_argument("--ids", type=int, nargs="+", help="Specific alert IDs to unpublish")
    
    args = parser.parse_args()
    
    if args.apply and not args.ids:
        print("Error: --apply requires --ids to be specified.")
        print("Example: python scripts/audit_public_alert_quality.py --apply --ids 288 291")
        exit(1)
        
    asyncio.run(run_audit(args.apply, args.ids))
