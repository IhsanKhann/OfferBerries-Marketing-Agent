import hashlib
import logging
import os
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import redis.asyncio as aioredis
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

from auth import AuthError, TenantContext, resolve_api_key
from constants import DEFAULT_VOICE_PROFILES, RESEARCH_MODELS_SEED, REQUIRED_ENV
from schemas import ResearchBrief, PlatformContent

# ── Startup validation ────────────────────────────────────────────────────────

def _validate_env():
    missing = [k for k in REQUIRED_ENV if not os.getenv(k)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

_validate_env()

# ── Log filter — redact API keys ──────────────────────────────────────────────

_KEY_PATTERN = re.compile(r"ofb_[a-z]+_[a-f0-9]{32,}")

class RedactingFilter(logging.Filter):
    def filter(self, record):
        record.msg = _KEY_PATTERN.sub("[REDACTED]", str(record.msg))
        return True

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp_server")
logger.addFilter(RedactingFilter())

# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(title="OfferBerries MCP Server", version="1.0.0")
_start_time = time.time()

DOMAIN = os.getenv("DOMAIN", "localhost")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"https://agent.{DOMAIN}", f"https://design.{DOMAIN}"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# ── DB clients (initialised on startup) ──────────────────────────────────────

mongo_client: Optional[AsyncIOMotorClient] = None
db = None
redis_client = None


@app.on_event("startup")
async def startup():
    global mongo_client, db, redis_client
    mongo_client = AsyncIOMotorClient(os.environ["MONGODB_URI"])
    db = mongo_client[os.environ["MONGODB_DB"]]
    redis_client = aioredis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    await _seed_research_models()


@app.on_event("shutdown")
async def shutdown():
    if mongo_client:
        mongo_client.close()
    if redis_client:
        await redis_client.close()

# ── Helpers ───────────────────────────────────────────────────────────────────

async def get_tenant(x_api_key: Optional[str] = None, authorization: Optional[str] = None) -> TenantContext:
    key = x_api_key
    if not key and authorization and authorization.startswith("Bearer "):
        key = authorization[7:]
    if not key:
        raise HTTPException(status_code=401, detail="API key required")
    try:
        return await resolve_api_key(key, db, redis_client)
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e))


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _require_owner(x_api_key: Optional[str]):
    owner_key = os.getenv("OWNER_API_KEY", "")
    if not owner_key or x_api_key != owner_key:
        raise HTTPException(status_code=401, detail="Unauthorized")


async def check_rate_limit(tenant: TenantContext, tool_name: str):
    limit = tenant.rate_limits.get(tool_name, 0)
    if limit == 0:
        raise HTTPException(status_code=403, detail=f"Tool '{tool_name}' not available on {tenant.tier} tier")
    rl_key = f"ratelimit:{tenant.tenant_id}:{tool_name}:{_today()}"
    count = await redis_client.incr(rl_key)
    if count == 1:
        await redis_client.expire(rl_key, 86400)
    if count > limit:
        raise HTTPException(status_code=429, detail=f"Daily limit of {limit} reached for {tool_name}")


async def log_tool_call(
    tenant_id: str,
    tool_name: str,
    status: str,
    run_id: str = "",
    model: str = "",
    provider: str = "",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cost_usd: float = 0.0,
):
    try:
        await db["tool_calls"].insert_one({
            "tenant_id": tenant_id,
            "run_id": run_id,
            "tool_name": tool_name,
            "status": status,
            "provider": provider,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost_usd": cost_usd,
            "recorded_at": datetime.now(timezone.utc),
        })
    except Exception:
        pass


async def _seed_research_models() -> None:
    if db is None:
        return
    count = await db["research_models"].count_documents({})
    if count == 0:
        await db["research_models"].insert_many(RESEARCH_MODELS_SEED)
        logger.info("Seeded %d research models", len(RESEARCH_MODELS_SEED))


async def _seed_voice_profiles_for_tenant(tenant_id: str) -> None:
    count = await db["voice_profiles"].count_documents({"tenant_id": tenant_id})
    if count == 0:
        now = datetime.now(timezone.utc)
        docs = [
            {**p, "id": str(uuid.uuid4()), "tenant_id": tenant_id, "is_active": True, "created_at": now}
            for p in DEFAULT_VOICE_PROFILES
        ]
        await db["voice_profiles"].insert_many(docs)
        logger.info("Seeded %d voice profiles for tenant %s", len(docs), tenant_id)


