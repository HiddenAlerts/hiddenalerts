"""
Quick test script — runs the AI pipeline on 5 unprocessed items only.

Usage (from project root, with HiddenAlerts conda env active):
    python run_pipeline_test.py

Prints a summary of what happened to each item.
"""
import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)

from app.database import AsyncSessionLocal
from app.pipeline.alert_pipeline import process_unprocessed_items


import argparse
import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)

from app.database import AsyncSessionLocal
from app.pipeline.alert_pipeline import process_unprocessed_items


async def main(limit: int) -> None:
    print(f"\n=== HiddenAlerts — Pipeline Test ({limit} items) ===\n")
    async with AsyncSessionLocal() as session:
        stats = await process_unprocessed_items(session, limit=limit)

    print("\n=== Results ===")
    print(f"  Items examined       : {stats.items_examined}")
    print(f"  Processed (relevant) : {stats.items_processed}")
    print(f"  Skipped (no keywords): {stats.items_skipped_no_keywords}")
    print(f"  Skipped (AI said no) : {stats.items_skipped_ai_irrelevant}")
    print(f"  Failed               : {stats.items_failed}")
    if stats.errors:
        print("\n === Errors ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5, help="Number of items to test")
    args = parser.parse_args()
    asyncio.run(main(args.limit))

# python run_pipeline_test.py --limit 5