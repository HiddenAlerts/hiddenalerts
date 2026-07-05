import asyncio
from app.database import AsyncSessionLocal
from sqlalchemy import select
from app.models.processed_alert import ProcessedAlert

async def main():
    async with AsyncSessionLocal() as session:
        stmt = select(ProcessedAlert).where(ProcessedAlert.risk_level == "medium")
        res = await session.execute(stmt)
        alerts = res.scalars().all()
        print(f"Total medium alerts from DB query: {len(alerts)}")

asyncio.run(main())
