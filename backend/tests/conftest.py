import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.database import get_db
from app.main import app
from app.models.base import Base

# Stable test JWT secret — patched into settings at session scope
TEST_JWT_SECRET = "test-secret-key-32-chars-long-xx"

# Use SQLite for unit tests (no PostgreSQL needed)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


def _patch_jsonb_for_sqlite(target, connection, **kw):
    """Replace JSONB columns with JSON so SQLite can create the schema."""
    pass  # Handled via type_coerce at metadata level below


def _make_sqlite_compatible_metadata():
    """Swap JSONB → JSON in all model columns for SQLite compatibility.

    SQLite doesn't support PostgreSQL's JSONB type. We replace it with JSON
    (which aiosqlite supports) so the in-memory schema can be created.
    """
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, JSONB):
                column.type = JSON()
    return Base.metadata


@pytest.fixture(scope="session", autouse=True)
def patch_jwt_secret():
    """Patch JWT secret key for the entire test session so tokens are decodeable."""
    original = settings.jwt_secret_key
    settings.jwt_secret_key = TEST_JWT_SECRET
    yield
    settings.jwt_secret_key = original


@pytest_asyncio.fixture(scope="session")
async def engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    # Patch JSONB → JSON before creating tables
    metadata = _make_sqlite_compatible_metadata()
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(engine):
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
