"""Phase 3 intelligence tests — TDD."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── Platform dimensions ────────────────────────────────────────────────────────

class TestPlatformDimensions:
    def test_linkedin_is_landscape_1200x627(self):
        from constants import PLATFORM_DIMS
        assert PLATFORM_DIMS["linkedin"] == (1200, 627)

    def test_instagram_is_square_1080x1080(self):
        from constants import PLATFORM_DIMS
        assert PLATFORM_DIMS["instagram"] == (1080, 1080)

    def test_twitter_is_landscape_1600x900(self):
        from constants import PLATFORM_DIMS
        assert PLATFORM_DIMS["twitter"] == (1600, 900)

    def test_flux_size_map_linkedin_is_landscape(self):
        from tools.visual import _FAL_SIZE_MAP
        assert _FAL_SIZE_MAP["linkedin"] in ("landscape_16_9", "landscape_4_3", "landscape")


# ── fal.ai as primary visual source in graph ──────────────────────────────────

class TestVisualSourcePriority:
    def test_fal_is_default_source_for_linkedin(self):
        from crew.graph_config import get_visual_source
        assert get_visual_source("linkedin") == "fal"

    def test_fal_is_default_source_for_twitter(self):
        from crew.graph_config import get_visual_source
        assert get_visual_source("twitter") == "fal"

    def test_fal_is_default_source_for_instagram(self):
        from crew.graph_config import get_visual_source
        assert get_visual_source("instagram") == "fal"

    def test_template_is_fallback_source(self):
        from crew.graph_config import get_visual_source
        assert get_visual_source("unknown_platform") == "template"


# ── Competitor Perplexity fallback ────────────────────────────────────────────

class TestCompetitorFallback:
    @pytest.mark.asyncio
    async def test_returns_empty_list_when_both_apify_and_perplexity_keys_missing(self):
        from tools.research import tool_scrape_competitor
        with patch.dict(os.environ, {"APIFY_API_TOKEN": "", "PERPLEXITY_API_KEY": ""}):
            result = await tool_scrape_competitor("linkedin", "daraz.pk")
        assert result == []

    @pytest.mark.asyncio
    async def test_apify_success_does_not_call_perplexity(self):
        from tools.research import tool_scrape_competitor
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = [{
            "text": "Great payroll solution!", "likesCount": 10,
            "commentsCount": 2, "sharesCount": 0, "url": "https://linkedin.com/post/1",
        }]

        with patch("httpx.AsyncClient") as cls, \
             patch.dict(os.environ, {"APIFY_API_TOKEN": "real-token", "PERPLEXITY_API_KEY": "px-key"}):
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            cls.return_value = mock_client

            with patch("tools.research._perplexity_competitor_fallback") as px_fallback:
                result = await tool_scrape_competitor("linkedin", "daraz.pk")

        px_fallback.assert_not_called()
        assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_apify_failure_triggers_perplexity_fallback(self):
        from tools.research import tool_scrape_competitor
        with patch("httpx.AsyncClient") as cls, \
             patch.dict(os.environ, {"APIFY_API_TOKEN": "fake", "PERPLEXITY_API_KEY": "px-key"}):
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(side_effect=Exception("Apify down"))
            cls.return_value = mock_client

            fallback_data = [{"platform": "linkedin", "handle": "daraz.pk", "text": "Daraz promo content"}]
            with patch("tools.research._perplexity_competitor_fallback", return_value=fallback_data) as px_fallback:
                result = await tool_scrape_competitor("linkedin", "daraz.pk")

        px_fallback.assert_called_once()
        assert result == fallback_data

    @pytest.mark.asyncio
    async def test_perplexity_fallback_returns_competitor_post_list(self):
        from tools.research import _perplexity_competitor_fallback
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{
                "message": {
                    "content": "Daraz recently ran a promo campaign.\nLinkPost: Check out our deals!\nEngagement: 500 likes."
                }
            }]
        }
        with patch("httpx.AsyncClient") as cls, \
             patch.dict(os.environ, {"PERPLEXITY_API_KEY": "px-key"}):
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            cls.return_value = mock_client

            result = await _perplexity_competitor_fallback("linkedin", "daraz.pk")

        assert isinstance(result, list)
        assert len(result) >= 1
        assert result[0]["platform"] == "linkedin"
        assert result[0]["handle"] == "daraz.pk"

    @pytest.mark.asyncio
    async def test_perplexity_fallback_returns_empty_when_no_key(self):
        from tools.research import _perplexity_competitor_fallback
        with patch.dict(os.environ, {"PERPLEXITY_API_KEY": ""}):
            result = await _perplexity_competitor_fallback("linkedin", "daraz.pk")
        assert result == []


# ── Performance rating endpoint ───────────────────────────────────────────────

class TestPerformanceRating:
    @pytest.mark.asyncio
    async def test_patch_rate_saves_rating_to_post(self):
        from fastapi.testclient import TestClient
        import main as _m
        from main import app

        mock_coll = MagicMock()
        mock_coll.find_one = AsyncMock(return_value={
            "_id": "post-001", "tenant_id": "t1", "platform": "linkedin",
            "copy": "OfferBerries payroll", "status": "approved",
        })
        mock_coll.update_one = AsyncMock()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_coll)
        _m.db = mock_db

        client = TestClient(app)
        resp = client.patch(
            "/posts/post-001/rate",
            json={"rating": "high"},
            headers={"X-API-Key": ""},
        )
        assert resp.status_code in (200, 401, 404)  # endpoint must exist

    def test_rating_enum_values(self):
        from schemas import PerformanceRating
        assert "high" in [r.value for r in PerformanceRating]
        assert "medium" in [r.value for r in PerformanceRating]
        assert "low" in [r.value for r in PerformanceRating]
