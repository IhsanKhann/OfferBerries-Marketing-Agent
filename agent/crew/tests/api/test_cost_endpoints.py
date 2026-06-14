"""Tests for GET /runs/{id}/cost and POST /runs/estimate endpoints."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

OWNER_KEY = os.getenv("OWNER_API_KEY", "ofb_owner_test0000000000000000000000000000000")
AUTH_HEADERS = {"X-API-Key": OWNER_KEY}


@pytest.fixture
def mock_db():
    db = MagicMock()
    coll = MagicMock()
    coll.insert_one = AsyncMock()
    coll.find_one = AsyncMock(return_value=None)
    coll.update_one = AsyncMock()
    coll.create_index = AsyncMock()
    coll.find = MagicMock(return_value=MagicMock(
        sort=MagicMock(return_value=MagicMock(
            limit=MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
        ))
    ))
    db.__getitem__ = MagicMock(return_value=coll)
    return db, coll


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
    db, _ = mock_db
    run_weekly.db = db
    run_weekly.redis_client = mock_redis
    return run_weekly.app


# ── GET /runs/{id}/cost ────────────────────────────────────────────────────

class TestGetRunCost:
    @pytest.mark.asyncio
    async def test_returns_cost_breakdown(self, app_with_mocks, mock_db):
        db, coll = mock_db
        agg_results = [
            {"_id": "research_trends", "total_cost": 0.0014, "calls": 1, "prompt_tokens": 0, "completion_tokens": 0},
            {"_id": "generate_content", "total_cost": 0.0009, "calls": 3, "prompt_tokens": 3000, "completion_tokens": 900},
        ]
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=agg_results)
        coll.aggregate = MagicMock(return_value=mock_cursor)
        db.__getitem__ = MagicMock(return_value=coll)

        async with AsyncClient(transport=ASGITransport(app=app_with_mocks), base_url="http://test") as client:
            resp = await client.get("/runs/run-abc-123/cost", headers=AUTH_HEADERS)

        assert resp.status_code == 200
        body = resp.json()
        assert body["run_id"] == "run-abc-123"
        assert body["total_usd"] == pytest.approx(0.0023, abs=1e-6)
        assert len(body["breakdown"]) == 2
        assert body["breakdown"][0]["_id"] == "research_trends"

    @pytest.mark.asyncio
    async def test_returns_zero_cost_for_unknown_run(self, app_with_mocks, mock_db):
        db, coll = mock_db
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=[])
        coll.aggregate = MagicMock(return_value=mock_cursor)
        db.__getitem__ = MagicMock(return_value=coll)

        async with AsyncClient(transport=ASGITransport(app=app_with_mocks), base_url="http://test") as client:
            resp = await client.get("/runs/nonexistent/cost", headers=AUTH_HEADERS)

        assert resp.status_code == 200
        body = resp.json()
        assert body["total_usd"] == 0.0
        assert body["breakdown"] == []

    @pytest.mark.asyncio
    async def test_requires_auth(self, app_with_mocks):
        async with AsyncClient(transport=ASGITransport(app=app_with_mocks), base_url="http://test") as client:
            resp = await client.get("/runs/run-123/cost")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_returns_503_when_db_unavailable(self, mock_redis):
        import run_weekly
        run_weekly.db = None
        run_weekly.redis_client = mock_redis
        async with AsyncClient(transport=ASGITransport(app=run_weekly.app), base_url="http://test") as client:
            resp = await client.get("/runs/run-123/cost", headers=AUTH_HEADERS)
        assert resp.status_code == 503


# ── POST /runs/estimate ────────────────────────────────────────────────────

class TestEstimateRunCost:
    @pytest.mark.asyncio
    async def test_estimate_with_defaults(self, app_with_mocks):
        async with AsyncClient(transport=ASGITransport(app=app_with_mocks), base_url="http://test") as client:
            resp = await client.post("/runs/estimate", json={}, headers=AUTH_HEADERS)

        assert resp.status_code == 200
        body = resp.json()
        assert "estimated_total_usd" in body
        assert "breakdown" in body
        assert body["research_model"] == "sonar"
        assert body["estimated_total_usd"] > 0

    @pytest.mark.asyncio
    async def test_deep_research_model_costs_more(self, app_with_mocks):
        async with AsyncClient(transport=ASGITransport(app=app_with_mocks), base_url="http://test") as client:
            sonar_resp = await client.post("/runs/estimate", json={"research_model": "sonar"}, headers=AUTH_HEADERS)
            deep_resp = await client.post("/runs/estimate", json={"research_model": "sonar-deep-research"}, headers=AUTH_HEADERS)

        sonar_cost = sonar_resp.json()["estimated_total_usd"]
        deep_cost = deep_resp.json()["estimated_total_usd"]
        assert deep_cost > sonar_cost

    @pytest.mark.asyncio
    async def test_more_platforms_means_higher_cost(self, app_with_mocks):
        async with AsyncClient(transport=ASGITransport(app=app_with_mocks), base_url="http://test") as client:
            one_platform = await client.post(
                "/runs/estimate", json={"platforms": ["linkedin"]}, headers=AUTH_HEADERS
            )
            three_platforms = await client.post(
                "/runs/estimate", json={"platforms": ["linkedin", "twitter", "instagram"]}, headers=AUTH_HEADERS
            )

        assert three_platforms.json()["estimated_total_usd"] > one_platform.json()["estimated_total_usd"]

    @pytest.mark.asyncio
    async def test_linkedin_includes_carousel_extra(self, app_with_mocks):
        """LinkedIn adds 4 carousel slide calls; non-LinkedIn platforms don't."""
        async with AsyncClient(transport=ASGITransport(app=app_with_mocks), base_url="http://test") as client:
            with_linkedin = await client.post(
                "/runs/estimate", json={"platforms": ["linkedin"]}, headers=AUTH_HEADERS
            )
            without_linkedin = await client.post(
                "/runs/estimate", json={"platforms": ["twitter"]}, headers=AUTH_HEADERS
            )

        li_breakdown = {b["tool"]: b for b in with_linkedin.json()["breakdown"]}
        tw_breakdown = {b["tool"]: b for b in without_linkedin.json()["breakdown"]}
        assert li_breakdown["generate_content"]["calls"] > tw_breakdown["generate_content"]["calls"]

    @pytest.mark.asyncio
    async def test_breakdown_contains_expected_tools(self, app_with_mocks):
        async with AsyncClient(transport=ASGITransport(app=app_with_mocks), base_url="http://test") as client:
            resp = await client.post("/runs/estimate", json={}, headers=AUTH_HEADERS)

        tools = {item["tool"] for item in resp.json()["breakdown"]}
        assert "research_trends" in tools
        assert "generate_content" in tools
        assert "generate_visual_brief" in tools

    @pytest.mark.asyncio
    async def test_requires_auth(self, app_with_mocks):
        async with AsyncClient(transport=ASGITransport(app=app_with_mocks), base_url="http://test") as client:
            resp = await client.post("/runs/estimate", json={})
        assert resp.status_code == 401
