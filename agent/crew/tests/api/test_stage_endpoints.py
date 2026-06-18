"""API contract tests for /runs/{id}/stage/* endpoints — B1 requirement."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from unittest.mock import ANY, AsyncMock, MagicMock, patch

from httpx import AsyncClient, ASGITransport


OWNER_KEY = os.getenv("OWNER_API_KEY", "ofb_owner_test0000000000000000000000000000000")
AUTH_HEADERS = {"X-API-Key": OWNER_KEY}


@pytest.fixture
def mock_paused_run_doc():
    from models import AgentRun, StageStatus
    run = AgentRun(
        tenant_id="owner-tenant-test",
        topic="payroll",
        platforms=["linkedin"],
        execution_mode="controlled",
        overall_status="paused_for_review",
    )
    doc = run.to_mongo()
    doc["id"] = str(doc["_id"])
    doc["created_at"] = None
    doc["updated_at"] = None
    doc["stages"]["research"]["status"] = StageStatus.PAUSED.value
    doc["stages"]["research"]["output"] = {
        "topic": "payroll",
        "trending_angles": ["EOBI compliance", "Payroll automation"],
    }
    return doc


@pytest.fixture
def mock_db(mock_paused_run_doc):
    db = MagicMock()
    mock_coll = MagicMock()
    mock_coll.find_one = AsyncMock(return_value=mock_paused_run_doc)
    mock_coll.update_one = AsyncMock()
    mock_coll.create_index = AsyncMock()
    db.__getitem__ = MagicMock(return_value=mock_coll)
    return db


@pytest.fixture
def mock_redis():
    r = AsyncMock()
    r.publish = AsyncMock()
    return r


@pytest.fixture
def app_with_mocks(mock_db, mock_redis):
    import run_weekly
    run_weekly.db = mock_db
    run_weekly.redis_client = mock_redis
    return run_weekly.app


# ── GET /runs/{id}/stage/{stage} ───────────────────────────────────────────

class TestGetStageOutput:
    @pytest.mark.asyncio
    async def test_returns_stage_output(self, app_with_mocks):
        async with AsyncClient(transport=ASGITransport(app=app_with_mocks), base_url="http://test") as client:
            resp = await client.get("/runs/test-run/stage/research", headers=AUTH_HEADERS)

        assert resp.status_code == 200
        body = resp.json()
        assert body["stage"] == "research"
        assert body["run_id"] == "test-run"

    @pytest.mark.asyncio
    async def test_unknown_stage_returns_400(self, app_with_mocks):
        async with AsyncClient(transport=ASGITransport(app=app_with_mocks), base_url="http://test") as client:
            resp = await client.get("/runs/test-run/stage/unknown_stage", headers=AUTH_HEADERS)
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_requires_auth(self, app_with_mocks):
        async with AsyncClient(transport=ASGITransport(app=app_with_mocks), base_url="http://test") as client:
            resp = await client.get("/runs/test-run/stage/research")
        assert resp.status_code == 401


# ── POST /runs/{id}/stage/{stage}/approve ─────────────────────────────────

class TestApproveStage:
    @pytest.mark.asyncio
    async def test_approve_paused_stage(self, app_with_mocks):
        with patch("run_weekly.signal_resume", return_value=True) as mock_resume:
            async with AsyncClient(transport=ASGITransport(app=app_with_mocks), base_url="http://test") as client:
                resp = await client.post(
                    "/runs/test-run/stage/research/approve",
                    json={"edited_output": None},
                    headers=AUTH_HEADERS,
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["approved"] is True
        mock_resume.assert_called_once_with(ANY, "test-run", "research", edited_output=None)

    @pytest.mark.asyncio
    async def test_approve_with_edited_output(self, app_with_mocks):
        edited = {"topic": "payroll", "trending_angles": ["Custom trend"]}
        with patch("run_weekly.signal_resume", return_value=True):
            async with AsyncClient(transport=ASGITransport(app=app_with_mocks), base_url="http://test") as client:
                resp = await client.post(
                    "/runs/test-run/stage/research/approve",
                    json={"edited_output": edited},
                    headers=AUTH_HEADERS,
                )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_approve_already_approved_is_idempotent(self, app_with_mocks, mock_db):
        from models import StageStatus
        doc = (await mock_db["agent_runs"].find_one("test-run")).copy()
        doc["stages"]["research"]["status"] = StageStatus.APPROVED.value
        mock_db.__getitem__.return_value.find_one = AsyncMock(return_value=doc)

        with patch("run_weekly.signal_resume") as mock_resume:
            async with AsyncClient(transport=ASGITransport(app=app_with_mocks), base_url="http://test") as client:
                resp = await client.post(
                    "/runs/test-run/stage/research/approve",
                    json={"edited_output": None},
                    headers=AUTH_HEADERS,
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body.get("idempotent") is True
        mock_resume.assert_not_called()

    @pytest.mark.asyncio
    async def test_approve_non_paused_stage_returns_409(self, app_with_mocks, mock_db):
        from models import StageStatus
        doc = (await mock_db["agent_runs"].find_one("test-run")).copy()
        doc["stages"]["research"]["status"] = StageStatus.RUNNING.value
        mock_db.__getitem__.return_value.find_one = AsyncMock(return_value=doc)

        async with AsyncClient(transport=ASGITransport(app=app_with_mocks), base_url="http://test") as client:
            resp = await client.post(
                "/runs/test-run/stage/research/approve",
                json={"edited_output": None},
                headers=AUTH_HEADERS,
            )
        assert resp.status_code == 409


# ── POST /runs/{id}/stage/{stage}/edit ────────────────────────────────────

class TestEditStage:
    @pytest.mark.asyncio
    async def test_edit_stage_calls_signal_resume_with_output(self, app_with_mocks):
        edited = {"topic": "payroll", "trending_angles": ["EOBI deadline approaching"]}
        with patch("run_weekly.signal_resume", return_value=True) as mock_resume:
            async with AsyncClient(transport=ASGITransport(app=app_with_mocks), base_url="http://test") as client:
                resp = await client.post(
                    "/runs/test-run/stage/research/edit",
                    json={"output": edited},
                    headers=AUTH_HEADERS,
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["edited"] is True
        mock_resume.assert_called_once_with(ANY, "test-run", "research", edited_output=edited)


# ── POST /runs/{id}/stage/{stage}/reject ──────────────────────────────────

class TestRejectStage:
    @pytest.mark.asyncio
    async def test_reject_starts_rerun(self, app_with_mocks):
        import run_weekly
        mock_pool = AsyncMock()
        mock_pool.enqueue_job = AsyncMock()
        run_weekly.arq_pool = mock_pool

        async with AsyncClient(transport=ASGITransport(app=app_with_mocks), base_url="http://test") as client:
            resp = await client.post(
                "/runs/test-run/stage/research/reject",
                headers=AUTH_HEADERS,
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["rejected"] is True
        assert body["stage"] == "research"
        mock_pool.enqueue_job.assert_called_once_with("rerun_stage_job", "test-run", "research")

    @pytest.mark.asyncio
    async def test_reject_unknown_stage_returns_400(self, app_with_mocks):
        async with AsyncClient(transport=ASGITransport(app=app_with_mocks), base_url="http://test") as client:
            resp = await client.post(
                "/runs/test-run/stage/nonexistent/reject",
                headers=AUTH_HEADERS,
            )
        assert resp.status_code == 400


# ── POST /runs/{id}/resume ────────────────────────────────────────────────

class TestResumeRun:
    @pytest.mark.asyncio
    async def test_resume_signals_current_stage(self, app_with_mocks):
        with patch("run_weekly.signal_resume", return_value=True) as mock_resume:
            async with AsyncClient(transport=ASGITransport(app=app_with_mocks), base_url="http://test") as client:
                resp = await client.post("/runs/test-run/resume", headers=AUTH_HEADERS)

        assert resp.status_code == 200
        body = resp.json()
        assert body["resumed"] is True
