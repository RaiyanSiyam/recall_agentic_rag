"""API tests verifying FastAPI endpoints and SSE streaming."""
import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.main import app


@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "data_mode" in data
        assert "mcp_servers" in data


@pytest.mark.asyncio
async def test_memory_endpoints():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Add fact
        resp = await client.post("/api/memory", json={"fact_text": "Project X = top priority", "category": "priority"})
        assert resp.status_code == 200
        fact_id = resp.json()["fact"]["id"]

        # 2. List facts
        resp = await client.get("/api/memory")
        assert resp.status_code == 200
        facts = resp.json()["facts"]
        assert any(f["id"] == fact_id for f in facts)

        # 3. Delete fact
        resp = await client.delete(f"/api/memory/{fact_id}")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_chat_sse_stream():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/chat",
            json={"query": "Summarize Project X", "session_id": "test-sess", "stream": True},
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

        content = resp.text
        assert "event: plan" in content
        assert "event: tool_result" in content
        assert "event: evidence" in content
        assert "event: token" in content
        assert "event: done" in content
