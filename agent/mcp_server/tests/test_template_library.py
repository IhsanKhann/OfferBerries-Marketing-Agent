"""D2: Tests for /config/templates CRUD endpoints."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

import main
from main import DEFAULT_TEMPLATES
from auth import TenantContext


OWNER_KEY = os.getenv("OWNER_API_KEY", "ofb_owner_test0000000000000000000000000000000")
AUTH_HEADERS = {"X-API-Key": OWNER_KEY}

OWNER_TENANT = TenantContext(
    tenant_id="owner-tenant-test",
    tier="owner",
    rate_limits={},
    feature_flags=set(),
)


@pytest.fixture(autouse=True)
def patch_get_tenant():
    with patch("main.get_tenant", return_value=OWNER_TENANT):
        yield


@pytest.fixture
def mock_db():
    db = MagicMock()
    coll = MagicMock()
    coll.find_one = AsyncMock(return_value=None)
    coll.update_one = AsyncMock()
    coll.delete_one = AsyncMock()
    # find returns cursor with to_list
    coll.find = MagicMock(return_value=MagicMock(
        sort=MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
    ))
    db.__getitem__ = MagicMock(return_value=coll)
    return db, coll


# ── GET /config/templates ──────────────────────────────────────────────────

class TestGetTemplates:
    @pytest.mark.asyncio
    async def test_returns_default_templates_when_no_db_docs(self, mock_db):
        db, coll = mock_db
        main.db = db
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
            resp = await client.get("/config/templates", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        templates = resp.json()
        assert len(templates) == len(DEFAULT_TEMPLATES)
        ids = [t["template_id"] for t in templates]
        assert "linkedin-single" in ids
        assert "twitter-stat-card" in ids

    @pytest.mark.asyncio
    async def test_platform_filter_works(self, mock_db):
        db, coll = mock_db
        # Return empty list from DB to trigger default fallback
        main.db = db
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
            resp = await client.get("/config/templates?platform=linkedin", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        templates = resp.json()
        # Should only return linkedin + "all" platform templates
        for t in templates:
            assert t["platform"] in ("linkedin", "all"), f"Unexpected platform: {t['platform']}"

    @pytest.mark.asyncio
    async def test_returns_db_templates_when_available(self, mock_db):
        db, coll = mock_db
        db_templates = [
            {"template_id": "custom-card", "name": "Custom Card", "platform": "linkedin", "is_default": False},
        ]
        coll.find = MagicMock(return_value=MagicMock(
            sort=MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=db_templates)))
        ))
        main.db = db
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
            resp = await client.get("/config/templates", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()[0]["template_id"] == "custom-card"


# ── POST /config/templates ─────────────────────────────────────────────────

class TestCreateTemplate:
    @pytest.mark.asyncio
    async def test_create_template_returns_201(self, mock_db):
        db, coll = mock_db
        coll.update_one = AsyncMock()
        main.db = db
        payload = {
            "template_id": "promo-card",
            "name": "Promo Card",
            "platform": "instagram",
            "thumbnail_url": "https://example.com/promo.png",
            "is_default": False,
        }
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
            resp = await client.post("/config/templates", json=payload, headers=AUTH_HEADERS)
        assert resp.status_code == 201
        body = resp.json()
        assert body["saved"] is True
        assert body["template_id"] == "promo-card"
        coll.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_template_missing_required_fields_returns_422(self, mock_db):
        db, _ = mock_db
        main.db = db
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
            resp = await client.post("/config/templates", json={"name": "No ID"}, headers=AUTH_HEADERS)
        assert resp.status_code == 422


# ── PUT /config/templates/{id} ─────────────────────────────────────────────

class TestUpdateTemplate:
    @pytest.mark.asyncio
    async def test_update_existing_template(self, mock_db):
        db, coll = mock_db
        result = MagicMock()
        result.matched_count = 1
        coll.update_one = AsyncMock(return_value=result)
        main.db = db
        payload = {
            "template_id": "linkedin-single",
            "name": "LinkedIn Single v2",
            "platform": "linkedin",
        }
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
            resp = await client.put("/config/templates/linkedin-single", json=payload, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["saved"] is True

    @pytest.mark.asyncio
    async def test_update_nonexistent_template_returns_404(self, mock_db):
        db, coll = mock_db
        result = MagicMock()
        result.matched_count = 0
        coll.update_one = AsyncMock(return_value=result)
        main.db = db
        payload = {"template_id": "ghost-template", "name": "Ghost", "platform": "all"}
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
            resp = await client.put("/config/templates/ghost-template", json=payload, headers=AUTH_HEADERS)
        assert resp.status_code == 404


# ── DELETE /config/templates/{id} ─────────────────────────────────────────

class TestDeleteTemplate:
    @pytest.mark.asyncio
    async def test_delete_existing_template(self, mock_db):
        db, coll = mock_db
        result = MagicMock()
        result.deleted_count = 1
        coll.delete_one = AsyncMock(return_value=result)
        main.db = db
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
            resp = await client.delete("/config/templates/promo-card", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    @pytest.mark.asyncio
    async def test_delete_nonexistent_template_returns_404(self, mock_db):
        db, coll = mock_db
        result = MagicMock()
        result.deleted_count = 0
        coll.delete_one = AsyncMock(return_value=result)
        main.db = db
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
            resp = await client.delete("/config/templates/does-not-exist", headers=AUTH_HEADERS)
        assert resp.status_code == 404
