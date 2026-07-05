import asyncio
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal
from app.models.processed_alert import ProcessedAlert
from app.models.raw_item import RawItem
from app.models.source import Source

async def run_audit():
    async with AsyncSessionLocal() as session:
        # 1. number of published alerts
        published_alerts_count = await session.scalar(
            select(func.count(ProcessedAlert.id)).where(ProcessedAlert.is_published == True)
        )
        print(f"Number of published alerts: {published_alerts_count}")

        # 2. number of published alerts by category
        res = await session.execute(
            select(ProcessedAlert.primary_category, func.count(ProcessedAlert.id))
            .where(ProcessedAlert.is_published == True)
            .group_by(ProcessedAlert.primary_category)
        )
        categories = res.all()
        print(f"Published alerts by category:")
        for cat, count in categories:
            print(f"  {cat}: {count}")

        # 3. number of published alerts categorized as Other
        other_count = await session.scalar(
            select(func.count(ProcessedAlert.id)).where(
                ProcessedAlert.is_published == True,
                ProcessedAlert.primary_category == "Other"
            )
        )
        print(f"Number of published alerts categorized as Other: {other_count}")

        # 4. examples of weak or questionable published alerts
        # Look for Other + high score
        res = await session.execute(
            select(ProcessedAlert, RawItem.title, Source.name)
            .join(RawItem, ProcessedAlert.raw_item_id == RawItem.id)
            .join(Source, RawItem.source_id == Source.id)
            .where(
                ProcessedAlert.is_published == True,
                ProcessedAlert.primary_category == "Other"
            )
            .limit(10)
        )
        others = res.all()
        print("\nExamples of 'Other' published alerts:")
        for alert, title, source_name in others:
            print(f"ID: {alert.id} | Score: {alert.signal_score_total} | Source: {source_name} | Title: {title} | Matched: {alert.matched_keywords}")

if __name__ == "__main__":
    asyncio.run(run_audit())
