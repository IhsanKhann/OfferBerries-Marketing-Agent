"""Multi-format Perplexity response parser.

Handles bullet lists, numbered lists, bold headers, and plain paragraphs,
including mixed formats in a single response.
"""
import re
import logging
from dataclasses import dataclass

logger = logging.getLogger("mcp_server.research_parser")


@dataclass
class ParsedTrend:
    title: str
    description: str
    relevance_score: float
    raw_line: str


@dataclass
class ParsedResearch:
    trends: list[dict]
    quality_score: float = 0.0


class ResearchParser:
    """Parse Perplexity API responses into structured trend lists."""

    MAX_TRENDS = 10

    def parse(self, raw_response: str) -> ParsedResearch:
        """Parse a raw Perplexity response into structured trends.

        Handles: bullet lists (- • *), numbered lists (1. 1)), bold headers
        (**Trend:** desc), plain paragraphs, and mixed formats.
        """
        trends: list[ParsedTrend] = []
        lines = [line.strip() for line in raw_response.split("\n") if line.strip()]

        i = 0
        while i < len(lines) and len(trends) < self.MAX_TRENDS:
            line = lines[i]

            # Bold header: **Title:** description  or  **Title** description
            bold_match = re.match(r"^\*\*(.+?)\*\*[:\s]+(.+)$", line)
            if bold_match:
                title = bold_match.group(1).strip().rstrip(":")
                desc = bold_match.group(2).strip()
                if i + 1 < len(lines) and not self._is_list_item(lines[i + 1]) and not self._is_header(lines[i + 1]):
                    desc = (desc + " " + lines[i + 1]).strip()
                    i += 1
                trends.append(ParsedTrend(title=title, description=desc, relevance_score=0.0, raw_line=line))
                i += 1
                continue

            # Bullet list: -, •, *
            bullet_match = re.match(r"^[-•*]\s+(.+)$", line)
            if bullet_match:
                content = bullet_match.group(1).strip()
                desc = ""
                if i + 1 < len(lines) and not self._is_list_item(lines[i + 1]) and not self._is_header(lines[i + 1]):
                    desc = lines[i + 1]
                    i += 1
                title, desc = self._split_title_desc(content, desc)
                trends.append(ParsedTrend(title=title, description=desc, relevance_score=0.0, raw_line=line))
                i += 1
                continue

            # Numbered list: 1. or 1)
            numbered_match = re.match(r"^\d+[.)]\s+(.+)$", line)
            if numbered_match:
                content = numbered_match.group(1).strip()
                desc = ""
                if i + 1 < len(lines) and not self._is_list_item(lines[i + 1]) and not self._is_header(lines[i + 1]):
                    desc = lines[i + 1]
                    i += 1
                title, desc = self._split_title_desc(content, desc)
                trends.append(ParsedTrend(title=title, description=desc, relevance_score=0.0, raw_line=line))
                i += 1
                continue

            # Plain paragraph: use if long enough and not a section header
            if len(line) > 40 and not re.match(r"^#{1,4}\s", line):
                title = line[:100]
                trends.append(ParsedTrend(title=title, description=line, relevance_score=0.0, raw_line=line))

            i += 1

        # Assign descending relevance scores (first = most relevant)
        total = len(trends)
        for idx, trend in enumerate(trends):
            trend.relevance_score = round(1.0 - (idx / max(total, 1)) * 0.3, 2)

        quality = min(len(trends) / 5.0, 1.0)
        logger.info("Parsed %d trends (quality=%.2f)", len(trends), quality)

        return ParsedResearch(
            trends=[
                {
                    "title": t.title,
                    "description": t.description,
                    "relevance_score": t.relevance_score,
                    "raw_line": t.raw_line,
                }
                for t in trends
            ],
            quality_score=quality,
        )

    # ── helpers ──────────────────────────────────────────────────────────────

    def _is_list_item(self, line: str) -> bool:
        return bool(re.match(r"^[-•*\d]", line.strip()))

    def _is_header(self, line: str) -> bool:
        return bool(re.match(r"^(#{1,4}\s|\*\*)", line.strip()))

    def _split_title_desc(self, content: str, extra_desc: str) -> tuple[str, str]:
        """Split combined content into (title, description) at a natural boundary."""
        # Colon split
        if ":" in content and len(content.split(":", 1)[0]) < 80:
            parts = content.split(":", 1)
            return parts[0].strip(), (parts[1].strip() + " " + extra_desc).strip()
        # Em-dash / en-dash split
        dash_match = re.split(r" [—–] ", content, maxsplit=1)
        if len(dash_match) == 2:
            return dash_match[0].strip(), (dash_match[1].strip() + " " + extra_desc).strip()
        return content[:80], (extra_desc or content)
