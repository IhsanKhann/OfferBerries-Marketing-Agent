"""D2: Tests for template upload + preview endpoints."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

import main
from auth import TenantContext

OWNER_KEY = os.getenv("OWNER_API_KEY", "ofb_owner_test0000000000000000000000000000000")
AUTH_HEADERS = {"X-API-Key": OWNER_KEY}
TENANT = TenantContext(tenant_id="t-1", tier="pro", rate_limits={}, feature_flags=set())


def _make_db():
    coll = MagicMock()
    coll.count_documents = AsyncMock(return_value=1)
    coll.insert_one = AsyncMock()
    coll.insert_many = AsyncMock()
    result = MagicMock(); result.matched_count = 1
    coll.update_one = AsyncMock(return_value=result)
    coll.find_one = AsyncMock(return_value=None)
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=coll)
    return db, coll


# ── POST /config/templates/upload ─────────────────────────────────────────

class TestTemplateUpload:
    @pytest.mark.asyncio
    async def test_upload_extracts_variables(self):
        db, coll = _make_db()
        main.db = db
        html = "<h1>{{headline}}</h1><p>{{subtext}}</p><div class='cta'>{{cta}}</div>"
        payload = {
            "template_id": "promo-v2",
            "name": "Promo V2",
            "platform": "linkedin",
            "html_content": html,
        }
        with patch("main.get_tenant", return_value=TENANT):
            async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
                resp = await c.post("/config/templates/upload", json=payload, headers=AUTH_HEADERS)
        assert resp.status_code == 201
        body = resp.json()
        assert body["saved"] is True
        assert set(body["variables"]) == {"headline", "subtext", "cta"}

    @pytest.mark.asyncio
    async def test_upload_deduplicates_variables(self):
        db, coll = _make_db()
        main.db = db
        html = "<p>{{name}} and {{name}} again {{title}}</p>"
        payload = {
            "template_id": "test-tpl",
            "name": "Test",
            "platform": "instagram",
            "html_content": html,
        }
        with patch("main.get_tenant", return_value=TENANT):
            async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
                resp = await c.post("/config/templates/upload", json=payload, headers=AUTH_HEADERS)
        body = resp.json()
        assert body["variables"].count("name") == 1
        assert "title" in body["variables"]

    @pytest.mark.asyncio
    async def test_upload_no_variables(self):
        db, coll = _make_db()
        main.db = db
        html = "<h1>Static Template</h1>"
        payload = {
            "template_id": "static-tpl",
            "name": "Static",
            "platform": "twitter",
            "html_content": html,
        }
        with patch("main.get_tenant", return_value=TENANT):
            async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
                resp = await c.post("/config/templates/upload", json=payload, headers=AUTH_HEADERS)
        assert resp.status_code == 201
        assert resp.json()["variables"] == []

    @pytest.mark.asyncio
    async def test_upload_persists_to_db(self):
        db, coll = _make_db()
        main.db = db
        payload = {
            "template_id": "promo-v3",
            "name": "Promo V3",
            "platform": "instagram",
            "html_content": "<div>{{copy}}</div>",
        }
        with patch("main.get_tenant", return_value=TENANT):
            async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
                await c.post("/config/templates/upload", json=payload, headers=AUTH_HEADERS)
        coll.update_one.assert_called_once()
        call_args = coll.update_one.call_args
        doc_set = call_args[0][1]["$set"]
        assert doc_set["html_content"] == "<div>{{copy}}</div>"
        assert "variables" in doc_set
        assert doc_set["tenant_id"] == "t-1"

    @pytest.mark.asyncio
    async def test_upload_missing_required_fields_422(self):
        db, coll = _make_db()
        main.db = db
        with patch("main.get_tenant", return_value=TENANT):
            async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
                resp = await c.post("/config/templates/upload", json={"name": "No ID"}, headers=AUTH_HEADERS)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_upload_requires_auth(self):
        payload = {"template_id": "test", "name": "Test", "platform": "linkedin", "html_content": "<p>hi</p>"}
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
            resp = await c.post("/config/templates/upload", json=payload)
        assert resp.status_code == 401


# ── POST /config/templates/{id}/preview ───────────────────────────────────

class TestTemplatePreview:
    @pytest.mark.asyncio
    async def test_preview_renders_and_returns_url(self):
        db, coll = _make_db()
        coll.find_one = AsyncMock(return_value={
            "template_id": "promo-v2",
            "html_content": "<h1>{{headline}}</h1>",
            "tenant_id": "t-1",
        })
        main.db = db

        mock_render_resp = MagicMock()
        mock_render_resp.status_code = 200
        mock_render_resp.headers = {"x-output-filename": "preview-abc.png"}

        with patch("main.get_tenant", return_value=TENANT):
            with patch("httpx.AsyncClient") as mock_cls:
                mock_http = AsyncMock()
                mock_http.__aenter__ = AsyncMock(return_value=mock_http)
                mock_http.__aexit__ = AsyncMock(return_value=False)
                mock_http.post = AsyncMock(return_value=mock_render_resp)
                mock_cls.return_value = mock_http

                async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
                    resp = await c.post(
                        "/config/templates/promo-v2/preview",
                        json={"headline": "Hello World"},
                        headers=AUTH_HEADERS,
                    )
        assert resp.status_code == 200
        body = resp.json()
        assert "preview_url" in body
        assert body["template_id"] == "promo-v2"

    @pytest.mark.asyncio
    async def test_preview_returns_404_for_unknown_template(self):
        db, coll = _make_db()
        coll.find_one = AsyncMock(return_value=None)
        main.db = db
        with patch("main.get_tenant", return_value=TENANT):
            async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
                resp = await c.post("/config/templates/ghost/preview", json={}, headers=AUTH_HEADERS)
        assert resp.status_code == 404
