import pytest


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
async def test_sources_list_returns_200(client):
    response = await client.get("/api/v1/sources")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_raw_items_list_returns_200(client):
    response = await client.get("/api/v1/raw-items")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_stats_returns_counts(client):
    response = await client.get("/api/v1/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_raw_items" in data
    assert "total_sources" in data
