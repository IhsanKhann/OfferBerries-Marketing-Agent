"""C1: Tests for /config/research-model endpoints."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

import main
from auth import TenantContext


OWNER_KEY = os.getenv("OWNER_API_KEY", "ofb_owner_test0000000000000000000000000000000")
AUTH_HEADERS = {"X-API-Key": OWNER_KEY}

OWNER_TENANT = TenantContext(
    tenant_id="owner-tenant-test",
    tier="owner",
    rate_limits={"research_trends": 9999},
    feature_flags=set(),
)


@pytest.fixture
def mock_db():
    db = MagicMock()
    coll = MagicMock()
    coll.find_one = AsyncMock(return_value=None)
    coll.update_one = AsyncMock()
    db.__getitem__ = MagicMock(return_value=coll)
    return db, coll


@pytest.fixture(autouse=True)
def patch_get_tenant():
    with patch("main.get_tenant", return_value=OWNER_TENANT):
        yield


class TestGetResearchModel:
    @pytest.mark.asyncio
    async def test_returns_default_sonar_when_no_config(self, mock_db):
        db, coll = mock_db
        coll.find_one = AsyncMock(return_value=None)
        main.db = db
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
            resp = await client.get("/config/research-model", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["model_id"] == "sonar"

    @pytest.mark.asyncio
    async def test_returns_saved_model_from_db(self, mock_db):
        db, coll = mock_db
        coll.find_one = AsyncMock(return_value={"value": "sonar-pro"})
        main.db = db
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
            resp = await client.get("/config/research-model", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["model_id"] == "sonar-pro"


class TestPutResearchModel:
    @pytest.mark.asyncio
    async def test_save_valid_model(self, mock_db):
        db, coll = mock_db
        main.db = db
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
            resp = await client.put(
                "/config/research-model",
                json={"model_id": "sonar-deep-research"},
                headers=AUTH_HEADERS,
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["saved"] is True
        assert body["model_id"] == "sonar-deep-research"
        coll.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_reject_unknown_model(self, mock_db):
        db, _ = mock_db
        main.db = db
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
            resp = await client.put(
                "/config/research-model",
                json={"model_id": "gpt-99-ultra"},
                headers=AUTH_HEADERS,
            )
        assert resp.status_code == 400
        assert "Unknown research model" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_all_valid_perplexity_models_accepted(self, mock_db):
        db, _ = mock_db
        main.db = db
        valid_models = ["sonar", "sonar-pro", "sonar-deep-research", "sonar-reasoning"]
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
            for model in valid_models:
                resp = await client.put(
                    "/config/research-model",
                    json={"model_id": model},
                    headers=AUTH_HEADERS,
                )
                assert resp.status_code == 200, f"Expected 200 for model {model}"
