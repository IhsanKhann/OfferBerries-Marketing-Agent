import hashlib
import hmac
import logging
import os
import re
import secrets
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel

from auth import AuthError, TenantContext, resolve_api_key

# ── Startup validation ─────────────────────────────────────────────────────
REQUIRED_ENV = [
    "MONGODB_URI", "MONGODB_DB", "REDIS_URL",
    "OWNER_API_KEY", "OWNER_TENANT_ID",
    "OPENROUTER_API_KEY",
    "MCP_SERVER_URL",
]
# Optional: PERPLEXITY_API_KEY — web search tool degrades gracefully without it

def _validate_env():
    missing = [k for k in REQUIRED_ENV if not os.getenv(k)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

_validate_env()

# ── Log filter — redact API keys ───────────────────────────────────────────
_KEY_PATTERN = re.compile(r"ofb_[a-z]+_[a-f0-9]{32,}")

class RedactingFilter(logging.Filter):
    def filter(self, record):
        record.msg = _KEY_PATTERN.sub("[REDACTED]", str(record.msg))
        return True

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp_server")
logger.addFilter(RedactingFilter())

# ── App ────────────────────────────────────────────────────────────────────
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

# ── DB clients (initialised on startup) ───────────────────────────────────
mongo_client: Optional[AsyncIOMotorClient] = None
db = None
redis_client = None

@app.on_event("startup")
async def startup():
    global mongo_client, db, redis_client
    mongo_client = AsyncIOMotorClient(os.environ["MONGODB_URI"])
    db = mongo_client[os.environ["MONGODB_DB"]]
    redis_client = aioredis.from_url(os.environ["REDIS_URL"], decode_responses=True)

@app.on_event("shutdown")
async def shutdown():
    if mongo_client:
        mongo_client.close()
    if redis_client:
        await redis_client.close()

# ── Helpers ────────────────────────────────────────────────────────────────

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


async def log_tool_call(tenant_id: str, tool_name: str, status: str, cost_estimate: float = 0.0):
    try:
        await db["tool_calls"].insert_one({
            "tenant_id": tenant_id,
            "tool_name": tool_name,
            "status": status,
            "cost_estimate": cost_estimate,
            "recorded_at": datetime.now(timezone.utc),
        })
    except Exception:
        pass

# ── Pydantic models ────────────────────────────────────────────────────────

class ResearchBrief(BaseModel):
    topic: str
    trending_angles: list[str] = []
    pain_points: list[str] = []
    suggested_hooks: list[str] = []
    platform_notes: dict[str, str] = {}
    generated_at: str = ""

class PlatformContent(BaseModel):
    platform: str
    copy: str
    hashtags: list[str] = []
    cta: str = ""
    estimated_reading_time: int = 1
    word_count: int = 0

class VisualAsset(BaseModel):
    path: str = ""
    url: str = ""
    format: str = "png"
    width: int = 1080
    height: int = 1080
    source: str = "template"
    template_id: str = ""

class CompetitorPost(BaseModel):
    platform: str
    handle: str
    text: str = ""
    likes: int = 0
    comments: int = 0
    shares: int = 0
    posted_at: str = ""
    url: str = ""

class QueuedPost(BaseModel):
    postiz_id: str
    platform: str
    scheduled_at: str
    preview_url: str = ""

class AnalyticsReport(BaseModel):
    period_days: int
    total_impressions: int = 0
    total_clicks: int = 0
    top_posts: list[dict] = []
    platform_breakdown: dict = {}
    trend: str = "flat"
    best_performing_template: str = ""
    best_performing_day: str = ""
    recommendations: list[str] = []

class StrategyDoc(BaseModel):
    tenant_id: str
    week_of: str = ""
    topic_focus: str = ""
    format_preference: str = ""
    platform_priority: list[str] = []
    tone_notes: str = ""
    avoid_topics: list[str] = []
    updated_at: str = ""

# ── Platform dimension map ─────────────────────────────────────────────────
PLATFORM_DIMS = {
    "linkedin": (1080, 1080),
    "twitter": (1600, 900),
    "instagram": (1080, 1080),
    "youtube": (1280, 720),
    "email": (600, 200),
}

PLATFORM_CHAR_LIMITS = {
    "linkedin": 1300,
    "twitter": 280,
    "instagram": 2200,
    "youtube": 500,
    "email": 300,
}

# ── Health check ───────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0", "uptime_seconds": int(time.time() - _start_time)}

# ── MCP endpoint (JSON-RPC style) ─────────────────────────────────────────
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
                {"name": "research_trends", "description": "Research trending topics on social media"},
                {"name": "scrape_competitor", "description": "Scrape competitor posts via Apify"},
                {"name": "generate_content", "description": "Generate platform-specific content copy"},
                {"name": "generate_visual", "description": "Render a visual asset from a template"},
                {"name": "queue_post", "description": "Queue a post in Postiz for scheduling"},
                {"name": "get_analytics", "description": "Retrieve analytics from Postiz"},
                {"name": "update_strategy", "description": "Update the weekly content strategy doc"},
            ]
        }

    if method == "tools/call":
        tool_name = params.get("name", "")
        args = params.get("arguments", {})
        await check_rate_limit(tenant, tool_name)

        try:
            result = await _dispatch_tool(tool_name, args, tenant)
            await log_tool_call(tenant.tenant_id, tool_name, "success")
            return {"result": result}
        except HTTPException:
            raise
        except Exception as exc:
            await log_tool_call(tenant.tenant_id, tool_name, "error")
            logger.error(f"Tool {tool_name} error: {exc}")
            raise HTTPException(status_code=500, detail=str(exc))

    raise HTTPException(status_code=400, detail=f"Unknown method: {method}")


