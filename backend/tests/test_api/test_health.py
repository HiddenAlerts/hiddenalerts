import uuid

import pytest

from app.auth import create_access_token, hash_password
from app.models.user import User


async def _admin_headers(db_session) -> dict:
    user = User(
        email=f"admin_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password("pw"),
        is_active=True,
        role="admin",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"}


@pytest.mark.asyncio
async def test_health_returns_200(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_has_status_field(client):
    response = await client.get("/api/v1/health")
    data = response.json()
    assert "status" in data
    assert "database" in data


@pytest.mark.asyncio
async def test_sources_list_returns_200(client, db_session):
    headers = await _admin_headers(db_session)
    response = await client.get("/api/v1/sources", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_raw_items_list_returns_200(client, db_session):
    headers = await _admin_headers(db_session)
    response = await client.get("/api/v1/raw-items", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_stats_returns_counts(client, db_session):
    headers = await _admin_headers(db_session)
    response = await client.get("/api/v1/stats", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "total_raw_items" in data
    assert "total_sources" in data
