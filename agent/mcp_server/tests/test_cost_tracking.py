"""C3: Tests for cost computation and log_tool_call."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

import main
from constants import compute_openrouter_cost as _compute_openrouter_cost, OPENROUTER_PRICING, PERPLEXITY_COSTS
from main import log_tool_call


# ── _compute_openrouter_cost ───────────────────────────────────────────────

class TestComputeOpenrouterCost:
    def test_gemini_flash_cost(self):
        # 1M prompt + 1M completion at (0.075, 0.30) per 1M tokens
        cost = _compute_openrouter_cost("google/gemini-2.5-flash", 1_000_000, 1_000_000)
        assert abs(cost - 0.375) < 1e-6

    def test_free_model_returns_zero(self):
        cost = _compute_openrouter_cost("meta-llama/llama-3.1-8b-instruct:free", 50_000, 50_000)
        assert cost == 0.0

    def test_unknown_model_returns_zero(self):
        cost = _compute_openrouter_cost("nonexistent/model", 10_000, 5_000)
        assert cost == 0.0

    def test_small_token_count(self):
        # 500 prompt + 200 completion for Gemini Flash → (500 * 0.075 + 200 * 0.30) / 1M
        cost = _compute_openrouter_cost("google/gemini-2.5-flash", 500, 200)
        expected = (500 * 0.075 + 200 * 0.30) / 1_000_000
        assert abs(cost - expected) < 1e-9

    def test_claude_sonnet_cost(self):
        # 1000 prompt + 500 completion at (3.00, 15.00) per 1M
        cost = _compute_openrouter_cost("anthropic/claude-sonnet-4-6", 1_000, 500)
        expected = (1_000 * 3.00 + 500 * 15.00) / 1_000_000
        assert abs(cost - expected) < 1e-9

    def test_all_models_in_pricing_table_return_nonzero_for_paid(self):
        paid = [k for k, (p, c) in OPENROUTER_PRICING.items() if p > 0 or c > 0]
        for model in paid:
            cost = _compute_openrouter_cost(model, 1_000, 1_000)
            assert cost > 0, f"Expected positive cost for {model}"


# ── PERPLEXITY_COSTS table ─────────────────────────────────────────────────

class TestPerplexityCosts:
    def test_sonar_cheapest(self):
        assert PERPLEXITY_COSTS["sonar"] < PERPLEXITY_COSTS["sonar-pro"]

    def test_deep_research_most_expensive(self):
        assert PERPLEXITY_COSTS["sonar-deep-research"] > PERPLEXITY_COSTS["sonar-pro"]

    def test_all_costs_positive(self):
        for model, cost in PERPLEXITY_COSTS.items():
            assert cost > 0, f"Expected positive cost for {model}"


# ── log_tool_call ──────────────────────────────────────────────────────────

class TestLogToolCall:
    @pytest.mark.asyncio
    async def test_stores_all_cost_fields(self):
        mock_coll = MagicMock()
        mock_coll.insert_one = AsyncMock()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_coll)
        main.db = mock_db

        await log_tool_call(
            tenant_id="tenant-123",
            tool_name="research_trends",
            status="success",
            run_id="run-abc",
            model="sonar",
            provider="perplexity",
            prompt_tokens=0,
            completion_tokens=0,
            cost_usd=0.0014,
        )

        mock_coll.insert_one.assert_called_once()
        doc = mock_coll.insert_one.call_args[0][0]
        assert doc["tenant_id"] == "tenant-123"
        assert doc["run_id"] == "run-abc"
        assert doc["tool_name"] == "research_trends"
        assert doc["provider"] == "perplexity"
        assert doc["cost_usd"] == 0.0014
        assert "recorded_at" in doc

    @pytest.mark.asyncio
    async def test_does_not_raise_on_db_error(self):
        mock_coll = MagicMock()
        mock_coll.insert_one = AsyncMock(side_effect=Exception("DB down"))
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_coll)
        main.db = mock_db

        # Should swallow the exception
        await log_tool_call(
            tenant_id="t", tool_name="generate_content", status="error",
        )

    @pytest.mark.asyncio
    async def test_run_id_defaults_to_empty_string(self):
        mock_coll = MagicMock()
        mock_coll.insert_one = AsyncMock()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_coll)
        main.db = mock_db

        await log_tool_call(tenant_id="t", tool_name="queue_post", status="success")

        doc = mock_coll.insert_one.call_args[0][0]
        assert doc["run_id"] == ""


# ── tool_generate_content captures token cost ──────────────────────────────

class TestGenerateContentCostCapture:
    @pytest.mark.asyncio
    async def test_logs_cost_with_usage_tokens(self):
        """generate_content should call log_tool_call with usage data from API response."""
        mock_openrouter_resp = {
            "choices": [{"message": {"content": "OfferBerries HR: automate payroll now. #HR"}}],
            "usage": {"prompt_tokens": 400, "completion_tokens": 50},
        }

        mock_coll = MagicMock()
        mock_coll.insert_one = AsyncMock()
        mock_coll.find_one = AsyncMock(return_value=None)
        mock_coll.count_documents = AsyncMock(return_value=1)  # skip seeding
        mock_coll.insert_many = AsyncMock()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_coll)
        main.db = mock_db

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.json.return_value = mock_openrouter_resp
            mock_resp.raise_for_status = MagicMock()
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
                from tools.content import tool_generate_content as _tgc
                result = await _tgc(
                    brief={"topic": "payroll", "trending_angles": ["saves time"]},
                    platform="linkedin",
                    run_id="run-xyz",
                    tenant_id="t1",
                )

        # Should have inserted a tool_call record
        assert mock_coll.insert_one.called
        doc = mock_coll.insert_one.call_args[0][0]
        assert doc["tool_name"] == "generate_content"
        assert doc["prompt_tokens"] == 400
        assert doc["completion_tokens"] == 50
        assert doc["cost_usd"] > 0  # Gemini Flash cost
        assert doc["run_id"] == "run-xyz"
