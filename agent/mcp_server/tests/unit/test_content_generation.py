"""Unit tests for A3: LLM-generated hashtags and CTAs (no hardcoded values)."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tools.content import tool_generate_content, _parse_content_response
from schemas import ResearchBrief


def _mock_openrouter(content: str):
    """Build a mocked OpenRouter HTTP response."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"choices": [{"message": {"content": content}}]}
    resp.raise_for_status = MagicMock()
    return resp


def _make_mock_http(content: str):
    mock_http = AsyncMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    mock_http.post = AsyncMock(return_value=_mock_openrouter(content))
    return mock_http


PAYROLL_BRIEF = ResearchBrief(
    topic="payroll compliance",
    trending_angles=["EOBI deadlines causing SMB stress", "Manual payroll costs PKR 50,000/year"],
    pain_points=["Compliance errors", "Manual processes"],
    suggested_hooks=["Are you still calculating payroll by hand?"],
    platform_notes={},
)

EDUCATIONAL_BRIEF = ResearchBrief(
    topic="HR software trends",
    trending_angles=["Remote work requires digital HR", "Mobile-first payroll growing"],
    pain_points=["Paper-based processes", "Lack of visibility"],
    suggested_hooks=["Your competitors are already automating HR"],
    platform_notes={},
)


# ── Parse helper tests ─────────────────────────────────────────────────────

class TestParseContentResponse:
    def test_parses_valid_json(self):
        raw = json.dumps({
            "copy": "Great post about payroll",
            "hashtags": ["#PayrollAutomation", "#PakistanHR"],
            "cta": "Learn more about compliance",
        })
        copy, hashtags, cta = _parse_content_response(raw, "payroll", "linkedin")
        assert copy == "Great post about payroll"
        assert "#PayrollAutomation" in hashtags
        assert cta == "Learn more about compliance"

    def test_parses_json_inside_code_fence(self):
        raw = '```json\n{"copy": "Post text", "hashtags": ["#HR"], "cta": "Read more"}\n```'
        copy, hashtags, cta = _parse_content_response(raw, "payroll", "linkedin")
        assert copy == "Post text"
        assert "#HR" in hashtags

    def test_fallback_on_non_json(self):
        raw = "Here is a post about payroll. #PayrollTech #HRSoftware"
        copy, hashtags, cta = _parse_content_response(raw, "payroll", "linkedin")
        # Hashtags extracted via regex fallback
        assert "#PayrollTech" in hashtags
        assert "#HRSoftware" in hashtags

    def test_filters_non_hashtag_strings(self):
        raw = json.dumps({
            "copy": "Test",
            "hashtags": ["#ValidTag", "no-hash-sign", "#AnotherValid"],
            "cta": "Learn more",
        })
        _, hashtags, _ = _parse_content_response(raw, "test", "linkedin")
        assert "no-hash-sign" not in hashtags
        assert len(hashtags) == 2

    def test_empty_json_response(self):
        raw = json.dumps({"copy": "Test post", "hashtags": [], "cta": ""})
        copy, hashtags, cta = _parse_content_response(raw, "test", "linkedin")
        assert copy == "Test post"
        assert hashtags == []
        assert cta == ""


# ── Hashtag generation tests ───────────────────────────────────────────────

