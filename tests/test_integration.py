import pytest

@pytest.mark.asyncio
async def test_health_endpoint(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data

@pytest.mark.asyncio
async def test_instructions_endpoint(client):
    resp = await client.get("/instructions")
    assert resp.status_code == 200
    assert "AgentLens" in resp.text
    assert "LLM Instructions" in resp.text

@pytest.mark.asyncio
async def test_cache_clear_endpoint(client):
    resp = await client.get("/cache/clear")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "cache cleared"

@pytest.mark.asyncio
async def test_parse_missing_url(client):
    resp = await client.get("/parse")
    assert resp.status_code == 422  # FastAPI validation error

@pytest.mark.asyncio
async def test_parse_invalid_url(client):
    resp = await client.get("/parse", params={"url": "not-a-valid-url"})
    assert resp.status_code == 400

@pytest.mark.asyncio
async def test_parse_unsupported_scheme(client):
    resp = await client.get("/parse", params={"url": "ftp://files.example.com/data"})
    assert resp.status_code == 400

@pytest.mark.asyncio
async def test_agent_manifest_missing_url(client):
    resp = await client.get("/agent-manifest")
    assert resp.status_code == 422

@pytest.mark.asyncio
async def test_agent_manifest_invalid_url(client):
    resp = await client.get("/agent-manifest", params={"url": "not-valid"})
    assert resp.status_code == 400

@pytest.mark.asyncio
async def test_agent_manifest_unsupported_scheme(client):
    resp = await client.get("/agent-manifest", params={"url": "ftp://files.example.com"})
    assert resp.status_code == 400
