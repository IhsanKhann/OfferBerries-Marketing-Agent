"""Admin, billing, account, usage, models, research-models, and voice-profiles endpoints."""
import hashlib
import hmac as _hmac
import json
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
import main as _m
from fastapi import APIRouter, Header, HTTPException, Request

from auth import TIER_LIMITS
from constants import (
    CTA_TYPE_VALUES,
    HASHTAG_STYLE_VALUES,
    OPENROUTER_MODELS,
    PLAN_PRICES,
    RESEARCH_MODELS_SEED,
    TIER_ORDER,
)
from schemas import (
    CheckoutRequest,
    CreateApiKeyRequest,
    ResearchModel,
    ResearchModelPatch,
    VoiceProfileCreateRequest,
    VoiceProfileUpdateRequest,
)

router = APIRouter()


def _require_owner(x_api_key: Optional[str]):
    owner_key = os.getenv("OWNER_API_KEY", "")
    if not owner_key or x_api_key != owner_key:
        raise HTTPException(status_code=401, detail="Unauthorized")


# ── API key management ────────────────────────────────────────────────────────

@router.get("/admin/api-keys")
async def list_api_keys(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await _m.get_tenant(x_api_key, authorization)
    if tenant.tier != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    cursor = _m.db["api_keys"].find({"revoked_at": None}, {"_id": 0, "key_hash": 0}).sort("created_at", -1).limit(100)
    keys = await cursor.to_list(length=100)
    for k in keys:
        for field in ("created_at", "last_used_at"):
            if k.get(field) and hasattr(k[field], "isoformat"):
                k[field] = k[field].isoformat()
    return keys


@router.post("/admin/api-keys")
async def create_api_key(
    req: CreateApiKeyRequest,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await _m.get_tenant(x_api_key, authorization)
    if tenant.tier != "owner":
        raise HTTPException(status_code=403, detail="Owner only")

    raw_key = "ofb_" + req.tier + "_" + secrets.token_hex(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    await _m.db["api_keys"].insert_one({
        "key_hash": key_hash,
        "key_prefix": f"ofb_{req.tier}_",
        "tenant_id": req.tenant_id,
        "tier": req.tier,
        "label": req.label,
        "created_at": datetime.now(timezone.utc),
        "revoked_at": None,
        "last_used_at": None,
    })
    return {"api_key": raw_key, "tenant_id": req.tenant_id, "tier": req.tier}


# ── Demo sessions ─────────────────────────────────────────────────────────────

@router.post("/admin/tenants/demo")
async def create_demo_session(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    session_id = str(uuid.uuid4())
    raw_key = f"ofb_demo_{secrets.token_hex(16)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=1800)

    await _m.db["api_keys"].insert_one({
        "key_hash": key_hash,
        "key_prefix": "ofb_demo_",
        "tenant_id": f"demo_{session_id}",
        "tier": "demo",
        "session_id": session_id,
        "created_at": datetime.now(timezone.utc),
        "expires_at": expires_at,
        "revoked_at": None,
    })

    await _m.redis_client.setex(
        f"demo:{session_id}",
        1800,
        json.dumps({"api_key_hash": key_hash, "created_at": datetime.now(timezone.utc).isoformat(), "expires_at": expires_at.isoformat()}),
    )

    domain = os.getenv("DOMAIN", "localhost")
    return {
        "session_id": session_id,
        "api_key": raw_key,
        "expires_at": expires_at.isoformat(),
        "demo_url": f"https://agent.{domain}/demo",
    }


@router.delete("/admin/tenants/demo/{session_id}")
async def delete_demo_session(
    session_id: str,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await _m.get_tenant(x_api_key, authorization)
    if tenant.tier != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    tenant_id = f"demo_{session_id}"
    await _m.db["api_keys"].update_many(
        {"tenant_id": tenant_id},
        {"$set": {"revoked_at": datetime.now(timezone.utc)}},
    )
    await _m.redis_client.delete(f"demo:{session_id}")
    return {"deleted": True, "session_id": session_id}


# ── Payment webhooks ──────────────────────────────────────────────────────────

@router.post("/webhooks/safepay")
async def safepay_webhook(request: Request):
    import logging
    logger = logging.getLogger("mcp_server")
    payload = await request.body()
    sig = request.headers.get("X-Safepay-Signature", "")
    secret = os.getenv("SAFEPAY_WEBHOOK_SECRET", "")
    if secret:
        expected = _hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        if not _hmac.compare_digest(expected, sig):
            raise HTTPException(status_code=403, detail="Invalid signature")
    data = json.loads(payload)
    if data.get("event") == "payment.success":
        meta = data.get("data", {}).get("metadata", {})
        logger.info(f"Safepay payment.success for tenant {meta.get('tenant_id')}")
    return {"received": True}


@router.post("/webhooks/2checkout")
async def twocheckout_webhook(request: Request):
    import logging
    logger = logging.getLogger("mcp_server")
    payload = await request.body()
    data = json.loads(payload)
    if data.get("MESSAGE_TYPE") == "ORDER_CREATED":
        logger.info("2Checkout ORDER_CREATED received")
    return {"received": True}


# ── Billing ───────────────────────────────────────────────────────────────────

@router.post("/billing/checkout")
async def create_checkout(
    req: CheckoutRequest,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    safepay_key = os.getenv("SAFEPAY_API_KEY", "")
    amount = PLAN_PRICES.get(req.plan, 4999)
    domain = os.getenv("DOMAIN", "localhost")

    if not safepay_key:
        return {"checkout_url": f"https://agent.{domain}/billing/demo?plan={req.plan}"}

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            "https://sandbox.api.getsafepay.com/order/v1/init/",
            headers={"X-SFPY-MERCHANT-SECRET": safepay_key},
            json={
                "amount": amount,
                "currency": "PKR",
                "order_id": str(uuid.uuid4()),
                "email": req.tenant_email,
                "metadata": {"plan": req.plan},
                "redirect_url": f"https://agent.{domain}/billing/success",
                "cancel_url": f"https://agent.{domain}/billing/cancel",
            },
        )
        result = resp.json()

    return {"checkout_url": result.get("data", {}).get("redirect_url", "https://sandbox.api.getsafepay.com/checkout")}


# ── Account & Usage ───────────────────────────────────────────────────────────

@router.get("/account")
async def get_account(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await _m.get_tenant(x_api_key, authorization)
    key = x_api_key
    if not key and authorization and authorization.startswith("Bearer "):
        key = authorization[7:]
    prefix = f"ofb_{tenant.tier}_"
    masked = (prefix + "••••••••" + key[-4:]) if key and len(key) > 8 else None
    return {
        "tier": tenant.tier,
        "tenant_id": tenant.tenant_id,
        "api_key_masked": masked,
        "api_key_active": True,
    }


@router.get("/usage")
async def get_usage(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await _m.get_tenant(x_api_key, authorization)
    today = _m._today()
    limits = TIER_LIMITS.get(tenant.tier, TIER_LIMITS["starter"])

    tool_usage = {}
    for tool_name, limit in limits.items():
        rl_key = f"ratelimit:{tenant.tenant_id}:{tool_name}:{today}"
        count_str = await _m.redis_client.get(rl_key)
        used = int(count_str) if count_str else 0
        tool_usage[tool_name] = {"used": used, "limit": limit}

    now_utc = datetime.now(timezone.utc)
    reset_at = (now_utc + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    openrouter_data = {"used_tokens": 0, "credit_balance_usd": 0.0, "monthly_spend_usd": 0.0, "monthly_limit_usd": 20.0, "reset_at": reset_at.isoformat()}
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
    if openrouter_key:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    "https://openrouter.ai/api/v1/auth/key",
                    headers={"Authorization": f"Bearer {openrouter_key}"},
                )
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    openrouter_data["credit_balance_usd"] = float(data.get("limit_remaining", 0) or 0)
                    openrouter_data["monthly_spend_usd"] = float(data.get("usage", 0) or 0) / 1_000_000
        except Exception:
            pass

    perplexity_data = {"requests_used": 0, "requests_limit": 100, "reset_at": reset_at.isoformat()}
    apify_data = {"compute_units_used": 0, "compute_units_limit": 500, "reset_at": reset_at.isoformat()}

    try:
        pipeline = [
            {"$match": {"tenant_id": tenant.tenant_id, "recorded_at": {"$gte": now_utc.replace(hour=0, minute=0, second=0, microsecond=0)}}},
            {"$group": {"_id": "$tool_name", "count": {"$sum": 1}}},
        ]
        cursor = _m.db["tool_calls"].aggregate(pipeline)
        async for doc in cursor:
            if doc["_id"] == "research_trends":
                perplexity_data["requests_used"] = doc["count"]
            elif doc["_id"] == "scrape_competitor":
                apify_data["compute_units_used"] = doc["count"] * 5
    except Exception:
        pass

    return {
        "reset_at": reset_at.isoformat(),
        "tier": tenant.tier,
        "tool_usage": tool_usage,
        "vendors": {
            "openrouter": openrouter_data,
            "perplexity": perplexity_data,
            "apify": apify_data,
        },
    }


# ── Models ────────────────────────────────────────────────────────────────────

@router.get("/models/available")
async def get_models(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    await _m.get_tenant(x_api_key, authorization)
    return OPENROUTER_MODELS


# ── Research models CRUD ──────────────────────────────────────────────────────

@router.get("/research-models")
async def list_research_models(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await _m.get_tenant(x_api_key, authorization)
    tier = tenant.tier if tenant.tier != "owner" else "pro"
    tier_level = TIER_ORDER.get(tier, 2)
    cursor = _m.db["research_models"].find({"is_active": True}, {"_id": 0})
    models = await cursor.to_list(length=50)
    if not models:
        models = RESEARCH_MODELS_SEED
    return [m for m in models if TIER_ORDER.get(m.get("tier_required", "free"), 0) <= tier_level]


@router.get("/admin/research-models")
async def admin_list_research_models(x_api_key: Optional[str] = Header(None)):
    _require_owner(x_api_key)
    cursor = _m.db["research_models"].find({}, {"_id": 0})
    models = await cursor.to_list(length=50)
    return models or RESEARCH_MODELS_SEED


@router.post("/admin/research-models", status_code=201)
async def admin_create_research_model(
    req: ResearchModel,
    x_api_key: Optional[str] = Header(None),
):
    _require_owner(x_api_key)
    if req.tier_required not in TIER_ORDER:
        raise HTTPException(status_code=400, detail=f"Invalid tier_required: {req.tier_required}")
    doc = {**req.model_dump(), "created_at": datetime.now(timezone.utc)}
    await _m.db["research_models"].update_one({"id": req.id}, {"$set": doc}, upsert=True)
    return {"saved": True, "id": req.id}


@router.patch("/admin/research-models/{model_id}")
async def admin_patch_research_model(
    model_id: str,
    req: ResearchModelPatch,
    x_api_key: Optional[str] = Header(None),
):
    _require_owner(x_api_key)
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    if "tier_required" in updates and updates["tier_required"] not in TIER_ORDER:
        raise HTTPException(status_code=400, detail=f"Invalid tier_required: {updates['tier_required']}")
    updates["updated_at"] = datetime.now(timezone.utc)
    result = await _m.db["research_models"].update_one({"id": model_id}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Research model not found")
    return {"updated": True, "id": model_id}


# ── Voice profiles CRUD ───────────────────────────────────────────────────────

@router.get("/voice-profiles")
async def list_voice_profiles(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await _m.get_tenant(x_api_key, authorization)
    await _m._seed_voice_profiles_for_tenant(tenant.tenant_id)
    cursor = _m.db["voice_profiles"].find(
        {"tenant_id": tenant.tenant_id, "is_active": True}, {"_id": 0}
    ).sort("name", 1)
    return await cursor.to_list(length=100)


@router.post("/voice-profiles", status_code=201)
async def create_voice_profile(
    req: VoiceProfileCreateRequest,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await _m.get_tenant(x_api_key, authorization)
    if req.hashtag_style not in HASHTAG_STYLE_VALUES:
        raise HTTPException(status_code=400, detail=f"Invalid hashtag_style: {req.hashtag_style}")
    if req.cta_type not in CTA_TYPE_VALUES:
        raise HTTPException(status_code=400, detail=f"Invalid cta_type: {req.cta_type}")
    profile_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    if req.is_default:
        await _m.db["voice_profiles"].update_many(
            {"tenant_id": tenant.tenant_id}, {"$set": {"is_default": False}}
        )
    doc = {
        **req.model_dump(), "id": profile_id,
        "tenant_id": tenant.tenant_id, "is_active": True, "created_at": now,
    }
    await _m.db["voice_profiles"].insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.patch("/voice-profiles/{profile_id}")
async def update_voice_profile(
    profile_id: str,
    req: VoiceProfileUpdateRequest,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await _m.get_tenant(x_api_key, authorization)
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    if "hashtag_style" in updates and updates["hashtag_style"] not in HASHTAG_STYLE_VALUES:
        raise HTTPException(status_code=400, detail=f"Invalid hashtag_style: {updates['hashtag_style']}")
    if "cta_type" in updates and updates["cta_type"] not in CTA_TYPE_VALUES:
        raise HTTPException(status_code=400, detail=f"Invalid cta_type: {updates['cta_type']}")
    updates["updated_at"] = datetime.now(timezone.utc)
    result = await _m.db["voice_profiles"].update_one(
        {"id": profile_id, "tenant_id": tenant.tenant_id}, {"$set": updates}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Voice profile not found")
    return {"updated": True, "id": profile_id}


@router.delete("/voice-profiles/{profile_id}")
async def delete_voice_profile(
    profile_id: str,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await _m.get_tenant(x_api_key, authorization)
    doc = await _m.db["voice_profiles"].find_one(
        {"id": profile_id, "tenant_id": tenant.tenant_id}, {"is_default": 1}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Voice profile not found")
    if doc.get("is_default"):
        raise HTTPException(status_code=400, detail="Cannot delete the default voice profile")
    await _m.db["voice_profiles"].update_one(
        {"id": profile_id, "tenant_id": tenant.tenant_id},
        {"$set": {"is_active": False, "deleted_at": datetime.now(timezone.utc)}},
    )
    return {"deleted": True, "id": profile_id}


@router.patch("/voice-profiles/{profile_id}/set-default")
async def set_default_voice_profile(
    profile_id: str,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await _m.get_tenant(x_api_key, authorization)
    doc = await _m.db["voice_profiles"].find_one(
        {"id": profile_id, "tenant_id": tenant.tenant_id, "is_active": True}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Voice profile not found")
    await _m.db["voice_profiles"].update_many(
        {"tenant_id": tenant.tenant_id}, {"$set": {"is_default": False}}
    )
    await _m.db["voice_profiles"].update_one(
        {"id": profile_id}, {"$set": {"is_default": True, "updated_at": datetime.now(timezone.utc)}}
    )
    return {"default_set": True, "id": profile_id}
