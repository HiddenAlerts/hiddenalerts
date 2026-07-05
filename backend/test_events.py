import asyncio
from app.database import AsyncSessionLocal
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.event import Event, EventSource
from app.models.processed_alert import ProcessedAlert
from app.models.raw_item import RawItem

async def main():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Event)
            .options(
                selectinload(Event.event_sources)
                .selectinload(EventSource.alert)
                .selectinload(ProcessedAlert.raw_item)
                .selectinload(RawItem.source)
            )
            .limit(1)
        )
        event = result.scalar_one_or_none()
        if not event:
            print("No event found")
            return
            
        print(f"Event ID: {event.id}")
        alerts = []
        for es in event.event_sources:
            if es.alert:
                alerts.append(es.alert)
                
        for alert in alerts:
            print(f"Alert ID: {alert.id}, Title: {alert.raw_item.title if alert.raw_item else 'Untitled'}")

asyncio.run(main())