async def _dispatch_tool(name: str, args: dict, tenant: TenantContext):
    if name == "research_trends":
        return await tool_research_trends(**args)
    if name == "scrape_competitor":
        return await tool_scrape_competitor(**args)
    if name == "generate_content":
        brief = ResearchBrief(**args["brief"]) if isinstance(args.get("brief"), dict) else args.get("brief")
        return await tool_generate_content(brief=brief, platform=args.get("platform", "linkedin"), product=args.get("product", "full_erp"), model=args.get("model", "google/gemini-2.5-flash"))
    if name == "generate_visual":
        content = PlatformContent(**args["content"]) if isinstance(args.get("content"), dict) else args.get("content")
        return await tool_generate_visual(content=content, template_id=args.get("template_id", "linkedin-single"), source=args.get("source", "template"))
    if name == "queue_post":
        return await tool_queue_post(tenant_id=tenant.tenant_id, **args)
    if name == "get_analytics":
        return await tool_get_analytics(**args)
    if name == "update_strategy":
        return await tool_update_strategy(tenant_id=tenant.tenant_id, changes=args.get("changes", {}))
    raise HTTPException(status_code=400, detail=f"Unknown tool: {name}")

# ── Tool implementations ───────────────────────────────────────────────────

async def tool_research_trends(topic: str, platform: str = "all") -> dict:
    perplexity_key = os.getenv("PERPLEXITY_API_KEY", "")
    if not perplexity_key:
        # Return mock data if key not configured
        return ResearchBrief(
            topic=topic,
            trending_angles=[f"How {topic} saves Pakistani SMBs 3+ hours/week", f"Common {topic} mistakes SMBs make"],
            pain_points=["Manual processes waste time", "Compliance errors cost money"],
            suggested_hooks=[f"Why 94% of Karachi businesses still struggle with {topic}"],
            platform_notes={"linkedin": "Educational angle works best", "twitter": "Short punchy stats"},
            generated_at=datetime.now(timezone.utc).isoformat(),
        ).model_dump()

    prompt = (
        f"Trending {topic} for {platform} social media Pakistan SMB 2026. "
        f"What pain points, hooks, and angles are working right now?"
    )
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.perplexity.ai/chat/completions",
            headers={"Authorization": f"Bearer {perplexity_key}"},
            json={
                "model": "sonar",
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]

    # Parse response into structured brief
    angles = [line.strip("- ").strip() for line in content.split("\n") if line.strip().startswith("-")][:5]
    if not angles:
        angles = [f"How {topic} transforms Pakistani SMB operations"]

    return ResearchBrief(
        topic=topic,
        trending_angles=angles[:5],
        pain_points=angles[5:8] if len(angles) > 5 else ["Manual processes", "Compliance burden"],
        suggested_hooks=[angles[0]] if angles else [f"Stop wasting time on {topic}"],
        platform_notes={"linkedin": "Educational", "twitter": "Stats-driven"},
        generated_at=datetime.now(timezone.utc).isoformat(),
    ).model_dump()


