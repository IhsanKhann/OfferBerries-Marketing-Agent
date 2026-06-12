"""Tests for the LangGraph agent graph."""
import pytest
from unittest.mock import AsyncMock, patch

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


MOCK_BRIEF = {
    "topic": "payroll automation",
    "trending_angles": ["Saves 3 days/month", "EOBI compliance"],
    "pain_points": ["Manual sheets", "Errors"],
    "suggested_hooks": ["Stop doing payroll by hand"],
    "platform_notes": {},
}

MOCK_CONTENT = {
    "platform": "linkedin",
    "copy": "Pakistani SMBs waste hours on manual payroll. OfferBerries fixes that.",
    "hashtags": ["#OfferBerries"],
    "cta": "Book a demo",
    "estimated_reading_time": 1,
    "word_count": 12,
}

MOCK_VISUAL = {
    "path": "/app/output/test.png",
    "url": "http://renderer:3001/output/test.png",
    "format": "png",
    "width": 1080,
    "height": 1080,
    "source": "template",
    "template_id": "linkedin-single",
}


def _initial_state(dry_run=True):
    import uuid
    return {
        "topic": "payroll automation",
        "platform_filter": ["linkedin", "twitter"],
        "brief": None,
        "competitor_data": [],
        "platform_content": {},
        "visual_assets": {},
        "queued_posts": [],
        "errors": [],
        "run_id": str(uuid.uuid4()),
        "dry_run": dry_run,
    }


@pytest.mark.asyncio
async def test_research_node_produces_brief():
    from graph import research_node

    state = _initial_state()
    with patch("graph._call_tool", new_callable=AsyncMock) as mock_tool:
        mock_tool.return_value = MOCK_BRIEF
        result = await research_node(state)

    assert result["brief"] is not None
    assert len(result["brief"].get("trending_angles", [])) > 0


@pytest.mark.asyncio
async def test_content_node_produces_content():
    from graph import content_node

    state = _initial_state()
    state["brief"] = MOCK_BRIEF

    with patch("graph._call_tool", new_callable=AsyncMock) as mock_tool:
        mock_tool.return_value = MOCK_CONTENT
        result = await content_node(state)

    assert "linkedin" in result["platform_content"] or len(result["platform_content"]) > 0


@pytest.mark.asyncio
async def test_visual_node_produces_assets():
    from graph import visual_node

    state = _initial_state()
    state["brief"] = MOCK_BRIEF
    state["platform_content"] = {"linkedin": MOCK_CONTENT}

    with patch("graph._call_tool", new_callable=AsyncMock) as mock_tool:
        mock_tool.return_value = MOCK_VISUAL
        result = await visual_node(state)

    assert "linkedin" in result["visual_assets"]
    assert result["visual_assets"]["linkedin"]["format"] == "png"


@pytest.mark.asyncio
async def test_dry_run_does_not_queue():
    from graph import queue_node

    state = _initial_state(dry_run=True)
    state["platform_content"] = {"linkedin": MOCK_CONTENT}
    state["visual_assets"] = {"linkedin": MOCK_VISUAL}

    with patch("graph._call_tool", new_callable=AsyncMock) as mock_tool:
        mock_tool.return_value = {"postiz_id": "test123", "platform": "linkedin"}
        result = await queue_node(state)

    assert len(result["queued_posts"]) == 0  # dry_run skips queuing


@pytest.mark.asyncio
async def test_too_many_errors_skips_to_end():
    from graph import _should_continue
    from langgraph.graph import END

    state = _initial_state()
    state["errors"] = ["err1", "err2", "err3", "err4"]  # > 3

    result = _should_continue(state)
    assert result == END
