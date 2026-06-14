"""Unit tests for ResearchParser — A2 requirement."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from services.research_parser import ResearchParser


@pytest.fixture
def parser():
    return ResearchParser()


# ── Format parsing tests ───────────────────────────────────────────────────

class TestBulletListParsing:
    def test_dash_bullets_extracted(self, parser):
        text = (
            "- Payroll automation saves 3 days per month\n"
            "- EOBI compliance errors cost businesses\n"
            "- WhatsApp payslips cause data errors\n"
        )
        result = parser.parse(text)
        assert len(result.trends) == 3
        assert all(t["title"] for t in result.trends)

    def test_bullet_point_unicode(self, parser):
        text = (
            "• Trend one: payroll automation growing\n"
            "• Trend two: compliance burden increasing\n"
            "• Trend three: digital payments accelerating\n"
        )
        result = parser.parse(text)
        assert len(result.trends) == 3

    def test_asterisk_bullets_extracted(self, parser):
        text = (
            "* First insight about HR tech\n"
            "* Second insight about payroll\n"
            "* Third insight about compliance\n"
        )
        result = parser.parse(text)
        assert len(result.trends) == 3


class TestNumberedListParsing:
    def test_period_numbered_list(self, parser):
        text = (
            "1. Payroll errors cost SMBs PKR 50,000/year on average\n"
            "2. SECP deadlines causing compliance panic\n"
            "3. Raast payment integration now expected\n"
            "4. Manual leave tracking still common at 80% of SMBs\n"
        )
        result = parser.parse(text)
        assert len(result.trends) == 4

    def test_parenthesis_numbered_list(self, parser):
        text = (
            "1) HR automation trend accelerating in Karachi\n"
            "2) Remote work compliance questions rising\n"
            "3) Mobile payroll apps gaining adoption\n"
        )
        result = parser.parse(text)
        assert len(result.trends) == 3


class TestParagraphParsing:
    def test_long_paragraphs_extracted_as_trends(self, parser):
        text = (
            "Pakistani SMBs are increasingly adopting payroll automation to reduce "
            "compliance errors and administrative burden across Karachi and Lahore.\n\n"
            "EOBI registration challenges continue to affect small businesses as the "
            "government tightens enforcement of social security contributions.\n\n"
            "Digital payment integration through Raast and JazzCash is becoming a "
            "competitive differentiator for HR software providers in Pakistan.\n"
        )
        result = parser.parse(text)
        assert len(result.trends) >= 2

    def test_short_lines_not_extracted_as_paragraphs(self, parser):
        text = "Short.\nAlso short.\nToo brief."
        result = parser.parse(text)
        assert len(result.trends) == 0


class TestBoldHeaderParsing:
    def test_bold_trend_headers_extracted(self, parser):
        text = (
            "**Payroll Automation:** Pakistani SMBs are saving 3+ days per month\n"
            "**EOBI Compliance:** Errors cost businesses PKR 50,000 on average\n"
            "**Digital Payments:** Raast integration becoming standard in HR software\n"
        )
        result = parser.parse(text)
        assert len(result.trends) == 3
        assert result.trends[0]["title"] == "Payroll Automation"
        assert "3+ days" in result.trends[0]["description"]

    def test_bold_header_without_colon(self, parser):
        text = "**Key Trend** Important insight about payroll software adoption\n"
        result = parser.parse(text)
        assert len(result.trends) == 1


class TestMixedFormatParsing:
    def test_mixed_format_extracts_all_trends(self, parser):
        text = (
            "**Key Insight:** Payroll automation is growing fast\n"
            "- Manual payslips still common at 70% of SMBs\n"
            "1. EOBI registration challenges persist\n"
            "2. JazzCash integration demand rising\n"
            "- Compliance burden increasing due to SECP changes\n"
        )
        result = parser.parse(text)
        assert len(result.trends) == 5

    def test_zero_trends_no_crash(self, parser):
        text = "This is a response with no structured trend data whatsoever."
        result = parser.parse(text)
        # Should not crash; may or may not extract the paragraph
        assert isinstance(result.trends, list)

    def test_empty_string_no_crash(self, parser):
        result = parser.parse("")
        assert result.trends == []


class TestCitationPreservation:
    def test_citations_in_response_noted(self, parser):
        """Parser processes the text — citations are passed separately by caller."""
        text = "- Trend with citation [1]\n- Another trend [2]\n- Third trend [3]\n"
        result = parser.parse(text)
        # Citations are in raw_line — verify they're preserved
        assert len(result.trends) == 3
        assert "[1]" in result.trends[0]["raw_line"]


class TestTrendCapping:
    def test_15_trends_capped_at_10(self, parser):
        lines = "\n".join([f"- Trend {i}: description for trend {i}" for i in range(15)])
        result = parser.parse(lines)
        assert len(result.trends) == 10

    def test_exactly_10_trends_not_capped(self, parser):
        lines = "\n".join([f"- Trend {i}: description" for i in range(10)])
        result = parser.parse(lines)
        assert len(result.trends) == 10


class TestRelevanceScores:
    def test_relevance_scores_are_descending(self, parser):
        text = "\n".join([f"- Trend {i}: detailed description here" for i in range(5)])
        result = parser.parse(text)
        scores = [t["relevance_score"] for t in result.trends]
        assert scores == sorted(scores, reverse=True), "Scores must be descending"

    def test_first_item_has_highest_score(self, parser):
        text = (
            "- First trend: most important insight\n"
            "- Second trend: second most important\n"
            "- Third trend: third insight\n"
        )
        result = parser.parse(text)
        assert result.trends[0]["relevance_score"] >= result.trends[-1]["relevance_score"]

    def test_all_scores_between_0_and_1(self, parser):
        text = "\n".join([f"- Trend {i}: description" for i in range(8)])
        result = parser.parse(text)
        for t in result.trends:
            assert 0.0 <= t["relevance_score"] <= 1.0


class TestQualityScore:
    def test_quality_score_increases_with_more_trends(self, parser):
        two_trends = "- A: desc\n- B: desc\n"
        five_trends = "\n".join([f"- Trend {i}: description here" for i in range(5)])
        r2 = parser.parse(two_trends)
        r5 = parser.parse(five_trends)
        assert r5.quality_score > r2.quality_score

    def test_quality_score_capped_at_1(self, parser):
        text = "\n".join([f"- Trend {i}: detailed description" for i in range(20)])
        result = parser.parse(text)
        assert result.quality_score <= 1.0
