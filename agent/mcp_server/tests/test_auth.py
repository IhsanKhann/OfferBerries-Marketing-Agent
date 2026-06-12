"""Tests for tenant auth / API key resolution."""
import hashlib
import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from auth import AuthError, TenantContext, resolve_api_key, TIER_LIMITS


def _make_key_doc(tier="owner", revoked=False, expires_in_seconds=None):
    raw_key = "test_api_key_abc123"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    doc = {
        "key_hash": key_hash,
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "tier": tier,
        "revoked_at": datetime.now(timezone.utc) if revoked else None,
        "last_used_at": None,
        "expires_at": None,
    }
    if expires_in_seconds is not None:
        doc["expires_at"] = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)
    return raw_key, key_hash, doc


def _make_mocks(key_doc=None, cached=None):
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=MagicMock(
        find_one=AsyncMock(return_value=key_doc),
        update_one=AsyncMock(),
    ))
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=cached)
    redis.setex = AsyncMock()
    return db, redis


@pytest.mark.asyncio
async def test_valid_owner_key():
    raw_key, key_hash, doc = _make_key_doc("owner")
    db, redis = _make_mocks(key_doc=doc, cached=None)
    ctx = await resolve_api_key(raw_key, db, redis)
    assert ctx.tier == "owner"
    assert ctx.tenant_id == doc["tenant_id"]
    assert ctx.rate_limits["generate_content"] == TIER_LIMITS["owner"]["generate_content"]


@pytest.mark.asyncio
async def test_invalid_key_raises():
    db, redis = _make_mocks(key_doc=None, cached=None)
    with pytest.raises(AuthError):
        await resolve_api_key("bad_key_xyz", db, redis)


@pytest.mark.asyncio
async def test_revoked_key_raises():
    raw_key, _, doc = _make_key_doc("owner", revoked=True)
    db, redis = _make_mocks(key_doc=doc, cached=None)
    with pytest.raises(AuthError):
        await resolve_api_key(raw_key, db, redis)


@pytest.mark.asyncio
async def test_redis_cache_hit():
    raw_key, key_hash, doc = _make_key_doc("pro")
    ctx_data = TenantContext(
        tenant_id="cached-tenant",
        tier="pro",
        rate_limits=TIER_LIMITS["pro"],
        feature_flags=set(),
    )
    db, redis = _make_mocks(key_doc=doc, cached=ctx_data.model_dump_json())
    ctx = await resolve_api_key(raw_key, db, redis)
    assert ctx.tenant_id == "cached-tenant"
    # MongoDB should NOT have been called
    db["api_keys"].find_one.assert_not_called()


@pytest.mark.asyncio
async def test_demo_tier_resolves():
    raw_key, _, doc = _make_key_doc("demo")
    doc["expires_at"] = datetime.now(timezone.utc) + timedelta(minutes=30)
    db, redis = _make_mocks(key_doc=doc, cached=None)
    ctx = await resolve_api_key(raw_key, db, redis)
    assert ctx.tier == "demo"
    assert ctx.rate_limits["scrape_competitor"] == 0
