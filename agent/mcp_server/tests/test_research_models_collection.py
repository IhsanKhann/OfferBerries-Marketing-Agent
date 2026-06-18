"""C1: Tests for /research-models and /admin/research-models endpoints."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

import main
from constants import RESEARCH_MODELS_SEED, TIER_ORDER
from auth import TenantContext

OWNER_KEY = os.getenv("OWNER_API_KEY", "ofb_owner_test0000000000000000000000000000000")
AUTH_HEADERS = {"X-API-Key": OWNER_KEY}

PRO_TENANT = TenantContext(tenant_id="t-pro", tier="pro", rate_limits={}, feature_flags=set())
STARTER_TENANT = TenantContext(tenant_id="t-starter", tier="starter", rate_limits={}, feature_flags=set())
FREE_TENANT = TenantContext(tenant_id="t-free", tier="free", rate_limits={}, feature_flags=set())
OWNER_TENANT = TenantContext(tenant_id="t-owner", tier="owner", rate_limits={}, feature_flags=set())


def _make_mock_coll(docs=None):
    coll = MagicMock()
    coll.count_documents = AsyncMock(return_value=len(docs or []))
    coll.insert_many = AsyncMock()
    coll.insert_one = AsyncMock()
    coll.update_one = AsyncMock()
    _cursor = MagicMock()
    _cursor.to_list = AsyncMock(return_value=docs or [])
    coll.find = MagicMock(return_value=_cursor)
    result = MagicMock(); result.matched_count = 1
    coll.update_one = AsyncMock(return_value=result)
    return coll


def _make_mock_db(docs=None):
    db = MagicMock()
    coll = _make_mock_coll(docs)
    db.__getitem__ = MagicMock(return_value=coll)
    return db, coll


# ── RESEARCH_MODELS_SEED ───────────────────────────────────────────────────

class TestResearchModelsSeed:
    def test_seed_contains_three_models(self):
        assert len(RESEARCH_MODELS_SEED) == 3

    def test_sonar_is_free_tier(self):
        sonar = next(m for m in RESEARCH_MODELS_SEED if m["id"] == "sonar")
        assert sonar["tier_required"] == "free"

    def test_sonar_pro_is_starter_tier(self):
        sp = next(m for m in RESEARCH_MODELS_SEED if m["id"] == "sonar-pro")
        assert sp["tier_required"] == "starter"

    def test_deep_research_is_pro_tier(self):
        dr = next(m for m in RESEARCH_MODELS_SEED if m["id"] == "sonar-deep-research")
        assert dr["tier_required"] == "pro"

    def test_costs_are_increasing(self):
        costs = {m["id"]: m["cost_usd_per_call"] for m in RESEARCH_MODELS_SEED}
        assert costs["sonar"] < costs["sonar-pro"] < costs["sonar-deep-research"]


# ── TIER_ORDER ─────────────────────────────────────────────────────────────

class TestTierOrder:
    def test_free_is_lowest(self):
        assert TIER_ORDER["free"] < TIER_ORDER["starter"] < TIER_ORDER["pro"]

    def test_all_tiers_present(self):
        assert {"free", "starter", "pro"} == set(TIER_ORDER.keys())


# ── GET /research-models (user-facing, tier-filtered) ─────────────────────

class TestListResearchModels:
    @pytest.mark.asyncio
    async def test_pro_tenant_sees_all_models(self):
        db, coll = _make_mock_db(list(RESEARCH_MODELS_SEED))
        main.db = db
        with patch("main.get_tenant", return_value=PRO_TENANT):
            async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
                resp = await c.get("/research-models", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    @pytest.mark.asyncio
    async def test_free_tenant_only_sees_sonar(self):
        db, coll = _make_mock_db(list(RESEARCH_MODELS_SEED))
        main.db = db
        with patch("main.get_tenant", return_value=FREE_TENANT):
            async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
                resp = await c.get("/research-models", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        ids = [m["id"] for m in resp.json()]
        assert "sonar" in ids
        assert "sonar-pro" not in ids
        assert "sonar-deep-research" not in ids

    @pytest.mark.asyncio
    async def test_starter_tenant_sees_sonar_and_sonar_pro(self):
        db, coll = _make_mock_db(list(RESEARCH_MODELS_SEED))
        main.db = db
        with patch("main.get_tenant", return_value=STARTER_TENANT):
            async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
                resp = await c.get("/research-models", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        ids = [m["id"] for m in resp.json()]
        assert "sonar" in ids
        assert "sonar-pro" in ids
        assert "sonar-deep-research" not in ids

    @pytest.mark.asyncio
    async def test_owner_tenant_treated_as_pro(self):
        db, coll = _make_mock_db(list(RESEARCH_MODELS_SEED))
        main.db = db
        with patch("main.get_tenant", return_value=OWNER_TENANT):
            async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
                resp = await c.get("/research-models", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    @pytest.mark.asyncio
    async def test_falls_back_to_seed_when_db_empty(self):
        db, coll = _make_mock_db([])  # empty DB
        main.db = db
        with patch("main.get_tenant", return_value=PRO_TENANT):
            async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
                resp = await c.get("/research-models", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert len(resp.json()) == 3


# ── GET /admin/research-models ─────────────────────────────────────────────

class TestAdminListResearchModels:
    @pytest.mark.asyncio
    async def test_owner_sees_all_models(self):
        db, _ = _make_mock_db(list(RESEARCH_MODELS_SEED))
        main.db = db
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
            resp = await c.get("/admin/research-models", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    @pytest.mark.asyncio
    async def test_requires_owner_auth(self):
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
            resp = await c.get("/admin/research-models")
        assert resp.status_code == 401


# ── POST /admin/research-models ────────────────────────────────────────────

class TestAdminCreateResearchModel:
    @pytest.mark.asyncio
    async def test_creates_new_model(self):
        db, _ = _make_mock_db()
        main.db = db
        payload = {
            "id": "sonar-reasoning", "display_name": "Sonar Reasoning",
            "cost_usd_per_call": 0.005, "credits_per_call": 5,
            "tier_required": "starter", "is_active": True,
        }
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
            resp = await c.post("/admin/research-models", json=payload, headers=AUTH_HEADERS)
        assert resp.status_code == 201
        assert resp.json()["id"] == "sonar-reasoning"

    @pytest.mark.asyncio
    async def test_rejects_invalid_tier(self):
        db, _ = _make_mock_db()
        main.db = db
        payload = {
            "id": "test-model", "display_name": "Test",
            "cost_usd_per_call": 0.001, "credits_per_call": 1,
            "tier_required": "enterprise",
        }
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
            resp = await c.post("/admin/research-models", json=payload, headers=AUTH_HEADERS)
        assert resp.status_code == 400


# ── PATCH /admin/research-models/{id} ─────────────────────────────────────

class TestAdminPatchResearchModel:
    @pytest.mark.asyncio
    async def test_patch_updates_field(self):
        db, coll = _make_mock_db()
        main.db = db
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
            resp = await c.patch("/admin/research-models/sonar", json={"is_active": False}, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["updated"] is True

    @pytest.mark.asyncio
    async def test_patch_404_for_unknown_model(self):
        db, coll = _make_mock_db()
        no_match = MagicMock(); no_match.matched_count = 0
        coll.update_one = AsyncMock(return_value=no_match)
        main.db = db
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
            resp = await c.patch("/admin/research-models/ghost", json={"is_active": False}, headers=AUTH_HEADERS)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_patch_rejects_invalid_tier(self):
        db, _ = _make_mock_db()
        main.db = db
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
            resp = await c.patch("/admin/research-models/sonar", json={"tier_required": "vip"}, headers=AUTH_HEADERS)
        assert resp.status_code == 400