class TestHashtagsAreTopicSpecific:
    @pytest.mark.asyncio
    async def test_payroll_topic_hashtags_contain_payroll_terms(self):
        json_resp = json.dumps({
            "copy": "Pakistani SMBs face payroll compliance challenges every month.",
            "hashtags": ["#PayrollCompliance", "#EOBIDeadlines", "#HRAutomation", "#PakistanBusiness"],
            "cta": "Learn how to automate payroll compliance",
        })
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test_key"}):
            with patch("httpx.AsyncClient") as mock_cls:
                mock_cls.return_value = _make_mock_http(json_resp)
                with patch("main.db") as mock_db:
                    mock_db.__getitem__ = MagicMock(return_value=MagicMock(find_one=AsyncMock(return_value=None), count_documents=AsyncMock(return_value=1), insert_many=AsyncMock()))
                    result = await tool_generate_content(
                        brief=PAYROLL_BRIEF, platform="linkedin", tenant_id="test"
                    )

        hashtags = result["hashtags"]
        # At least one hashtag should relate to payroll, HR, or compliance
        payroll_terms = {"payroll", "hr", "compliance", "eobi", "pakistan", "business", "automation"}
        found = any(any(term in h.lower() for term in payroll_terms) for h in hashtags)
        assert found, f"Expected topic-specific hashtags, got: {hashtags}"

    @pytest.mark.asyncio
    async def test_hardcoded_offerberries_hashtag_not_returned_by_default(self):
        json_resp = json.dumps({
            "copy": "Payroll automation post copy here.",
            "hashtags": ["#PayrollAutomation", "#PakistanHR", "#EOBICompliance"],
            "cta": "See how businesses automate compliance",
        })
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test_key"}):
            with patch("httpx.AsyncClient") as mock_cls:
                mock_cls.return_value = _make_mock_http(json_resp)
                with patch("main.db") as mock_db:
                    mock_db.__getitem__ = MagicMock(return_value=MagicMock(find_one=AsyncMock(return_value=None), count_documents=AsyncMock(return_value=1), insert_many=AsyncMock()))
                    result = await tool_generate_content(
                        brief=PAYROLL_BRIEF, platform="linkedin", tenant_id="test"
                    )

        # The hardcoded list ["#OfferBerries", "#PakistanSMB"] is gone —
        # hashtags come from LLM, not hardcoded in source
        assert result["hashtags"] != ["#OfferBerries", "#PakistanSMB"]

    @pytest.mark.asyncio
    async def test_different_responses_produce_different_hashtags(self):
        """Each LLM call returns different hashtags — parser handles both correctly."""
        response_a = json.dumps({
            "copy": "Post A",
            "hashtags": ["#PayrollA", "#EOBI", "#PakistanHR"],
            "cta": "Learn more",
        })
        response_b = json.dumps({
            "copy": "Post B",
            "hashtags": ["#HRTech", "#Compliance2026", "#SMBPakistan"],
            "cta": "See the solution",
        })

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test_key"}):
            with patch("main.db") as mock_db:
                mock_db.__getitem__ = MagicMock(return_value=MagicMock(find_one=AsyncMock(return_value=None), count_documents=AsyncMock(return_value=1), insert_many=AsyncMock()))

                with patch("httpx.AsyncClient") as mock_cls:
                    mock_cls.return_value = _make_mock_http(response_a)
                    result_a = await tool_generate_content(brief=PAYROLL_BRIEF, platform="linkedin", tenant_id="t")

                with patch("httpx.AsyncClient") as mock_cls:
                    mock_cls.return_value = _make_mock_http(response_b)
                    result_b = await tool_generate_content(brief=PAYROLL_BRIEF, platform="linkedin", tenant_id="t")

        assert result_a["hashtags"] != result_b["hashtags"]


class TestHashtagCountByPlatform:
    @pytest.mark.asyncio
    async def test_linkedin_respects_5_hashtag_limit(self):
        """Parser accepts what the LLM returns; prompt caps at 5 for LinkedIn."""
        json_resp = json.dumps({
            "copy": "LinkedIn post content",
            "hashtags": ["#HR", "#Payroll", "#Pakistan", "#Business", "#Compliance"],
            "cta": "Connect with us",
        })
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test_key"}):
            with patch("httpx.AsyncClient") as mock_cls:
                mock_cls.return_value = _make_mock_http(json_resp)
                with patch("main.db") as mock_db:
                    mock_db.__getitem__ = MagicMock(return_value=MagicMock(find_one=AsyncMock(return_value=None), count_documents=AsyncMock(return_value=1), insert_many=AsyncMock()))
                    result = await tool_generate_content(brief=PAYROLL_BRIEF, platform="linkedin", tenant_id="t")

        assert len(result["hashtags"]) <= 5

    @pytest.mark.asyncio
    async def test_instagram_returns_at_least_5_hashtags(self):
        json_resp = json.dumps({
            "copy": "Instagram post content",
            "hashtags": ["#HR", "#Payroll", "#Pakistan", "#Business", "#Compliance", "#EOBI", "#HRTech"],
            "cta": "Save this post",
        })
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test_key"}):
            with patch("httpx.AsyncClient") as mock_cls:
                mock_cls.return_value = _make_mock_http(json_resp)
                with patch("main.db") as mock_db:
                    mock_db.__getitem__ = MagicMock(return_value=MagicMock(find_one=AsyncMock(return_value=None), count_documents=AsyncMock(return_value=1), insert_many=AsyncMock()))
                    result = await tool_generate_content(brief=PAYROLL_BRIEF, platform="instagram", tenant_id="t")

        assert len(result["hashtags"]) >= 5


