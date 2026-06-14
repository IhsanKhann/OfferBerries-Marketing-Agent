"""D1: Tests for tool_generate_visual_brief and visual prompt assembly."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import main
from main import tool_generate_visual_brief, VisualBrief


MOCK_BRIEF = {
    "topic": "OfferBerries HR payroll",
    "trending_angles": ["Saves 3 days on payroll", "EOBI compliance"],
    "pain_points": ["Manual sheets"],
    "suggested_hooks": ["Stop wasting time on payroll"],
    "platform_notes": {},
}

MOCK_CONTENT = {
    "platform": "linkedin",
    "copy": "Pakistani SMBs: automate your payroll with OfferBerries. EOBI, Raast, CNIC — all covered.",
    "hashtags": ["#HR", "#Payroll"],
    "cta": "Book a demo",
}


def _make_mock_client(resp_text: str, prompt_tokens=200, completion_tokens=60):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": resp_text}}],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
    }
    mock_resp.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)
    return mock_client


# ── tool_generate_visual_brief ─────────────────────────────────────────────

class TestGenerateVisualBrief:
    @pytest.mark.asyncio
    async def test_returns_visual_brief_structure(self):
        resp_json = '{"headline": "Stop Wasting Payroll Days", "subtext": "OfferBerries automates it", "visual_mood": "professional clean trustworthy", "color_directive": "dominant indigo white text", "layout_hint": "announcement"}'

        mock_coll = MagicMock()
        mock_coll.insert_one = AsyncMock()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_coll)
        main.db = mock_db

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = _make_mock_client(resp_json)
            with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
                result = await tool_generate_visual_brief(
                    brief=MOCK_BRIEF,
                    content=MOCK_CONTENT,
                    platform="linkedin",
                )

        assert "headline" in result
        assert "visual_mood" in result
        assert "layout_hint" in result
        assert result["headline"] == "Stop Wasting Payroll Days"
        assert result["layout_hint"] == "announcement"

    @pytest.mark.asyncio
    async def test_falls_back_gracefully_on_invalid_json(self):
        mock_coll = MagicMock()
        mock_coll.insert_one = AsyncMock()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_coll)
        main.db = mock_db

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = _make_mock_client("This is not JSON")
            with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
                result = await tool_generate_visual_brief(
                    brief=MOCK_BRIEF, content=MOCK_CONTENT, platform="linkedin",
                )

        # Should fall back to VisualBrief defaults (not raise)
        assert "headline" in result
        assert "visual_mood" in result

    @pytest.mark.asyncio
    async def test_returns_default_brief_when_no_api_key(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}):
            result = await tool_generate_visual_brief(
                brief=MOCK_BRIEF, content=MOCK_CONTENT, platform="linkedin",
            )
        default = VisualBrief().model_dump()
        assert result == default

    @pytest.mark.asyncio
    async def test_logs_cost_to_tool_calls(self):
        mock_coll = MagicMock()
        mock_coll.insert_one = AsyncMock()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_coll)
        main.db = mock_db

        resp_json = '{"headline": "Automate Payroll", "subtext": "Save time", "visual_mood": "professional", "color_directive": "indigo", "layout_hint": "stat-card"}'
        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = _make_mock_client(resp_json, 300, 80)
            with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
                await tool_generate_visual_brief(
                    brief=MOCK_BRIEF, content=MOCK_CONTENT, platform="instagram",
                    run_id="run-999", tenant_id="tenant-111",
                )

        assert mock_coll.insert_one.called
        doc = mock_coll.insert_one.call_args[0][0]
        assert doc["tool_name"] == "generate_visual_brief"
        assert doc["run_id"] == "run-999"
        assert doc["prompt_tokens"] == 300
        assert doc["completion_tokens"] == 80
        assert doc["cost_usd"] > 0


# ── VisualBrief model ──────────────────────────────────────────────────────

class TestVisualBriefModel:
    def test_default_values(self):
        vb = VisualBrief()
        assert vb.visual_mood == "professional, clean"
        assert vb.layout_hint == "announcement"

    def test_all_fields_populated(self):
        vb = VisualBrief(
            headline="Save 3 Days on Payroll",
            subtext="OfferBerries makes it simple",
            visual_mood="bold energetic",
            color_directive="dominant indigo white text",
            layout_hint="stat-card",
        )
        assert vb.layout_hint == "stat-card"
        assert "indigo" in vb.color_directive

    def test_model_dump_round_trips(self):
        original = VisualBrief(headline="Test Headline", layout_hint="quote-card")
        restored = VisualBrief(**original.model_dump())
        assert restored.headline == original.headline
        assert restored.layout_hint == original.layout_hint
