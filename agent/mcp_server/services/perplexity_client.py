"""Perplexity API client with structured, typed error handling.

Production client raises PerplexityError on every failure condition.
MockPerplexityClient is available for APP_ENV=test only.
"""
import os
import logging
from dataclasses import dataclass
from enum import Enum

import httpx
from pydantic import BaseModel

from .research_parser import ResearchParser

logger = logging.getLogger("mcp_server.perplexity")


# ── Error taxonomy ─────────────────────────────────────────────────────────

class PerplexityErrorType(str, Enum):
    MISSING_KEY = "MISSING_KEY"
    INVALID_KEY = "INVALID_KEY"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    EMPTY_RESULT = "EMPTY_RESULT"
    SERVICE_DOWN = "SERVICE_DOWN"


@dataclass
class UserAction:
    label: str
    href: str


class PerplexityError(Exception):
    """Typed error raised by PerplexityClient for all failure conditions."""

    def __init__(
        self,
        error_type: PerplexityErrorType,
        message: str,
        retry_allowed: bool,
        user_action: UserAction,
    ) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.message = message
        self.retry_allowed = retry_allowed
        self.user_action = user_action

    def to_dict(self) -> dict:
        return {
            "error_type": self.error_type.value,
            "message": self.message,
            "retry_allowed": self.retry_allowed,
            "user_action": {"label": self.user_action.label, "href": self.user_action.href},
        }


# ── Result model ───────────────────────────────────────────────────────────

class ResearchResult(BaseModel):
    topic: str
    trends: list[dict]          # each: {title, description, relevance_score, raw_line}
    citations: list[str] = []
    model_used: str = ""
    raw_response: str = ""


# ── Production client ──────────────────────────────────────────────────────

class PerplexityClient:
    """Calls Perplexity API and returns structured ResearchResult.

    Never returns mock/fallback data — raises PerplexityError on all failures.
    """

    BASE_URL = "https://api.perplexity.ai/chat/completions"
    TIMEOUT = 15.0

    async def research(self, topic: str, platform: str, model: str = "sonar") -> ResearchResult:
        """Research trending angles for the given topic and platform.

        Raises:
            PerplexityError: on any failure (key missing, invalid, quota, empty, service down)
        """
        api_key = os.getenv("PERPLEXITY_API_KEY", "")
        if not api_key:
            raise PerplexityError(
                error_type=PerplexityErrorType.MISSING_KEY,
                message="Research is not configured. Contact OfferBerries support.",
                retry_allowed=False,
                user_action=UserAction(label="Go to Settings", href="/settings/integrations"),
            )

        prompt = (
            f"Trending {topic} for {platform} social media Pakistan SMB 2026. "
            f"What pain points, hooks, and angles are working right now? "
            f"List 5-8 specific trends with brief descriptions."
        )

        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
                resp = await client.post(
                    self.BASE_URL,
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "return_citations": True,
                    },
                )
        except httpx.TimeoutException:
            raise PerplexityError(
                error_type=PerplexityErrorType.SERVICE_DOWN,
                message="Research service is temporarily unavailable. Your run has been saved and can be resumed.",
                retry_allowed=True,
                user_action=UserAction(label="Resume Run", href=""),
            )
        except httpx.RequestError:
            raise PerplexityError(
                error_type=PerplexityErrorType.SERVICE_DOWN,
                message="Research service is temporarily unavailable. Your run has been saved and can be resumed.",
                retry_allowed=True,
                user_action=UserAction(label="Resume Run", href=""),
            )

        if resp.status_code == 401:
            raise PerplexityError(
                error_type=PerplexityErrorType.INVALID_KEY,
                message="Research API key is invalid. Please update it in Settings.",
                retry_allowed=False,
                user_action=UserAction(label="Update API Key", href="/settings/integrations"),
            )

        if resp.status_code in (429, 402):
            raise PerplexityError(
                error_type=PerplexityErrorType.QUOTA_EXCEEDED,
                message="Research quota reached. Your run has been paused — no credits deducted.",
                retry_allowed=False,
                user_action=UserAction(label="View Billing", href="/billing"),
            )

        if resp.status_code >= 500:
            raise PerplexityError(
                error_type=PerplexityErrorType.SERVICE_DOWN,
                message="Research service is temporarily unavailable. Your run has been saved and can be resumed.",
                retry_allowed=True,
                user_action=UserAction(label="Resume Run", href=""),
            )

        resp.raise_for_status()

        data = resp.json()
        raw_content: str = data["choices"][0]["message"]["content"]

        # Extract citations stored alongside the message
        citations: list[str] = []
        raw_citations = data.get("citations", [])
        if isinstance(raw_citations, list):
            citations = [str(c) for c in raw_citations]

        parser = ResearchParser()
        parsed = parser.parse(raw_content)

        if not parsed.trends:
            raise PerplexityError(
                error_type=PerplexityErrorType.EMPTY_RESULT,
                message="Research returned no usable data for this topic. Try a different topic or switch to a more powerful research model.",
                retry_allowed=True,
                user_action=UserAction(label="Retry", href=""),
            )

        return ResearchResult(
            topic=topic,
            trends=parsed.trends,
            citations=citations,
            model_used=model,
            raw_response=raw_content,
        )


# ── Test-only mock client ──────────────────────────────────────────────────

class MockPerplexityClient:
    """Returns deterministic fixture data. Only instantiated when APP_ENV=test."""

    async def research(self, topic: str, platform: str, model: str = "sonar") -> ResearchResult:
        return ResearchResult(
            topic=topic,
            trends=[
                {
                    "title": f"How {topic} saves Pakistani SMBs 3+ hours/week",
                    "description": "Automation reduces manual work significantly",
                    "relevance_score": 1.0,
                    "raw_line": f"- How {topic} saves Pakistani SMBs 3+ hours/week",
                },
                {
                    "title": f"Common {topic} compliance mistakes SMBs make",
                    "description": "Many businesses face costly compliance issues",
                    "relevance_score": 0.9,
                    "raw_line": f"- Common {topic} compliance mistakes SMBs make",
                },
                {
                    "title": f"Why 94% of Karachi businesses still struggle with {topic}",
                    "description": "Legacy processes hold back growth",
                    "relevance_score": 0.8,
                    "raw_line": f"- Why 94% of Karachi businesses still struggle with {topic}",
                },
            ],
            citations=["https://example.com/pakistan-smb-research"],
            model_used=model,
            raw_response="mock fixture",
        )


# ── Factory ────────────────────────────────────────────────────────────────

def get_perplexity_client() -> PerplexityClient | MockPerplexityClient:
    """Return mock client in test env, real client otherwise."""
    if os.getenv("APP_ENV") == "test":
        return MockPerplexityClient()
    return PerplexityClient()