class TestCTAGeneration:
    @pytest.mark.asyncio
    async def test_educational_content_cta_is_not_demo_booking(self):
        json_resp = json.dumps({
            "copy": "Here's how to understand EOBI compliance for your team.",
            "hashtags": ["#EOBI", "#Compliance", "#PakistanHR"],
            "cta": "Read the full compliance guide",
        })
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test_key"}):
            with patch("httpx.AsyncClient") as mock_cls:
                mock_cls.return_value = _make_mock_http(json_resp)
                with patch("main.db") as mock_db:
                    mock_db.__getitem__ = MagicMock(return_value=MagicMock(find_one=AsyncMock(return_value=None), count_documents=AsyncMock(return_value=1), insert_many=AsyncMock()))
                    result = await tool_generate_content(
                        brief=EDUCATIONAL_BRIEF, platform="linkedin", tenant_id="t"
                    )

        cta = result["cta"].lower()
        assert "free demo" not in cta, f"Educational CTA should not be a demo booking, got: {cta}"

    @pytest.mark.asyncio
    async def test_cta_is_not_hardcoded_string(self):
        """Verify 'Book a free demo' is not the hardcoded default for all content."""
        json_resp = json.dumps({
            "copy": "Learn how Pakistan's top SMBs handle payroll compliance.",
            "hashtags": ["#PayrollCompliance", "#PakistanHR"],
            "cta": "Download the compliance checklist",
        })
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test_key"}):
            with patch("httpx.AsyncClient") as mock_cls:
                mock_cls.return_value = _make_mock_http(json_resp)
                with patch("main.db") as mock_db:
                    mock_db.__getitem__ = MagicMock(return_value=MagicMock(find_one=AsyncMock(return_value=None), count_documents=AsyncMock(return_value=1), insert_many=AsyncMock()))
                    result = await tool_generate_content(
                        brief=EDUCATIONAL_BRIEF, platform="linkedin", tenant_id="t"
                    )

        assert result["cta"] != "Book a free demo"


# ── Regression: no hardcoded values in codebase ───────────────────────────

class TestNoHardcodedValues:
    def test_main_py_does_not_contain_offerberries_hashtag_array(self):
        main_path = os.path.join(os.path.dirname(__file__), "..", "..", "main.py")
        with open(main_path) as f:
            source = f.read()
        assert '["#OfferBerries", "#PakistanSMB"]' not in source, (
            "Hardcoded hashtag array found in main.py"
        )

    def test_main_py_does_not_contain_book_free_demo_hardcode(self):
        main_path = os.path.join(os.path.dirname(__file__), "..", "..", "main.py")
        with open(main_path) as f:
            source = f.read()
        # Allow the string in prompts/instructions but not as a hardcoded return value
        lines_with_demo = [
            line for line in source.splitlines()
            if "Book a free demo" in line and "cta=" in line and "=" in line
        ]
        assert not lines_with_demo, (
            f"Hardcoded CTA assignment found: {lines_with_demo}"
        )

    def test_graph_py_does_not_contain_hardcoded_fallback_brief(self):
        graph_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "crew", "graph.py")
        with open(graph_path) as f:
            source = f.read()
        assert "trending_angles" not in source or "Manual processes" not in source, (
            "Hardcoded fallback brief still present in graph.py"
        )
