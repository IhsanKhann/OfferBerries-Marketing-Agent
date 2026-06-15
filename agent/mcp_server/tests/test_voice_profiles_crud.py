"""C2: Tests for /voice-profiles CRUD endpoints."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

import main
from main import DEFAULT_VOICE_PROFILES, build_content_prompt, VoiceProfileDoc
from auth import TenantContext

OWNER_KEY = os.getenv("OWNER_API_KEY", "ofb_owner_test0000000000000000000000000000000")
AUTH_HEADERS = {"X-API-Key": OWNER_KEY}

TENANT = TenantContext(tenant_id="t-1", tier="pro", rate_limits={}, feature_flags=set())


def _make_coll(find_results=None, find_one_result=None):
    coll = MagicMock()
    coll.count_documents = AsyncMock(return_value=0)
    coll.insert_many = AsyncMock()
    coll.insert_one = AsyncMock()
    matched = MagicMock(); matched.matched_count = 1
    coll.update_one = AsyncMock(return_value=matched)
    coll.update_many = AsyncMock()
    coll.find_one = AsyncMock(return_value=find_one_result)
    _cur = MagicMock()
    _cur.to_list = AsyncMock(return_value=find_results or [])
    _cur.sort = MagicMock(return_value=_cur)
    coll.find = MagicMock(return_value=_cur)
    return coll


def _make_db(find_results=None, find_one_result=None):
    db = MagicMock()
    coll = _make_coll(find_results, find_one_result)
    db.__getitem__ = MagicMock(return_value=coll)
    return db, coll


# ── build_content_prompt ───────────────────────────────────────────────────

class TestBuildContentPrompt:
    def test_returns_tuple_of_two_strings(self):
        system, user = build_content_prompt(
            "payroll", [], [], [], "linkedin", "erp", None
        )
        assert isinstance(system, str)
        assert isinstance(user, str)

    def test_voice_system_prompt_used_when_set(self):
        voice = VoiceProfileDoc(
            name="Test", system_prompt="You are a robot writer.", hashtag_style="contextual", cta_type="contextual",
        )
        system, _ = build_content_prompt("payroll", [], [], [], "linkedin", "erp", voice)
        assert "robot writer" in system

    def test_default_system_prompt_when_no_voice(self):
        system, _ = build_content_prompt("payroll", [], [], [], "linkedin", "erp", None)
        assert "Pakistani SMBs" in system or "Tone:" in system or len(system) > 10

    def test_demo_cta_rule_in_user_prompt(self):
        voice = VoiceProfileDoc(name="Test", hashtag_style="contextual", cta_type="demo")
        _, user = build_content_prompt("payroll", [], [], [], "linkedin", "erp", voice)
        assert "demo" in user.lower() or "free trial" in user.lower()

    def test_branded_hashtag_style_in_user_prompt(self):
        voice = VoiceProfileDoc(name="Test", hashtag_style="branded", cta_type="contextual")
        _, user = build_content_prompt("payroll", [], [], [], "linkedin", "erp", voice)
        assert "OfferBerries" in user or "brand" in user.lower()

    def test_engagement_cta_promotes_questions(self):
        voice = VoiceProfileDoc(name="Test", hashtag_style="contextual", cta_type="engagement")
        _, user = build_content_prompt("payroll", [], [], [], "linkedin", "erp", voice)
        assert "question" in user.lower() or "engagement" in user.lower() or "comment" in user.lower()

    def test_user_prompt_contains_topic(self):
        _, user = build_content_prompt("HR automation", [], [], [], "linkedin", "erp", None)
        assert "HR automation" in user


# ── DEFAULT_VOICE_PROFILES ─────────────────────────────────────────────────

class TestDefaultVoiceProfiles:
    def test_exactly_two_defaults(self):
        assert len(DEFAULT_VOICE_PROFILES) == 2

    def test_one_is_default(self):
        defaults = [p for p in DEFAULT_VOICE_PROFILES if p["is_default"]]
        assert len(defaults) == 1

    def test_all_have_required_fields(self):
        for p in DEFAULT_VOICE_PROFILES:
            assert "name" in p
            assert "hashtag_style" in p
            assert "cta_type" in p


# ── GET /voice-profiles ───────────────────────────────────────────────────

class TestListVoiceProfiles:
    @pytest.mark.asyncio
    async def test_returns_profiles(self):
        profiles = [{"id": "p1", "name": "General", "is_default": True, "is_active": True, "tenant_id": "t-1"}]
        db, coll = _make_db(find_results=profiles)
        # First call (count_documents) returns 1 so no seeding
        coll.count_documents = AsyncMock(return_value=1)
        main.db = db
        with patch("main.get_tenant", return_value=TENANT):
            async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
                resp = await c.get("/voice-profiles", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    @pytest.mark.asyncio
    async def test_seeds_profiles_for_new_tenant(self):
        db, coll = _make_db(find_results=[])
        coll.count_documents = AsyncMock(return_value=0)
        main.db = db
        with patch("main.get_tenant", return_value=TENANT):
            async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
                await c.get("/voice-profiles", headers=AUTH_HEADERS)
        coll.insert_many.assert_called_once()

    @pytest.mark.asyncio
    async def test_requires_auth(self):
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
            resp = await c.get("/voice-profiles")
        assert resp.status_code == 401


# ── POST /voice-profiles ──────────────────────────────────────────────────

class TestCreateVoiceProfile:
    @pytest.mark.asyncio
    async def test_creates_profile_returns_201(self):
        db, coll = _make_db()
        main.db = db
        payload = {
            "name": "Startup Mode",
            "hashtag_style": "discovery",
            "cta_type": "learn_more",
            "tone": "casual",
        }
        with patch("main.get_tenant", return_value=TENANT):
            async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
                resp = await c.post("/voice-profiles", json=payload, headers=AUTH_HEADERS)
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Startup Mode"
        assert "id" in body

    @pytest.mark.asyncio
    async def test_rejects_invalid_hashtag_style(self):
        db, coll = _make_db()
        main.db = db
        payload = {"name": "Bad", "hashtag_style": "random", "cta_type": "demo"}
        with patch("main.get_tenant", return_value=TENANT):
            async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
                resp = await c.post("/voice-profiles", json=payload, headers=AUTH_HEADERS)
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_rejects_invalid_cta_type(self):
        db, coll = _make_db()
        main.db = db
        payload = {"name": "Bad", "hashtag_style": "contextual", "cta_type": "buy_now"}
        with patch("main.get_tenant", return_value=TENANT):
            async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
                resp = await c.post("/voice-profiles", json=payload, headers=AUTH_HEADERS)
        assert resp.status_code == 400


# ── PATCH /voice-profiles/{id}/set-default ────────────────────────────────

class TestSetDefaultVoiceProfile:
    @pytest.mark.asyncio
    async def test_sets_profile_as_default(self):
        existing = {"id": "p-1", "name": "Test", "is_active": True, "tenant_id": "t-1"}
        db, coll = _make_db(find_one_result=existing)
        main.db = db
        with patch("main.get_tenant", return_value=TENANT):
            async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
                resp = await c.patch("/voice-profiles/p-1/set-default", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["default_set"] is True
        assert body["id"] == "p-1"

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_profile(self):
        db, coll = _make_db(find_one_result=None)
        main.db = db
        with patch("main.get_tenant", return_value=TENANT):
            async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
                resp = await c.patch("/voice-profiles/ghost/set-default", headers=AUTH_HEADERS)
        assert resp.status_code == 404


# ── DELETE /voice-profiles/{id} ───────────────────────────────────────────

class TestDeleteVoiceProfile:
    @pytest.mark.asyncio
    async def test_soft_deletes_non_default_profile(self):
        existing = {"id": "p-2", "name": "Alt", "is_default": False, "tenant_id": "t-1"}
        db, coll = _make_db(find_one_result=existing)
        main.db = db
        with patch("main.get_tenant", return_value=TENANT):
            async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
                resp = await c.delete("/voice-profiles/p-2", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True
        coll.update_one.assert_called()

    @pytest.mark.asyncio
    async def test_cannot_delete_default_profile(self):
        existing = {"id": "p-1", "name": "General", "is_default": True, "tenant_id": "t-1"}
        db, coll = _make_db(find_one_result=existing)
        main.db = db
        with patch("main.get_tenant", return_value=TENANT):
            async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
                resp = await c.delete("/voice-profiles/p-1", headers=AUTH_HEADERS)
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_404_when_profile_not_found(self):
        db, coll = _make_db(find_one_result=None)
        main.db = db
        with patch("main.get_tenant", return_value=TENANT):
            async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as c:
                resp = await c.delete("/voice-profiles/ghost", headers=AUTH_HEADERS)
        assert resp.status_code == 404
