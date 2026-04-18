from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.raw_item import RawItem


async def get_known_url_hashes(session: AsyncSession, url_hashes: set[str]) -> set[str]:
    """Batch check: return the subset of url_hashes that already exist in raw_items.

    Used for pre-filtering stubs before fetching full articles — avoids N individual
    round-trips by doing a single IN query.
    """
    if not url_hashes:
        return set()
    result = await session.execute(
        select(RawItem.url_hash).where(RawItem.url_hash.in_(url_hashes))
    )
    return set(result.scalars().all())


async def is_url_duplicate(session: AsyncSession, url_hash: str) -> bool:
    """Return True if a RawItem with this url_hash already exists."""
    result = await session.execute(
        select(RawItem.id).where(RawItem.url_hash == url_hash).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def is_content_duplicate(session: AsyncSession, content_hash: str) -> bool:
    """Return True if a RawItem with this content_hash already exists."""
    if not content_hash:
        return False
    result = await session.execute(
        select(RawItem.id).where(RawItem.content_hash == content_hash).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def is_duplicate(session: AsyncSession, url_hash: str, content_hash: str) -> bool:
    """Return True if this item is a duplicate by URL or content."""
    if await is_url_duplicate(session, url_hash):
        return True
    if content_hash and await is_content_duplicate(session, content_hash):
        return True
    return False
