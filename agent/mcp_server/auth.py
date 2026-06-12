import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel


class AuthError(Exception):
    pass


class TenantContext(BaseModel):
    tenant_id: str
    tier: str  # "owner" | "pro" | "starter" | "demo"
    rate_limits: dict
    feature_flags: set[str]


TIER_LIMITS = {
    "owner": {
        "research_trends": 9999,
        "scrape_competitor": 9999,
        "generate_content": 9999,
        "generate_visual": 9999,
        "queue_post": 9999,
        "get_analytics": 9999,
        "update_strategy": 9999,
    },
    "pro": {
        "research_trends": 30,
        "scrape_competitor": 100,
        "generate_content": 200,
        "generate_visual": 200,
        "queue_post": 100,
        "get_analytics": 9999,
        "update_strategy": 9999,
    },
    "starter": {
        "research_trends": 10,
        "scrape_competitor": 20,
        "generate_content": 50,
        "generate_visual": 50,
        "queue_post": 30,
        "get_analytics": 9999,
        "update_strategy": 9999,
    },
    "demo": {
        "research_trends": 3,
        "scrape_competitor": 0,
        "generate_content": 5,
        "generate_visual": 5,
        "queue_post": 0,
        "get_analytics": 0,
        "update_strategy": 0,
    },
}

TIER_FEATURES = {
    "owner": {"all"},
    "pro": {"research", "content", "visual", "publish", "analytics"},
    "starter": {"research", "content", "visual", "publish", "analytics"},
    "demo": {"research", "content", "visual"},
}


def _hash_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()


async def resolve_api_key(api_key: str, db, redis_client) -> TenantContext:
    key_hash = _hash_key(api_key)

    # Try Redis cache first
    cache_key = f"tenant:{key_hash}"
    cached = await redis_client.get(cache_key)
    if cached:
        data = json.loads(cached)
        return TenantContext(**data)

    # MongoDB lookup
    key_doc = await db["api_keys"].find_one({"key_hash": key_hash})
    if not key_doc:
        raise AuthError("Invalid API key")
    if key_doc.get("revoked_at") is not None:
        raise AuthError("Invalid API key")

    # Check TTL for demo keys
    if key_doc.get("expires_at"):
        expires_at = key_doc["expires_at"]
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires_at:
            raise AuthError("Invalid API key")

    tier = key_doc.get("tier", "starter")
    tenant_id = key_doc["tenant_id"]

    # Fire-and-forget last_used_at update
    async def _update_last_used():
        try:
            await db["api_keys"].update_one(
                {"key_hash": key_hash},
                {"$set": {"last_used_at": datetime.now(timezone.utc)}},
            )
        except Exception:
            pass

    import asyncio
    asyncio.create_task(_update_last_used())

    ctx = TenantContext(
        tenant_id=tenant_id,
        tier=tier,
        rate_limits=TIER_LIMITS.get(tier, TIER_LIMITS["starter"]),
        feature_flags=TIER_FEATURES.get(tier, set()),
    )

    # Cache for 5 minutes
    await redis_client.setex(cache_key, 300, ctx.model_dump_json())

    return ctx
