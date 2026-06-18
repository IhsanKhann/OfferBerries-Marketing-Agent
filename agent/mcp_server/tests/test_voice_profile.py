"""C2: Tests for /config/voice-profile endpoints and VoiceProfile model."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

import main
from schemas import VoiceProfile
from auth import TenantContext


OWNER_KEY = os.getenv("OWNER_API_KEY", "ofb_owner_test0000000000000000000000000000000")
AUTH_HEADERS = {"X-API-Key": OWNER_KEY}

OWNER_TENANT = TenantContext(
    tenant_id="owner-tenant-test",
    tier="owner",
    rate_limits={},
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


# ── Model unit tests ───────────────────────────────────────────────────────

class TestVoiceProfileModel:
    def test_default_tone_is_professional(self):
        vp = VoiceProfile()
        assert vp.tone == "professional"

    def test_all_fields_present(self):
        vp = VoiceProfile(
            tone="bold",
            personality="energetic and direct",
            writing_style="short punchy sentences",
            avoid_phrases=["synergy", "leverage"],
            platform_overrides={"twitter": "casual"},
            example_ctas=["Book a demo", "Try free"],
        )
        assert vp.tone == "bold"
        assert "synergy" in vp.avoid_phrases
        assert vp.platform_overrides["twitter"] == "casual"
        assert len(vp.example_ctas) == 2

    def test_model_dump_round_trips(self):
        original = VoiceProfile(tone="witty", personality="friendly", avoid_phrases=["lorem"])
        dumped = original.model_dump()
        restored = VoiceProfile(**dumped)
        assert restored.tone == original.tone
        assert restored.avoid_phrases == original.avoid_phrases


# ── GET /config/voice-profile ──────────────────────────────────────────────

class TestGetVoiceProfile:
    @pytest.mark.asyncio
    async def test_returns_default_when_no_config(self, mock_db):
        db, coll = mock_db
        coll.find_one = AsyncMock(return_value=None)
        main.db = db
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
            resp = await client.get("/config/voice-profile", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["tone"] == "professional"
        assert "avoid_phrases" in body
        assert isinstance(body["platform_overrides"], dict)

    @pytest.mark.asyncio
    async def test_returns_saved_profile(self, mock_db):
        db, coll = mock_db
        saved = VoiceProfile(tone="bold", personality="direct", avoid_phrases=["lorem"]).model_dump()
        coll.find_one = AsyncMock(return_value={"value": saved})
        main.db = db
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
            resp = await client.get("/config/voice-profile", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["tone"] == "bold"
        assert "lorem" in body["avoid_phrases"]

    @pytest.mark.asyncio
    async def test_falls_back_to_default_on_corrupt_config(self, mock_db):
        db, coll = mock_db
        coll.find_one = AsyncMock(return_value={"value": "not-a-dict"})
        main.db = db
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
            resp = await client.get("/config/voice-profile", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        # Should return defaults, not 500
        assert resp.json()["tone"] == "professional"


# ── PUT /config/voice-profile ──────────────────────────────────────────────

class TestPutVoiceProfile:
    @pytest.mark.asyncio
    async def test_save_voice_profile(self, mock_db):
        db, coll = mock_db
        main.db = db
        payload = {
            "tone": "bold",
            "personality": "direct and energetic",
            "writing_style": "short sentences with impact",
            "avoid_phrases": ["synergy"],
            "platform_overrides": {"twitter": "casual"},
            "example_ctas": ["Get started free"],
        }
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
            resp = await client.put("/config/voice-profile", json=payload, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["saved"] is True
        coll.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_minimal_profile(self, mock_db):
        db, coll = mock_db
        main.db = db
        async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://test") as client:
            resp = await client.put("/config/voice-profile", json={}, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["saved"] is True