async def tool_scrape_competitor(platform: str, handle: str, limit: int = 20) -> list:
    apify_token = os.getenv("APIFY_API_TOKEN", "")
    actor_map = {
        "linkedin": "apify/linkedin-post-scraper",
        "twitter": "apidojo/tweet-scraper",
        "instagram": "apify/instagram-scraper",
    }
    actor = actor_map.get(platform)
    if not actor:
        raise HTTPException(status_code=400, detail=f"Unsupported platform: {platform}")
    if not apify_token:
        return []

    url_map = {
        "linkedin": f"https://www.linkedin.com/in/{handle}",
        "twitter": f"https://twitter.com/{handle}",
        "instagram": f"https://www.instagram.com/{handle}",
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items",
            headers={"Authorization": f"Bearer {apify_token}"},
            json={"startUrls": [{"url": url_map[platform]}], "maxItems": limit},
        )
        resp.raise_for_status()
        items = resp.json()

    return [
        CompetitorPost(
            platform=platform,
            handle=handle,
            text=item.get("text", item.get("content", "")),
            likes=item.get("likesCount", 0),
            comments=item.get("commentsCount", 0),
            shares=item.get("sharesCount", item.get("retweetCount", 0)),
            posted_at=str(item.get("timestamp", "")),
            url=item.get("url", ""),
        ).model_dump()
        for item in items
    ]


async def tool_generate_content(
    brief: ResearchBrief,
    platform: str,
    product: str = "full_erp",
    model: str = "google/gemini-2.5-flash",
) -> dict:
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")

    # Read brand voice
    brand_voice_path = "/app/config/brand_voice.md"
    brand_voice = ""
    try:
        with open(brand_voice_path) as f:
            brand_voice = f.read()
    except FileNotFoundError:
        brand_voice = "Write honest, direct content for Pakistani SMBs. No corporate buzzwords."

    char_limit = PLATFORM_CHAR_LIMITS.get(platform, 1300)
    platform_instructions = {
        "linkedin": f"Professional, insight-driven, educational tone. End with a question. Max {char_limit} characters.",
        "twitter": "Punchy, opinionated. Use line breaks. Max 4 tweets at 280 chars each. Thread format.",
        "instagram": "Visual-first caption, story-driven. 3-5 hashtags only.",
        "youtube": "60-second script. Hook in first 3 seconds. Problem→Solution→CTA.",
        "email": "Subject line + 150-word body. One CTA link.",
    }

    if not openrouter_key:
        # Return mock content if key not configured
        mock_copy = f"Pakistani SMBs are losing hours every week to manual {brief.topic}. OfferBerries changes that. Our HR module automates payroll, leave tracking, and compliance — starting at PKR 1,999/month. What's your biggest payroll headache right now?"
        return PlatformContent(
            platform=platform,
            copy=mock_copy[:char_limit],
            hashtags=["#OfferBerries", "#PakistanSMB", "#HRSoftware"],
            cta="Book a free demo today",
            estimated_reading_time=1,
            word_count=len(mock_copy.split()),
        ).model_dump()

    actual_model = "anthropic/claude-sonnet-4-6" if model == "premium" else model

    user_prompt = f"""Platform: {platform}
Platform instructions: {platform_instructions.get(platform, '')}
Topic: {brief.topic if isinstance(brief, ResearchBrief) else brief.get('topic','')}
Trending angles: {brief.trending_angles if isinstance(brief, ResearchBrief) else brief.get('trending_angles',[])}
Pain points: {brief.pain_points if isinstance(brief, ResearchBrief) else brief.get('pain_points',[])}
Suggested hooks: {brief.suggested_hooks if isinstance(brief, ResearchBrief) else brief.get('suggested_hooks',[])}
Product: {product}

Write the social media post copy. Return only the post copy, no explanations."""

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {openrouter_key}"},
            json={
                "model": actual_model,
                "max_tokens": 1000,
                "messages": [
                    {"role": "system", "content": brand_voice},
                    {"role": "user", "content": user_prompt},
                ],
            },
        )
        resp.raise_for_status()
        copy = resp.json()["choices"][0]["message"]["content"].strip()

    copy = copy[:char_limit]
    words = copy.split()
    return PlatformContent(
        platform=platform,
        copy=copy,
        hashtags=["#OfferBerries", "#PakistanSMB"],
        cta="Book a free demo",
        estimated_reading_time=max(1, len(words) // 200),
        word_count=len(words),
    ).model_dump()


async def tool_generate_visual(
    content: PlatformContent,
    template_id: str,
    source: str = "template",
) -> dict:
    platform = content.platform if isinstance(content, PlatformContent) else content.get("platform", "linkedin")
    copy = content.copy if isinstance(content, PlatformContent) else content.get("copy", "")
    width, height = PLATFORM_DIMS.get(platform, (1080, 1080))
    renderer_url = os.getenv("RENDERER_URL", "http://renderer:3001")
    od_url = os.getenv("OD_URL", "http://open-design:7456")
    od_token = os.getenv("OD_API_TOKEN", "")

    content_data = content.model_dump() if isinstance(content, PlatformContent) else content

    if source == "template":
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{renderer_url}/render",
                json={"template_id": template_id, "content_data": content_data, "width": width, "height": height},
            )
            resp.raise_for_status()
            filename = resp.headers.get("x-output-filename", f"{uuid.uuid4()}.png")
        return VisualAsset(
            path=f"/app/output/{filename}",
            url=f"{renderer_url}/output/{filename}",
            format="png",
            width=width,
            height=height,
            source="template",
            template_id=template_id,
        ).model_dump()

    if source == "open_design":
        async with httpx.AsyncClient(timeout=90) as client:
            od_resp = await client.post(
                f"{od_url}/api/generate",
                headers={"Authorization": f"Bearer {od_token}"},
                json={"prompt": copy, "skill": template_id, "design_system": "offerberries"},
            )
            od_resp.raise_for_status()
            od_data = od_resp.json()
            html_content = od_data.get("html", "")

        # Screenshot the OD output via renderer
        import base64
        html_b64 = base64.b64encode(html_content.encode()).decode()
        async with httpx.AsyncClient(timeout=60) as client:
            render_resp = await client.post(
                f"{renderer_url}/render",
                json={
                    "template_id": "_od_html_",
                    "content_data": {"__html_b64": html_b64},
                    "width": width,
                    "height": height,
                },
            )
            if render_resp.status_code == 200:
                filename = render_resp.headers.get("x-output-filename", f"{uuid.uuid4()}.png")
                return VisualAsset(
                    path=f"/app/output/{filename}",
                    url=f"{renderer_url}/output/{filename}",
                    format="png",
                    width=width,
                    height=height,
                    source="open_design",
                    template_id=template_id,
                ).model_dump()

        return VisualAsset(format="png", source="open_design", template_id=template_id).model_dump()

    if source == "fal":
        fal_key = os.getenv("FAL_API_KEY", "")
        size_map = {"linkedin": "square_hd", "twitter": "landscape_16_9", "instagram": "square_hd", "youtube": "landscape_16_9"}
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(
                "https://fal.run/fal-ai/flux/dev",
                headers={"Authorization": f"Key {fal_key}"},
                json={"prompt": f"Professional social media graphic: {copy[:200]}", "image_size": size_map.get(platform, "square_hd")},
            )
            resp.raise_for_status()
            data = resp.json()
            img_url = data.get("images", [{}])[0].get("url", "")

        filename = f"{uuid.uuid4()}.png"
        async with httpx.AsyncClient(timeout=30) as client:
            img_resp = await client.get(img_url)
        with open(f"/app/output/{filename}", "wb") as f:
            f.write(img_resp.content)

        return VisualAsset(
            path=f"/app/output/{filename}",
            url=f"{renderer_url}/output/{filename}",
            format="png",
            width=width,
            height=height,
            source="fal",
            template_id=template_id,
        ).model_dump()

    raise HTTPException(status_code=400, detail=f"Unknown source: {source}")


