"""Tests for rate limiting logic."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from auth import TenantContext, TIER_LIMITS
from main import check_rate_limit


def _make_redis(count_sequence):
    """Return a mock redis where incr returns values from count_sequence in order."""
    redis = AsyncMock()
    redis.incr = AsyncMock(side_effect=count_sequence)
    redis.expire = AsyncMock()
    return redis


def _make_tenant(tier):
    return TenantContext(
        tenant_id=f"test-{tier}",
        tier=tier,
        rate_limits=TIER_LIMITS[tier],
        feature_flags=set(),
    )


@pytest.mark.asyncio
async def test_owner_tier_no_limit():
    """Owner tier: 100 calls to any tool succeed."""
    tenant = _make_tenant("owner")
    # Owner limit is 9999 — calling 100 times should all pass
    redis = _make_redis(list(range(1, 101)))
    # Patch module-level redis_client
    import main
    original = main.redis_client
    main.redis_client = redis
    try:
        for i in range(100):
            await check_rate_limit(tenant, "research_trends")
    finally:
        main.redis_client = original


@pytest.mark.asyncio
async def test_starter_scrape_competitor_limit():
    """Starter tier: scrape_competitor limit is 20. 21st call raises 429."""
    tenant = _make_tenant("starter")
    import main
    original = main.redis_client

    # First 20 calls succeed, 21st call hits limit
    call_count = 0

    async def fake_incr(key):
        nonlocal call_count
        call_count += 1
        return call_count

    redis = AsyncMock()
    redis.incr = fake_incr
    redis.expire = AsyncMock()
    main.redis_client = redis

    try:
        for i in range(20):
            await check_rate_limit(tenant, "scrape_competitor")

        with pytest.raises(HTTPException) as exc_info:
            await check_rate_limit(tenant, "scrape_competitor")
        assert exc_info.value.status_code == 429
    finally:
        main.redis_client = original


@pytest.mark.asyncio
async def test_demo_generate_content_limit():
    """Demo tier: generate_content limit is 5. 6th call raises 429."""
    tenant = _make_tenant("demo")
    import main
    original = main.redis_client

    call_count = 0

    async def fake_incr(key):
        nonlocal call_count
        call_count += 1
        return call_count

    redis = AsyncMock()
    redis.incr = fake_incr
    redis.expire = AsyncMock()
    main.redis_client = redis

    try:
        for i in range(5):
            await check_rate_limit(tenant, "generate_content")

        with pytest.raises(HTTPException) as exc_info:
            await check_rate_limit(tenant, "generate_content")
        assert exc_info.value.status_code == 429
    finally:
        main.redis_client = original


@pytest.mark.asyncio
async def test_demo_scrape_competitor_blocked():
    """Demo tier: scrape_competitor limit is 0, always blocked."""
    tenant = _make_tenant("demo")
    import main
    original = main.redis_client

    redis = AsyncMock()
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock()
    main.redis_client = redis

    try:
        with pytest.raises(HTTPException) as exc_info:
            await check_rate_limit(tenant, "scrape_competitor")
        assert exc_info.value.status_code == 403
    finally:
        main.redis_client = original


@pytest.mark.asyncio
async def test_rate_limit_resets_after_ttl():
    """Simulating TTL reset: after expiry, counter goes back to 1."""
    tenant = _make_tenant("starter")
    import main
    original = main.redis_client

    # Simulate: first call is day 1 count 20 (at limit), then TTL resets and count=1
    counts = [20, 1]
    idx = [0]

    async def fake_incr(key):
        val = counts[idx[0]]
        idx[0] = min(idx[0] + 1, len(counts) - 1)
        return val

    redis = AsyncMock()
    redis.incr = fake_incr
    redis.expire = AsyncMock()
    main.redis_client = redis

    try:
        # At limit
        await check_rate_limit(tenant, "scrape_competitor")  # returns 20, allowed (20 <= 20)
        # After TTL reset, counter is 1 again
        await check_rate_limit(tenant, "scrape_competitor")  # returns 1, allowed
    finally:
        main.redis_client = original
