import asyncio
from app.database import AsyncSessionLocal
from sqlalchemy import select
from app.models.processed_alert import ProcessedAlert

async def main():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(ProcessedAlert).limit(1))
        alert = result.scalar_one_or_none()
        
        def _to_display(alert: ProcessedAlert) -> dict:
            return {
                "id": alert.id,
            }
            
        d = _to_display(alert)
        print(d)

asyncio.run(main())
