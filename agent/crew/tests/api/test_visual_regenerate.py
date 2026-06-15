"""D3: Tests for POST /runs/{run_id}/visual/regenerate endpoint."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

OWNER_KEY = os.getenv("OWNER_API_KEY", "ofb_owner_test0000000000000000000000000000000")
AUTH_HEADERS = {"X-API-Key": OWNER_KEY}


def _make_db(run_doc=None):
    db = MagicMock()
    coll = MagicMock()
    coll.find_one = AsyncMock(return_value=run_doc)
    res = MagicMock(); res.matched_count = 1
    coll.update_one = AsyncMock(return_value=res)
    coll.create_index = AsyncMock()
    coll.find = MagicMock(return_value=MagicMock(
        sort=MagicMock(return_value=MagicMock(
            limit=MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
        ))
    ))
    db.__getitem__ = MagicMock(return_value=coll)
    return db, coll


def _make_redis():
    r = AsyncMock()
    r.setex = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.publish = AsyncMock()
    return r


RUN_DOC = {
    "_id": "run-abc",
    "state_snapshot": {
        "platform_content": {
            "linkedin": {"platform": "linkedin", "copy": "Test copy", "hashtags": [], "cta": "CTA"},
        },
        "visual_assets": {},
        "visual_briefs": {
            "linkedin": {"headline": "Test", "subtext": "Sub", "visual_mood": "clean", "layout_hint": "card"},
        },
    },
}

MOCK_VISUAL_RESULT = {
    "url": "https://renderer/output/new-visual.png",
    "path": "/app/output/new-visual.png",
    "format": "png",
    "width": 1080,
    "height": 1080,
    "source": "fal",
}


@pytest.fixture
def app_with_mocks():
    import run_weekly
    db, _ = _make_db(run_doc=RUN_DOC)
    run_weekly.db = db
    run_weekly.redis_client = _make_redis()
    return run_weekly.app, db


class TestRegenerateVisual:
    @pytest.mark.asyncio
    async def test_returns_visual_url(self, app_with_mocks):
        app, db = app_with_mocks
        with patch("run_weekly._mcp_call", new_callable=AsyncMock, return_value=MOCK_VISUAL_RESULT):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post(
                    "/runs/run-abc/visual/regenerate",
                    json={"platform": "linkedin", "source": "fal"},
                    headers=AUTH_HEADERS,
                )
        assert resp.status_code == 200
        body = resp.json()
        assert body["visual_url"] == MOCK_VISUAL_RESULT["url"]
        assert body["platform"] == "linkedin"

    @pytest.mark.asyncio
    async def test_history_entry_in_response(self, app_with_mocks):
        app, db = app_with_mocks
        with patch("run_weekly._mcp_call", new_callable=AsyncMock, return_value=MOCK_VISUAL_RESULT):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post(
                    "/runs/run-abc/visual/regenerate",
                    json={"platform": "linkedin", "additional_instructions": "make it brighter"},
                    headers=AUTH_HEADERS,
                )
        body = resp.json()
        assert "history_entry" in body
        assert body["history_entry"]["instructions"] == "make it brighter"
        assert body["history_entry"]["platform"] == "linkedin"

    @pytest.mark.asyncio
    async def test_updates_run_doc_in_db(self, app_with_mocks):
        app, db = app_with_mocks
        _, coll = _make_db(run_doc=RUN_DOC)
        db.__getitem__ = MagicMock(return_value=coll)
        import run_weekly
        run_weekly.db = db
        with patch("run_weekly._mcp_call", new_callable=AsyncMock, return_value=MOCK_VISUAL_RESULT):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                await c.post(
                    "/runs/run-abc/visual/regenerate",
                    json={"platform": "linkedin"},
                    headers=AUTH_HEADERS,
                )
        coll.update_one.assert_called()

    @pytest.mark.asyncio
    async def test_returns_404_when_run_not_found(self, app_with_mocks):
        app, db = app_with_mocks
        import run_weekly
        _, no_run_coll = _make_db(run_doc=None)
        db.__getitem__ = MagicMock(return_value=no_run_coll)
        run_weekly.db = db
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                "/runs/nonexistent/visual/regenerate",
                json={"platform": "linkedin"},
                headers=AUTH_HEADERS,
            )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_404_when_platform_has_no_content(self, app_with_mocks):
        app, db = app_with_mocks
        import run_weekly
        run_weekly.db = db
        with patch("run_weekly._mcp_call", new_callable=AsyncMock, return_value=MOCK_VISUAL_RESULT):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post(
                    "/runs/run-abc/visual/regenerate",
                    json={"platform": "twitter"},  # not in RUN_DOC
                    headers=AUTH_HEADERS,
                )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_503_when_db_not_available(self):
        import run_weekly
        run_weekly.db = None
        run_weekly.redis_client = _make_redis()
        async with AsyncClient(transport=ASGITransport(app=run_weekly.app), base_url="http://test") as c:
            resp = await c.post(
                "/runs/run-abc/visual/regenerate",
                json={"platform": "linkedin"},
                headers=AUTH_HEADERS,
            )
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_requires_auth(self, app_with_mocks):
        app, _ = app_with_mocks
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/runs/run-abc/visual/regenerate", json={"platform": "linkedin"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_mcp_failure_returns_502(self, app_with_mocks):
        app, db = app_with_mocks
        import run_weekly
        run_weekly.db = db
        with patch("run_weekly._mcp_call", new_callable=AsyncMock, side_effect=Exception("MCP down")):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post(
                    "/runs/run-abc/visual/regenerate",
                    json={"platform": "linkedin"},
                    headers=AUTH_HEADERS,
                )
        assert resp.status_code == 502
