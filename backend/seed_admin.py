import asyncio
from app.auth import hash_password
from app.database import AsyncSessionLocal
from app.models.user import User

async def seed():
    async with AsyncSessionLocal() as s:
        user = User(
            email="admin@hiddenalerts.com",
            password_hash=hash_password("admin123"),
            is_active=True,
        )
        s.add(user)
        await s.commit()
        print("Done — admin user created")

asyncio.run(seed())