async def tool_queue_post(
    platform: str,
    caption: str,
    image_path: str,
    scheduled_at: str,
    tenant_id: str,
) -> dict:
    postiz_secret = os.getenv("POSTIZ_SECRET", "")
    postiz_url = os.getenv("POSTIZ_URL", "http://postiz:3000")

    mock_id = str(uuid.uuid4())
    if not postiz_secret:
        queued = QueuedPost(postiz_id=mock_id, platform=platform, scheduled_at=scheduled_at)
    else:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{postiz_url}/api/posts",
                headers={"Authorization": f"Bearer {postiz_secret}"},
                json={"content": caption, "date": scheduled_at, "platform": platform},
            )
            resp.raise_for_status()
            postiz_id = resp.json().get("id", mock_id)
        queued = QueuedPost(postiz_id=postiz_id, platform=platform, scheduled_at=scheduled_at)

    await db["posts"].insert_one({
        "tenant_id": tenant_id,
        "platform": platform,
        "caption_hash": hashlib.sha256(caption.encode()).hexdigest(),
        "postiz_id": queued.postiz_id,
        "scheduled_at": scheduled_at,
        "status": "queued",
        "created_at": datetime.now(timezone.utc),
    })

    return queued.model_dump()


async def tool_get_analytics(platform: str = "all", days: int = 7) -> dict:
    postiz_secret = os.getenv("POSTIZ_SECRET", "")
    postiz_url = os.getenv("POSTIZ_URL", "http://postiz:3000")

    if not postiz_secret:
        return AnalyticsReport(
            period_days=days,
            total_impressions=0,
            total_clicks=0,
            trend="flat",
            recommendations=["Connect your social accounts to start seeing analytics"],
        ).model_dump()

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{postiz_url}/api/analytics",
            headers={"Authorization": f"Bearer {postiz_secret}"},
            params={"days": days},
        )
        data = resp.json() if resp.status_code == 200 else {}

    return AnalyticsReport(
        period_days=days,
        total_impressions=data.get("totalImpressions", 0),
        total_clicks=data.get("totalClicks", 0),
        top_posts=data.get("topPosts", [])[:5],
        platform_breakdown=data.get("platformBreakdown", {}),
        trend=data.get("trend", "flat"),
        best_performing_template=data.get("bestTemplate", ""),
        best_performing_day=data.get("bestDay", ""),
        recommendations=data.get("recommendations", []),
    ).model_dump()


