"""API contract tests for /runs endpoints — B1 requirement."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import asyncio
import json
import pytest
from unittest.mock import ANY, AsyncMock, MagicMock, patch

from httpx import AsyncClient, ASGITransport


# ── App setup ─────────────────────────────────────────────────────────────

@pytest.fixture
def mock_db():
    db = MagicMock()
    # insert_one
    db.__getitem__ = MagicMock(return_value=MagicMock(
        insert_one=AsyncMock(),
        find_one=AsyncMock(return_value=None),
        update_one=AsyncMock(),
        create_index=AsyncMock(),
        find=MagicMock(return_value=MagicMock(
            sort=MagicMock(return_value=MagicMock(
                limit=MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
            ))
        )),
    ))
    db.create_collection = AsyncMock()
    return db


@pytest.fixture
def mock_redis():
    r = AsyncMock()
    r.publish = AsyncMock()
    r.setex = AsyncMock()
    r.get = AsyncMock(return_value=None)
    return r


@pytest.fixture
def app_with_mocks(mock_db, mock_redis):
    import run_weekly
    run_weekly.db = mock_db
    run_weekly.redis_client = mock_redis
    return run_weekly.app


OWNER_KEY = os.getenv("OWNER_API_KEY", "ofb_owner_test0000000000000000000000000000000")
AUTH_HEADERS = {"X-API-Key": OWNER_KEY}


# ── POST /runs ─────────────────────────────────────────────────────────────

class TestCreateRun:
    @pytest.mark.asyncio
    async def test_create_run_returns_201(self, app_with_mocks, mock_db):
        import run_weekly
        mock_coll = MagicMock()
        mock_coll.insert_one = AsyncMock()
        mock_coll.create_index = AsyncMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_coll)

        mock_pool = AsyncMock()
        mock_pool.enqueue_job = AsyncMock()
        run_weekly.arq_pool = mock_pool

        async with AsyncClient(transport=ASGITransport(app=app_with_mocks), base_url="http://test") as client:
            resp = await client.post(
                "/runs",
                json={"topic": "payroll", "platforms": ["linkedin"]},
                headers=AUTH_HEADERS,
            )

        assert resp.status_code == 201
        body = resp.json()
        assert "run_id" in body
        assert body["status"] == "pending"

    @pytest.mark.asyncio
    async def test_create_run_requires_auth(self, app_with_mocks):
        async with AsyncClient(transport=ASGITransport(app=app_with_mocks), base_url="http://test") as client:
            resp = await client.post("/runs", json={"topic": "payroll", "platforms": ["linkedin"]})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_create_run_response_shape(self, app_with_mocks, mock_db):
        import run_weekly
        mock_coll = MagicMock()
        mock_coll.insert_one = AsyncMock()
        mock_coll.create_index = AsyncMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_coll)

        mock_pool = AsyncMock()
        mock_pool.enqueue_job = AsyncMock()
        run_weekly.arq_pool = mock_pool

        async with AsyncClient(transport=ASGITransport(app=app_with_mocks), base_url="http://test") as client:
            resp = await client.post(
                "/runs",
                json={
                    "topic": "HR compliance",
                    "platforms": ["linkedin", "instagram"],
                    "execution_mode": "controlled",
                },
                headers=AUTH_HEADERS,
            )

        assert resp.status_code == 201
        body = resp.json()
        assert "run_id" in body
        assert len(body["run_id"]) == 36  # UUID format


# ── GET /runs/{run_id} ────────────────────────────────────────────────────

class TestGetRun:
    @pytest.mark.asyncio
    async def test_get_run_returns_run(self, app_with_mocks, mock_db):
        from models import AgentRun
        run = AgentRun(tenant_id="owner-tenant-test", topic="payroll", platforms=["linkedin"])
        doc = run.to_mongo()
        doc["updated_at"] = None
        doc["created_at"] = None

        mock_coll = MagicMock()
        mock_coll.find_one = AsyncMock(return_value=doc)
        mock_coll.create_index = AsyncMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_coll)

        async with AsyncClient(transport=ASGITransport(app=app_with_mocks), base_url="http://test") as client:
            resp = await client.get(f"/runs/{run.id}", headers=AUTH_HEADERS)

        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == run.id
        assert body["topic"] == "payroll"
        assert "stages" in body

    @pytest.mark.asyncio
    async def test_get_run_not_found_returns_404(self, app_with_mocks, mock_db):
        mock_coll = MagicMock()
        mock_coll.find_one = AsyncMock(return_value=None)
        mock_coll.create_index = AsyncMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_coll)

        async with AsyncClient(transport=ASGITransport(app=app_with_mocks), base_url="http://test") as client:
            resp = await client.get("/runs/nonexistent-id", headers=AUTH_HEADERS)

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_run_requires_auth(self, app_with_mocks):
        async with AsyncClient(transport=ASGITransport(app=app_with_mocks), base_url="http://test") as client:
            resp = await client.get("/runs/some-id")
        assert resp.status_code == 401


# ── DELETE /runs/{run_id} ─────────────────────────────────────────────────

class TestCancelRun:
    @pytest.mark.asyncio
    async def test_cancel_run_returns_200(self, app_with_mocks, mock_db):
        mock_coll = MagicMock()
        mock_coll.update_one = AsyncMock()
        mock_coll.create_index = AsyncMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_coll)

        with patch("run_weekly.cancel_run", new_callable=AsyncMock) as mock_cancel:
            async with AsyncClient(transport=ASGITransport(app=app_with_mocks), base_url="http://test") as client:
                resp = await client.delete("/runs/test-run-id", headers=AUTH_HEADERS)

        assert resp.status_code == 200
        assert resp.json()["cancelled"] is True
        mock_cancel.assert_called_once_with(ANY, "test-run-id")
