"""Multi-format Perplexity response parser.

Handles bullet lists, numbered lists, bold headers, and plain paragraphs,
including mixed formats in a single response. Strips markdown emphasis and
citation markers, and classifies lines explicitly labelled as pain points or
hooks so the caller can route them correctly.
"""
import re
import logging
from dataclasses import dataclass

logger = logging.getLogger("mcp_server.research_parser")

# Citation markers like [1], [2][3]
_CITATION_RE = re.compile(r"\[\d+\](?:\[\d+\])*")
# A bare category header, e.g. "Pain point", "Hooks", "Trends"
_CATEGORY_RE = re.compile(r"^(pain points?|hooks?|angles?|trends?)$", re.IGNORECASE)
# A "Label: value" / "Label - value" line, e.g. "Pain point: How do SMBs ..."
_LABELED_RE = re.compile(r"^(pain points?|hooks?|angles?|trends?)\s*[:\-–—]\s*(.+)$", re.IGNORECASE)


def clean_markdown(text: str) -> str:
    """Strip markdown emphasis, citation markers, surrounding quotes and
    collapse whitespace. Returns a clean human-readable string."""
    if not text:
        return ""
    t = _CITATION_RE.sub("", text)
    t = re.sub(r"[*_`]+", "", t)          # emphasis / code markers
    t = re.sub(r"^#{1,6}\s*", "", t)      # leading heading hashes
    t = re.sub(r"\s+", " ", t).strip()
    t = t.strip('"').strip("'").strip()
    t = t.rstrip(":").strip()
    return t


def _norm_label(raw_label: str) -> str:
    l = raw_label.lower()
    if "pain" in l:
        return "pain_point"
    if "hook" in l:
        return "hook"
    return "angle"


@dataclass
class ParsedTrend:
    title: str
    description: str
    relevance_score: float
    raw_line: str
    label: str = "angle"   # "angle" | "pain_point" | "hook"


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
                trend = self._make_trend(title, desc, line)
                if trend:
                    trends.append(trend)
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
                trend = self._make_trend(title, desc, line)
                if trend:
                    trends.append(trend)
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
                trend = self._make_trend(title, desc, line)
                if trend:
                    trends.append(trend)
                i += 1
                continue

            # Plain paragraph: use if long enough and not a section header
            if len(line) > 40 and not re.match(r"^#{1,4}\s", line):
                trend = self._make_trend(line[:100], line, line)
                if trend:
                    trends.append(trend)

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
                    "label": t.label,
                }
                for t in trends
            ],
            quality_score=quality,
        )

    # ── helpers ──────────────────────────────────────────────────────────────

    def _make_trend(self, title: str, desc: str, raw: str):
        """Clean a (title, description) pair, classify pain-point/hook labels,
        and return a ParsedTrend — or None if there is no usable content.

        A line like "**Pain point:** How do SMBs handle EOBI?" yields the value
        ("How do SMBs handle EOBI?") with label="pain_point", never "**Pain point".
        A bare header ("Pain point") with no value is skipped.
        """
        title_c = clean_markdown(title)
        desc_c = clean_markdown(desc)
        label = "angle"

        # "Label: value" embedded in the title -> take the value
        m = _LABELED_RE.match(title_c)
        if m:
            label = _norm_label(m.group(1))
            value = clean_markdown(m.group(2))
            if not value:
                value = desc_c
            title_c = value
            if not desc_c:
                desc_c = value
        # Bare "Pain point" / "Hook" header -> value must come from description
        elif _CATEGORY_RE.match(title_c):
            label = _norm_label(title_c)
            if not desc_c:
                return None  # header with no value -> skip
            title_c = desc_c

        if not title_c:
            return None
        return ParsedTrend(
            title=title_c,
            description=desc_c or title_c,
            relevance_score=0.0,
            raw_line=raw,
            label=label,
        )

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
