"""Tests for MCP tool implementations."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from main import (
    tool_research_trends,
    tool_generate_content,
    tool_generate_visual,
    tool_queue_post,
    tool_get_analytics,
    ResearchBrief,
    PlatformContent,
)


MOCK_PERPLEXITY_RESP = {
    "choices": [{"message": {"content": "- Payroll automation saves 3 days\n- EOBI compliance challenges\n- Manual sheets cause errors\n- WhatsApp payslip distribution\n- JazzCash integration demand"}}]
}

MOCK_OPENROUTER_RESP = {
    "choices": [{"message": {"content": "Pakistani SMBs: stop wasting 3 days on payroll every month. OfferBerries HR module automates it all — EOBI, CNIC verification, Raast payments. Starting at PKR 1,999/month. What's your biggest payroll challenge right now?"}}]
}

MOCK_RENDERER_RESP_HEADERS = {"x-output-filename": "test-abc123.png"}


@pytest.mark.asyncio
async def test_research_trends_returns_brief():
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_PERPLEXITY_RESP
        mock_resp.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        with patch.dict(os.environ, {"PERPLEXITY_API_KEY": "test_key"}):
            result = await tool_research_trends("payroll software", "linkedin")

    assert "trending_angles" in result
    assert len(result["trending_angles"]) > 0
    assert result["topic"] == "payroll software"


@pytest.mark.asyncio
async def test_generate_content_linkedin_under_char_limit():
    brief = ResearchBrief(
        topic="payroll automation",
        trending_angles=["Saves time", "EOBI compliance"],
        pain_points=["Manual sheets"],
        suggested_hooks=["Stop wasting 3 days on payroll"],
        platform_notes={},
    )
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_OPENROUTER_RESP
        mock_resp.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test_key"}):
            result = await tool_generate_content(brief=brief, platform="linkedin")

    assert "copy" in result
    assert len(result["copy"]) <= 1300
    assert len(result["copy"]) > 0


@pytest.mark.asyncio
async def test_generate_visual_template_returns_png():
    content = PlatformContent(
        platform="linkedin",
        copy="Test post content for OfferBerries",
        hashtags=["#test"],
        cta="Learn more",
        estimated_reading_time=1,
        word_count=6,
    )
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = MOCK_RENDERER_RESP_HEADERS
        mock_resp.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        result = await tool_generate_visual(content=content, template_id="linkedin-single", source="template")

    assert result["format"] == "png"
    assert result["source"] == "template"


@pytest.mark.asyncio
async def test_queue_post_returns_queued_post():
    with patch("main.db") as mock_db:
        mock_db.__getitem__ = MagicMock(return_value=MagicMock(insert_one=AsyncMock()))
        with patch.dict(os.environ, {"POSTIZ_SECRET": ""}):
            result = await tool_queue_post(
                platform="linkedin",
                caption="Test caption",
                image_path="/app/output/test.png",
                scheduled_at="2026-06-16T10:00:00Z",
                tenant_id="owner-tenant",
            )

    assert "postiz_id" in result
    assert result["platform"] == "linkedin"
    assert len(result["postiz_id"]) > 0


@pytest.mark.asyncio
async def test_get_analytics_returns_report():
    with patch.dict(os.environ, {"POSTIZ_SECRET": ""}):
        result = await tool_get_analytics(platform="all", days=7)

    assert "trend" in result
    assert result["period_days"] == 7
    assert "total_impressions" in result