async def tool_update_strategy(tenant_id: str, changes: dict) -> dict:
    supabase_url = os.getenv("SUPABASE_URL", "")
    service_key = os.getenv("SUPABASE_SERVICE_KEY", "")
    if not supabase_url or not service_key:
        return StrategyDoc(tenant_id=tenant_id, **changes).model_dump()

    changes["tenant_id"] = tenant_id
    changes["updated_at"] = datetime.now(timezone.utc).isoformat()

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{supabase_url}/rest/v1/content_strategy",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
                "Prefer": "resolution=merge-duplicates",
            },
            json=changes,
        )
        result = resp.json() if resp.status_code in (200, 201) else changes

    if isinstance(result, list) and result:
        result = result[0]

    return StrategyDoc(**{k: v for k, v in result.items() if k in StrategyDoc.model_fields}).model_dump()

# ── Admin endpoints ────────────────────────────────────────────────────────

class CreateApiKeyRequest(BaseModel):
    tenant_id: str
    tier: str = "starter"
    label: str = ""

@app.post("/admin/api-keys")
async def create_api_key(
    req: CreateApiKeyRequest,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await get_tenant(x_api_key, authorization)
    if tenant.tier != "owner":
        raise HTTPException(status_code=403, detail="Owner only")

    raw_key = "ofb_" + req.tier + "_" + secrets.token_hex(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    await db["api_keys"].insert_one({
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


@app.post("/admin/tenants/demo")
async def create_demo_session(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    from datetime import timedelta
    session_id = str(uuid.uuid4())
    raw_key = f"ofb_demo_{secrets.token_hex(16)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=1800)

    await db["api_keys"].insert_one({
        "key_hash": key_hash,
        "key_prefix": "ofb_demo_",
        "tenant_id": f"demo_{session_id}",
        "tier": "demo",
        "session_id": session_id,
        "created_at": datetime.now(timezone.utc),
        "expires_at": expires_at,
        "revoked_at": None,
    })

    await redis_client.setex(
        f"demo:{session_id}",
        1800,
        json.dumps({"api_key_hash": key_hash, "created_at": datetime.now(timezone.utc).isoformat(), "expires_at": expires_at.isoformat()}),
    )

    import json as _json
    demo_url = f"https://agent.{os.getenv('DOMAIN', 'localhost')}/demo"
    return {
        "session_id": session_id,
        "api_key": raw_key,
        "expires_at": expires_at.isoformat(),
        "demo_url": demo_url,
    }


@app.delete("/admin/tenants/demo/{session_id}")
async def delete_demo_session(
    session_id: str,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await get_tenant(x_api_key, authorization)
    if tenant.tier != "owner":
        raise HTTPException(status_code=403, detail="Owner only")

    tenant_id = f"demo_{session_id}"
    await db["api_keys"].update_many(
        {"tenant_id": tenant_id},
        {"$set": {"revoked_at": datetime.now(timezone.utc)}},
    )
    await redis_client.delete(f"demo:{session_id}")
    # Invalidate any cached tenant contexts
    # (they'll expire naturally within 5 min)
    return {"deleted": True, "session_id": session_id}

# ── Payment webhooks ───────────────────────────────────────────────────────

import json
import hmac as _hmac

@app.post("/webhooks/safepay")
async def safepay_webhook(request: Request):
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


@app.post("/webhooks/2checkout")
async def twocheckout_webhook(request: Request):
    payload = await request.body()
    data = json.loads(payload)
    if data.get("MESSAGE_TYPE") == "ORDER_CREATED":
        logger.info("2Checkout ORDER_CREATED received")
    return {"received": True}


class CheckoutRequest(BaseModel):
    plan: str
    tenant_email: str

PLAN_PRICES = {"starter_pkr": 4999, "pro_pkr": 14999}

@app.post("/billing/checkout")
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

    return {"checkout_url": result.get("data", {}).get("redirect_url", f"https://sandbox.api.getsafepay.com/checkout")}