# ── Register routers (after all helpers are defined to avoid circular import) ─

from routers.queue_router import router as queue_router
from routers.config_router import router as config_router
from routers.admin_router import router as admin_router

app.include_router(queue_router)
app.include_router(config_router)
app.include_router(admin_router)

# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0", "uptime_seconds": int(time.time() - _start_time)}

# ── MCP endpoint ──────────────────────────────────────────────────────────────

@app.post("/mcp")
async def mcp_endpoint(
    request: Request,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await get_tenant(x_api_key, authorization)
    body = await request.json()
    method = body.get("method", "")
    params = body.get("params", {})

    if method == "tools/list":
        return {
            "tools": [
                {"name": "research_trends",       "description": "Research trending topics on social media"},
                {"name": "scrape_competitor",     "description": "Scrape competitor posts via Apify"},
                {"name": "generate_content",      "description": "Generate platform-specific content copy"},
                {"name": "generate_visual_brief", "description": "LLM-driven visual art direction brief"},
                {"name": "generate_visual",       "description": "Render a visual asset from a template"},
                {"name": "queue_post",            "description": "Queue a post in Postiz for scheduling"},
                {"name": "get_analytics",         "description": "Retrieve analytics from Postiz"},
                {"name": "update_strategy",       "description": "Update the weekly content strategy doc"},
            ]
        }

    if method == "tools/call":
        tool_name = params.get("name", "")
        args = params.get("arguments", {})
        run_id = args.pop("__run_id", "")
        await check_rate_limit(tenant, tool_name)
        try:
            result = await _dispatch_tool(tool_name, args, tenant, run_id=run_id)
            return {"result": result}
        except HTTPException:
            raise
        except Exception as exc:
            await log_tool_call(tenant.tenant_id, tool_name, "error", run_id=run_id)
            logger.error(f"Tool {tool_name} error: {exc}")
            raise HTTPException(status_code=500, detail=str(exc))

    raise HTTPException(status_code=400, detail=f"Unknown method: {method}")


async def _dispatch_tool(name: str, args: dict, tenant: TenantContext, run_id: str = ""):
    if name == "research_trends":
        from tools.research import tool_research_trends
        return await tool_research_trends(run_id=run_id, tenant_id=tenant.tenant_id, **args)
    if name == "scrape_competitor":
        from tools.research import tool_scrape_competitor
        return await tool_scrape_competitor(**args)
    if name == "generate_content":
        from tools.content import tool_generate_content
        brief = ResearchBrief(**args["brief"]) if isinstance(args.get("brief"), dict) else args.get("brief")
        return await tool_generate_content(
            brief=brief,
            platform=args.get("platform", "linkedin"),
            product=args.get("product", "full_erp"),
            model=args.get("model") or "anthropic/claude-sonnet-4-6",
            tenant_id=tenant.tenant_id,
            run_id=run_id,
        )
    if name == "generate_visual_brief":
        from tools.visual import tool_generate_visual_brief
        return await tool_generate_visual_brief(
            brief=args.get("brief", {}),
            content=args.get("content", {}),
            platform=args.get("platform", "linkedin"),
            brand_context=args.get("brand_context", {}),
            run_id=run_id,
            tenant_id=tenant.tenant_id,
        )
    if name == "generate_visual":
        from tools.visual import tool_generate_visual
        content = PlatformContent(**args["content"]) if isinstance(args.get("content"), dict) else args.get("content")
        return await tool_generate_visual(
            content=content,
            template_id=args.get("template_id", "linkedin-single"),
            source=args.get("source", "template"),
            visual_brief=args.get("visual_brief"),
        )
    if name == "queue_post":
        from tools.queue import tool_queue_post
        return await tool_queue_post(tenant_id=tenant.tenant_id, run_id=run_id, **args)
    if name == "get_analytics":
        from tools.analytics import tool_get_analytics
        return await tool_get_analytics(**args)
    if name == "update_strategy":
        from tools.analytics import tool_update_strategy
        return await tool_update_strategy(tenant_id=tenant.tenant_id, changes=args.get("changes", {}))
    raise HTTPException(status_code=400, detail=f"Unknown tool: {name}")
