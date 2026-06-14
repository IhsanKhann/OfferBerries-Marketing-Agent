"""Unit tests for PerplexityClient — A1 requirement."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from services.perplexity_client import (
    PerplexityClient,
    PerplexityError,
    PerplexityErrorType,
    MockPerplexityClient,
    get_perplexity_client,
)


# ── helpers ────────────────────────────────────────────────────────────────

def _mock_http_response(status_code: int, body: dict | None = None, side_effect=None):
    """Build a mocked httpx response."""
    resp = MagicMock()
    resp.status_code = status_code
    if body is not None:
        resp.json.return_value = body
    if side_effect:
        resp.raise_for_status.side_effect = side_effect
    else:
        resp.raise_for_status = MagicMock()
    return resp


BULLET_RESPONSE = {
    "choices": [{
        "message": {
            "content": (
                "- Payroll automation saves Pakistani SMBs 3 days/month\n"
                "- EOBI compliance errors cost businesses PKR 50,000 on average\n"
                "- Manual WhatsApp payslips lead to errors and disputes\n"
                "- JazzCash integration demand growing among SMBs\n"
                "- CNIC verification bottlenecks slowing onboarding"
            )
        }
    }],
    "citations": ["https://dawn.com/payroll", "https://secp.gov.pk/compliance"],
}

NUMBERED_RESPONSE = {
    "choices": [{
        "message": {
            "content": (
                "1. Payroll automation adoption rising in Lahore SMBs\n"
                "2. SECP compliance deadlines causing anxiety\n"
                "3. Raast payment integration becoming standard\n"
                "4. Leave management still manual at 80% of SMBs"
            )
        }
    }],
    "citations": [],
}

EMPTY_RESPONSE = {
    # Short lines below the 40-char paragraph threshold and no list markers — produces zero trends
    "choices": [{"message": {"content": "No data.\nUnsure.\nN/A."}}],
    "citations": [],
}


# ── A1 tests ───────────────────────────────────────────────────────────────

class TestPerplexityClientMissingKey:
    @pytest.mark.asyncio
    async def test_raises_missing_key_error(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("PERPLEXITY_API_KEY", None)
            client = PerplexityClient()
            with pytest.raises(PerplexityError) as exc_info:
                await client.research("payroll", "linkedin")
        err = exc_info.value
        assert err.error_type == PerplexityErrorType.MISSING_KEY
        assert err.retry_allowed is False
        assert "/settings/integrations" in err.user_action.href

    @pytest.mark.asyncio
    async def test_missing_key_message_is_user_friendly(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("PERPLEXITY_API_KEY", None)
            client = PerplexityClient()
            with pytest.raises(PerplexityError) as exc_info:
                await client.research("payroll", "all")
        assert "not configured" in exc_info.value.message.lower() or "support" in exc_info.value.message.lower()


class TestPerplexityClientInvalidKey:
    @pytest.mark.asyncio
    async def test_raises_invalid_key_on_401(self):
        mock_resp = _mock_http_response(401)
        with patch.dict(os.environ, {"PERPLEXITY_API_KEY": "bad_key"}):
            with patch("httpx.AsyncClient") as mock_cls:
                mock_http = AsyncMock()
                mock_http.__aenter__ = AsyncMock(return_value=mock_http)
                mock_http.__aexit__ = AsyncMock(return_value=False)
                mock_http.post = AsyncMock(return_value=mock_resp)
                mock_cls.return_value = mock_http

                client = PerplexityClient()
                with pytest.raises(PerplexityError) as exc_info:
                    await client.research("payroll", "linkedin")

        err = exc_info.value
        assert err.error_type == PerplexityErrorType.INVALID_KEY
        assert err.retry_allowed is False
        assert "/settings/integrations" in err.user_action.href


class TestPerplexityClientQuotaExceeded:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("status_code", [429, 402])
    async def test_raises_quota_exceeded(self, status_code: int):
        mock_resp = _mock_http_response(status_code)
        with patch.dict(os.environ, {"PERPLEXITY_API_KEY": "valid_key"}):
            with patch("httpx.AsyncClient") as mock_cls:
                mock_http = AsyncMock()
                mock_http.__aenter__ = AsyncMock(return_value=mock_http)
                mock_http.__aexit__ = AsyncMock(return_value=False)
                mock_http.post = AsyncMock(return_value=mock_resp)
                mock_cls.return_value = mock_http

                client = PerplexityClient()
                with pytest.raises(PerplexityError) as exc_info:
                    await client.research("payroll", "linkedin")

        err = exc_info.value
        assert err.error_type == PerplexityErrorType.QUOTA_EXCEEDED
        assert err.retry_allowed is False
        assert "/billing" in err.user_action.href
        assert "no credits deducted" in err.message.lower()


class TestPerplexityClientEmptyResult:
    @pytest.mark.asyncio
    async def test_raises_empty_result_when_no_trends_parsed(self):
        mock_resp = _mock_http_response(200, EMPTY_RESPONSE)
        with patch.dict(os.environ, {"PERPLEXITY_API_KEY": "valid_key"}):
            with patch("httpx.AsyncClient") as mock_cls:
                mock_http = AsyncMock()
                mock_http.__aenter__ = AsyncMock(return_value=mock_http)
                mock_http.__aexit__ = AsyncMock(return_value=False)
                mock_http.post = AsyncMock(return_value=mock_resp)
                mock_cls.return_value = mock_http

                client = PerplexityClient()
                with pytest.raises(PerplexityError) as exc_info:
                    await client.research("xyzzy_gibberish_topic_4829", "linkedin")

        err = exc_info.value
        assert err.error_type == PerplexityErrorType.EMPTY_RESULT
        assert err.retry_allowed is True


class TestPerplexityClientServiceDown:
    @pytest.mark.asyncio
    async def test_raises_service_down_on_timeout(self):
        with patch.dict(os.environ, {"PERPLEXITY_API_KEY": "valid_key"}):
            with patch("httpx.AsyncClient") as mock_cls:
                mock_http = AsyncMock()
                mock_http.__aenter__ = AsyncMock(return_value=mock_http)
                mock_http.__aexit__ = AsyncMock(return_value=False)
                mock_http.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
                mock_cls.return_value = mock_http

                client = PerplexityClient()
                with pytest.raises(PerplexityError) as exc_info:
                    await client.research("payroll", "linkedin")

        err = exc_info.value
        assert err.error_type == PerplexityErrorType.SERVICE_DOWN
        assert err.retry_allowed is True

    @pytest.mark.asyncio
    async def test_raises_service_down_on_5xx(self):
        mock_resp = _mock_http_response(503)
        with patch.dict(os.environ, {"PERPLEXITY_API_KEY": "valid_key"}):
            with patch("httpx.AsyncClient") as mock_cls:
                mock_http = AsyncMock()
                mock_http.__aenter__ = AsyncMock(return_value=mock_http)
                mock_http.__aexit__ = AsyncMock(return_value=False)
                mock_http.post = AsyncMock(return_value=mock_resp)
                mock_cls.return_value = mock_http

                client = PerplexityClient()
                with pytest.raises(PerplexityError) as exc_info:
                    await client.research("payroll", "linkedin")

        err = exc_info.value
        assert err.error_type == PerplexityErrorType.SERVICE_DOWN
        assert err.retry_allowed is True

    @pytest.mark.asyncio
    async def test_raises_service_down_on_network_error(self):
        with patch.dict(os.environ, {"PERPLEXITY_API_KEY": "valid_key"}):
            with patch("httpx.AsyncClient") as mock_cls:
                mock_http = AsyncMock()
                mock_http.__aenter__ = AsyncMock(return_value=mock_http)
                mock_http.__aexit__ = AsyncMock(return_value=False)
                mock_http.post = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
                mock_cls.return_value = mock_http

                client = PerplexityClient()
                with pytest.raises(PerplexityError) as exc_info:
                    await client.research("payroll", "linkedin")

        assert exc_info.value.error_type == PerplexityErrorType.SERVICE_DOWN


class TestPerplexityClientSuccessfulParse:
    @pytest.mark.asyncio
    async def test_parses_bullet_list_response(self):
        mock_resp = _mock_http_response(200, BULLET_RESPONSE)
        with patch.dict(os.environ, {"PERPLEXITY_API_KEY": "valid_key"}):
            with patch("httpx.AsyncClient") as mock_cls:
                mock_http = AsyncMock()
                mock_http.__aenter__ = AsyncMock(return_value=mock_http)
                mock_http.__aexit__ = AsyncMock(return_value=False)
                mock_http.post = AsyncMock(return_value=mock_resp)
                mock_cls.return_value = mock_http

                client = PerplexityClient()
                result = await client.research("payroll", "linkedin")

        assert len(result.trends) >= 3
        assert all("title" in t and "description" in t for t in result.trends)

    @pytest.mark.asyncio
    async def test_parses_numbered_list_response(self):
        mock_resp = _mock_http_response(200, NUMBERED_RESPONSE)
        with patch.dict(os.environ, {"PERPLEXITY_API_KEY": "valid_key"}):
            with patch("httpx.AsyncClient") as mock_cls:
                mock_http = AsyncMock()
                mock_http.__aenter__ = AsyncMock(return_value=mock_http)
                mock_http.__aexit__ = AsyncMock(return_value=False)
                mock_http.post = AsyncMock(return_value=mock_resp)
                mock_cls.return_value = mock_http

                client = PerplexityClient()
                result = await client.research("payroll", "linkedin")

        assert len(result.trends) >= 3
        assert result.model_used == "sonar"

    @pytest.mark.asyncio
    async def test_citations_are_extracted_and_stored(self):
        mock_resp = _mock_http_response(200, BULLET_RESPONSE)
        with patch.dict(os.environ, {"PERPLEXITY_API_KEY": "valid_key"}):
            with patch("httpx.AsyncClient") as mock_cls:
                mock_http = AsyncMock()
                mock_http.__aenter__ = AsyncMock(return_value=mock_http)
                mock_http.__aexit__ = AsyncMock(return_value=False)
                mock_http.post = AsyncMock(return_value=mock_resp)
                mock_cls.return_value = mock_http

                client = PerplexityClient()
                result = await client.research("payroll", "linkedin")

        assert len(result.citations) == 2
        assert "dawn.com" in result.citations[0]

    @pytest.mark.asyncio
    async def test_accepts_custom_model(self):
        mock_resp = _mock_http_response(200, BULLET_RESPONSE)
        captured_payload = {}

        async def mock_post(url, **kwargs):
            captured_payload.update(kwargs.get("json", {}))
            return mock_resp

        with patch.dict(os.environ, {"PERPLEXITY_API_KEY": "valid_key"}):
            with patch("httpx.AsyncClient") as mock_cls:
                mock_http = AsyncMock()
                mock_http.__aenter__ = AsyncMock(return_value=mock_http)
                mock_http.__aexit__ = AsyncMock(return_value=False)
                mock_http.post = mock_post
                mock_cls.return_value = mock_http

                client = PerplexityClient()
                await client.research("payroll", "linkedin", model="sonar-pro")

        assert captured_payload.get("model") == "sonar-pro"


class TestPerplexityClientEnvironmentGating:
    def test_get_perplexity_client_returns_mock_in_test_env(self):
        with patch.dict(os.environ, {"APP_ENV": "test"}):
            client = get_perplexity_client()
        assert isinstance(client, MockPerplexityClient)

    def test_get_perplexity_client_returns_real_client_in_production(self):
        env = {k: v for k, v in os.environ.items() if k != "APP_ENV"}
        with patch.dict(os.environ, env, clear=True):
            client = get_perplexity_client()
        assert isinstance(client, PerplexityClient)

    @pytest.mark.asyncio
    async def test_mock_client_returns_research_result(self):
        client = MockPerplexityClient()
        result = await client.research("payroll", "linkedin")
        assert len(result.trends) >= 3
        assert result.topic == "payroll"
        assert len(result.citations) > 0


class TestPerplexityErrorToDict:
    def test_to_dict_structure(self):
        from services.perplexity_client import UserAction
        err = PerplexityError(
            error_type=PerplexityErrorType.MISSING_KEY,
            message="Not configured",
            retry_allowed=False,
            user_action=UserAction(label="Settings", href="/settings"),
        )
        d = err.to_dict()
        assert d["error_type"] == "MISSING_KEY"
        assert d["retry_allowed"] is False
        assert d["user_action"]["href"] == "/settings"
