import hashlib
import hmac
import json
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
from services.perplexity_client import PerplexityError, get_perplexity_client

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
        return await tool_generate_content(brief=brief, platform=args.get("platform", "linkedin"), product=args.get("product", "full_erp"), model=args.get("model", "google/gemini-2.5-flash"), tenant_id=tenant.tenant_id)
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

async def tool_research_trends(topic: str, platform: str = "all", model: str = "sonar") -> dict:
    """Research trending angles via Perplexity.

    Raises HTTPException with a typed error body on any failure — never
    returns mock/fallback data in production.
    """
    client = get_perplexity_client()
    try:
        result = await client.research(topic=topic, platform=platform, model=model)
    except PerplexityError as exc:
        logger.warning("Perplexity error [%s]: %s", exc.error_type, exc.message)
        raise HTTPException(
            status_code=503,
            detail=exc.to_dict(),
        )

    # Adapt ResearchResult → ResearchBrief shape expected by downstream nodes
    trends = result.trends
    trend_titles = [t["title"] for t in trends]
    return ResearchBrief(
        topic=topic,
        trending_angles=trend_titles[:5],
        pain_points=trend_titles[5:8] if len(trend_titles) > 5 else [],
        suggested_hooks=[trend_titles[0]] if trend_titles else [],
        platform_notes={
            "citations": json.dumps(result.citations),
            "model_used": result.model_used,
            "raw_trends": json.dumps(trends),
        },
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
    tenant_id: str = "",
) -> dict:
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")

    # Load tenant-specific brand voice from MongoDB, fall back to file
    brand_voice = ""
    if tenant_id:
        doc = await db["configs"].find_one({"tenant_id": tenant_id, "key": "brand_voice"}, {"_id": 0})
        if doc:
            brand_voice = doc.get("value", "")
    if not brand_voice:
        try:
            with open("/app/config/brand_voice.md") as f:
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
        # No key — return empty rather than fake data so callers know generation failed
        logger.warning("OPENROUTER_API_KEY not set — content generation unavailable")
        raise HTTPException(status_code=503, detail="Content generation API key not configured")

    actual_model = "anthropic/claude-sonnet-4-6" if model == "premium" else model

    topic_str = brief.topic if isinstance(brief, ResearchBrief) else brief.get("topic", "")
    angles = brief.trending_angles if isinstance(brief, ResearchBrief) else brief.get("trending_angles", [])
    pain_points = brief.pain_points if isinstance(brief, ResearchBrief) else brief.get("pain_points", [])
    hooks = brief.suggested_hooks if isinstance(brief, ResearchBrief) else brief.get("suggested_hooks", [])

    hashtag_rules = {
        "linkedin": "3–5 hashtags: mix 2 broad professional + 2–3 niche topic-specific. No more than 5 total.",
        "twitter": "2–4 hashtags only. Short and trending.",
        "instagram": "7–10 hashtags: mix broad discovery + niche topic + location-relevant.",
        "youtube": "3–5 hashtags for the description.",
        "email": "No hashtags.",
    }.get(platform, "3–5 topic-relevant hashtags.")

    cta_rules = (
        "Generate the most appropriate CTA for this content type:\n"
        "- Educational/how-to content → 'Learn more', 'Read the guide', or an engagement question\n"
        "- Pain-point content → 'See how we solve this', 'Fix this today'\n"
        "- Product announcement → 'Read the full story', 'See what's new'\n"
        "- Explicit product pitch → 'Book a free demo', 'Start your free trial'\n"
        "Do NOT default to a demo CTA unless the content is explicitly pitching a product."
    )

    user_prompt = f"""Platform: {platform}
Platform instructions: {platform_instructions.get(platform, '')}
Topic: {topic_str}
Trending angles: {angles}
Pain points: {pain_points}
Suggested hooks: {hooks}
Product: {product}

Hashtag rules: {hashtag_rules}
Hashtag content requirements:
- Specific to the topic — not generic brand tags
- Pakistan SMB context where naturally relevant, not forced
- Mix broad (reach) and niche (relevance) tags

CTA rules:
{cta_rules}

Return your response as valid JSON with exactly this structure (no markdown, no extra keys):
{{
    "copy": "the full social media post copy here (no hashtags inline — keep them separate)",
    "hashtags": ["#TopicHashtag1", "#TopicHashtag2"],
    "cta": "the call to action text"
}}"""

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {openrouter_key}"},
            json={
                "model": actual_model,
                "max_tokens": 1200,
                "messages": [
                    {"role": "system", "content": brand_voice},
                    {"role": "user", "content": user_prompt},
                ],
            },
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()

    copy, hashtags, cta = _parse_content_response(raw, topic_str, platform)
    copy = copy[:char_limit]
    words = copy.split()
    return PlatformContent(
        platform=platform,
        copy=copy,
        hashtags=hashtags,
        cta=cta,
        estimated_reading_time=max(1, len(words) // 200),
        word_count=len(words),
    ).model_dump()


def _parse_content_response(raw: str, topic: str, platform: str) -> tuple[str, list[str], str]:
    """Parse LLM JSON response into (copy, hashtags, cta).

    Falls back to regex extraction if JSON parsing fails, so the pipeline
    never hard-stops on a non-JSON response.
    """
    # Strip markdown code fences if present
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("```").strip()

    try:
        parsed = json.loads(cleaned)
        copy = str(parsed.get("copy", raw))
        hashtags = [str(h) for h in parsed.get("hashtags", []) if str(h).startswith("#")]
        cta = str(parsed.get("cta", ""))
        return copy, hashtags, cta
    except (json.JSONDecodeError, TypeError):
        logger.warning("Content response was not valid JSON — falling back to regex extraction")
        hashtags = re.findall(r"#\w+", raw)
        # Remove hashtags from copy body
        copy = re.sub(r"#\w+", "", raw).strip()
        return copy, hashtags, ""


def _renderer_public_url(filename: str, renderer_url: str) -> str:
    """Return a browser-accessible URL for a rendered PNG."""
    domain = os.getenv("DOMAIN", "")
    if domain and domain != "localhost":
        return f"https://agent.{domain}/render-output/{filename}"
    return f"{renderer_url}/output/{filename}"


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
            url=_renderer_public_url(filename, renderer_url),
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
                    url=_renderer_public_url(filename, renderer_url),
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
            url=_renderer_public_url(filename, renderer_url),
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
    preview_url: str = "",
) -> dict:
    postiz_secret = os.getenv("POSTIZ_SECRET", "")
    postiz_url = os.getenv("POSTIZ_URL", "http://postiz:3000")

    mock_id = str(uuid.uuid4())
    if not postiz_secret:
        queued = QueuedPost(postiz_id=mock_id, platform=platform, scheduled_at=scheduled_at, preview_url=preview_url)
    else:
        postiz_id = mock_id
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{postiz_url}/api/posts",
                    headers={"Authorization": f"Bearer {postiz_secret}"},
                    json={"content": caption, "date": scheduled_at, "platform": platform},
                )
                if resp.status_code < 400:
                    postiz_id = resp.json().get("id", mock_id)
                else:
                    logger.warning(f"Postiz returned {resp.status_code}, using mock ID")
        except Exception as e:
            logger.warning(f"Postiz unavailable: {e}, using mock ID")
        queued = QueuedPost(postiz_id=postiz_id, platform=platform, scheduled_at=scheduled_at, preview_url=preview_url)

    await db["posts"].insert_one({
        "tenant_id": tenant_id,
        "platform": platform,
        "caption": caption,
        "caption_hash": hashlib.sha256(caption.encode()).hexdigest(),
        "postiz_id": queued.postiz_id,
        "preview_url": preview_url,
        "scheduled_at": scheduled_at,
        "status": "queued",
        "created_at": datetime.now(timezone.utc),
    })

    return queued.model_dump()


async def tool_get_analytics(platform: str = "all", days: int = 7, tenant_id: str = "", db_ref=None) -> dict:
    from datetime import timedelta

    _db = db_ref if db_ref is not None else db

    # Read from MongoDB — always available regardless of Postiz connection
    mongo_breakdown: dict = {}
    mongo_top: list = []
    total_queued = 0
    total_approved = 0

    if _db is not None and tenant_id:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        query: dict = {"tenant_id": tenant_id, "created_at": {"$gte": cutoff}}
        if platform != "all":
            query["platform"] = platform
        cursor = _db["posts"].find(query, {"_id": 0}).sort("created_at", -1).limit(200)
        posts = await cursor.to_list(length=200)
        for p in posts:
            plat = p.get("platform", "unknown")
            status = p.get("status", "queued")
            if status == "queued":
                total_queued += 1
            elif status == "approved":
                total_approved += 1
            entry = mongo_breakdown.setdefault(plat, {"impressions": 0, "clicks": 0, "posts": 0, "engagement_rate": 0.0})
            entry["posts"] += 1
        mongo_top = [
            {"postiz_id": p.get("postiz_id", ""), "platform": p.get("platform", ""), "impressions": 0, "clicks": 0, "status": p.get("status", ""), "caption": p.get("caption", "")[:120]}
            for p in posts[:5]
        ]

    # Try Postiz for real impression/click data
    postiz_secret = os.getenv("POSTIZ_SECRET", "")
    postiz_url = os.getenv("POSTIZ_URL", "http://postiz:3000")
    postiz_data: dict = {}
    if postiz_secret:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{postiz_url}/api/analytics",
                    headers={"Authorization": f"Bearer {postiz_secret}"},
                    params={"days": days},
                )
                if resp.status_code == 200:
                    postiz_data = resp.json()
        except Exception:
            pass

    total_impressions = postiz_data.get("totalImpressions", 0)
    total_clicks = postiz_data.get("totalClicks", 0)
    top_posts = postiz_data.get("topPosts", mongo_top)[:5]
    platform_breakdown = postiz_data.get("platformBreakdown", mongo_breakdown)
    trend = postiz_data.get("trend", "growing" if total_queued > 0 else "flat")
    best_template = postiz_data.get("bestTemplate", "linkedin-single")
    best_day = postiz_data.get("bestDay", "")

    recs: list[str] = postiz_data.get("recommendations", [])
    if not recs:
        if total_queued > 0:
            recs = [
                f"{total_queued} post(s) queued, {total_approved} approved in the last {days} days.",
                "Connect your LinkedIn and Instagram accounts in Postiz to start publishing.",
                "Approve queued posts in the Queue page to schedule them.",
            ]
        else:
            recs = [
                "No posts generated yet. Click 'Run Agent' in the Queue page with a topic.",
                "Connect your social accounts in Settings → Manage in Postiz.",
            ]

    return AnalyticsReport(
        period_days=days,
        total_impressions=total_impressions,
        total_clicks=total_clicks,
        top_posts=top_posts,
        platform_breakdown=platform_breakdown,
        trend=trend,
        best_performing_template=best_template,
        best_performing_day=best_day,
        recommendations=recs,
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

    strategy = StrategyDoc(**{k: v for k, v in result.items() if k in StrategyDoc.model_fields}).model_dump()

    # Mirror to MongoDB for fast reads via GET /config/strategy
    await db["configs"].update_one(
        {"tenant_id": tenant_id, "key": "strategy"},
        {"$set": {"value": strategy, "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return strategy

# ── REST queue endpoints ───────────────────────────────────────────────────

@app.get("/queue")
async def rest_get_queue(
    platform: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await get_tenant(x_api_key, authorization)
    query: dict = {"tenant_id": tenant.tenant_id}
    if platform and platform != "all":
        query["platform"] = platform
    if status:
        query["status"] = status
    cursor = db["posts"].find(query, {"_id": 0}).sort("created_at", -1).limit(limit)
    posts = await cursor.to_list(length=limit)
    for p in posts:
        if "created_at" in p:
            p["created_at"] = p["created_at"].isoformat() if hasattr(p["created_at"], "isoformat") else str(p["created_at"])
    return posts


@app.post("/queue/{post_id}/approve")
async def rest_approve_post(
    post_id: str,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await get_tenant(x_api_key, authorization)
    result = await db["posts"].update_one(
        {"postiz_id": post_id, "tenant_id": tenant.tenant_id},
        {"$set": {"status": "approved", "approved_at": datetime.now(timezone.utc)}},
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"approved": True, "post_id": post_id}


@app.delete("/queue/{post_id}")
async def rest_delete_post(
    post_id: str,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await get_tenant(x_api_key, authorization)
    result = await db["posts"].delete_one(
        {"postiz_id": post_id, "tenant_id": tenant.tenant_id}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"deleted": True, "post_id": post_id}


@app.post("/render")
async def render_template(
    request: Request,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    await get_tenant(x_api_key, authorization)
    renderer_url = os.getenv("RENDERER_URL", "http://renderer:3001")
    body = await request.body()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{renderer_url}/render",
            content=body,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
    from fastapi.responses import Response as FastAPIResponse
    return FastAPIResponse(content=resp.content, media_type="image/png")


@app.get("/analytics")
async def rest_get_analytics(
    platform: str = "all",
    days: int = 7,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await get_tenant(x_api_key, authorization)
    return await tool_get_analytics(platform=platform, days=days, tenant_id=tenant.tenant_id)


# ── Config endpoints ──────────────────────────────────────────────────────

class BrandVoiceRequest(BaseModel):
    content: str

@app.get("/config/brand-voice")
async def get_brand_voice(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await get_tenant(x_api_key, authorization)
    doc = await db["configs"].find_one(
        {"tenant_id": tenant.tenant_id, "key": "brand_voice"}, {"_id": 0}
    )
    if doc:
        return {"content": doc.get("value", ""), "updated_at": str(doc.get("updated_at", ""))}
    try:
        with open("/app/config/brand_voice.md") as f:
            content = f.read()
    except FileNotFoundError:
        content = "Write honest, direct content for Pakistani SMBs. No corporate buzzwords."
    return {"content": content, "updated_at": ""}


@app.put("/config/brand-voice")
async def put_brand_voice(
    req: BrandVoiceRequest,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await get_tenant(x_api_key, authorization)
    await db["configs"].update_one(
        {"tenant_id": tenant.tenant_id, "key": "brand_voice"},
        {"$set": {"value": req.content, "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return {"saved": True}


@app.get("/config/strategy")
async def get_strategy(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await get_tenant(x_api_key, authorization)
    doc = await db["configs"].find_one(
        {"tenant_id": tenant.tenant_id, "key": "strategy"}, {"_id": 0}
    )
    if doc:
        data = doc.get("value", {})
        return StrategyDoc(**{k: v for k, v in data.items() if k in StrategyDoc.model_fields}).model_dump()
    return StrategyDoc(tenant_id=tenant.tenant_id).model_dump()


# ── Admin endpoints ────────────────────────────────────────────────────────

class CreateApiKeyRequest(BaseModel):
    tenant_id: str
    tier: str = "starter"
    label: str = ""

@app.get("/admin/api-keys")
async def list_api_keys(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await get_tenant(x_api_key, authorization)
    if tenant.tier != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    cursor = db["api_keys"].find({"revoked_at": None}, {"_id": 0, "key_hash": 0}).sort("created_at", -1).limit(100)
    keys = await cursor.to_list(length=100)
    for k in keys:
        for field in ("created_at", "last_used_at"):
            if k.get(field) and hasattr(k[field], "isoformat"):
                k[field] = k[field].isoformat()
    return keys


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


# ── Account endpoints ──────────────────────────────────────────────────────

@app.get("/account")
async def get_account(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await get_tenant(x_api_key, authorization)
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


# ── Usage endpoints ────────────────────────────────────────────────────────

from auth import TIER_LIMITS

@app.get("/usage")
async def get_usage(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await get_tenant(x_api_key, authorization)
    today = _today()
    limits = TIER_LIMITS.get(tenant.tier, TIER_LIMITS["starter"])

    tool_usage = {}
    for tool_name, limit in limits.items():
        rl_key = f"ratelimit:{tenant.tenant_id}:{tool_name}:{today}"
        count_str = await redis_client.get(rl_key)
        used = int(count_str) if count_str else 0
        tool_usage[tool_name] = {"used": used, "limit": limit}

    # Next reset at midnight UTC
    from datetime import timedelta
    now_utc = datetime.now(timezone.utc)
    reset_at = (now_utc + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    # Vendor credit: OpenRouter balance (best-effort)
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
                    openrouter_data["monthly_spend_usd"]  = float(data.get("usage", 0) or 0) / 1_000_000
        except Exception:
            pass

    perplexity_data = {"requests_used": 0, "requests_limit": 100, "reset_at": reset_at.isoformat()}
    apify_data      = {"compute_units_used": 0, "compute_units_limit": 500, "reset_at": reset_at.isoformat()}

    # Count today's tool calls from MongoDB for vendor usage estimate
    try:
        pipeline = [
            {"$match": {"tenant_id": tenant.tenant_id, "recorded_at": {"$gte": now_utc.replace(hour=0, minute=0, second=0, microsecond=0)}}},
            {"$group": {"_id": "$tool_name", "count": {"$sum": 1}}},
        ]
        cursor = db["tool_calls"].aggregate(pipeline)
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


# ── Models endpoints ───────────────────────────────────────────────────────

OPENROUTER_MODELS = [
    # Fast
    {"id": "google/gemini-2.5-flash", "name": "Gemini 2.5 Flash", "tier": "fast", "context_length": 1_000_000, "pricing": {"prompt": "0.075", "completion": "0.30"}, "description": "Fast and cost-effective, great for drafts"},
    {"id": "meta-llama/llama-3.1-8b-instruct:free", "name": "Llama 3.1 8B (Free)", "tier": "fast", "context_length": 131_072, "pricing": {"prompt": "0", "completion": "0"}, "description": "Free tier, limited quality"},
    {"id": "mistralai/mistral-7b-instruct:free", "name": "Mistral 7B (Free)", "tier": "fast", "context_length": 32_768, "pricing": {"prompt": "0", "completion": "0"}, "description": "Free, good for simple tasks"},
    # Balanced
    {"id": "google/gemini-2.5-pro", "name": "Gemini 2.5 Pro", "tier": "balanced", "context_length": 1_000_000, "pricing": {"prompt": "1.25", "completion": "10.00"}, "description": "Excellent reasoning and long context"},
    {"id": "anthropic/claude-haiku-4-5", "name": "Claude Haiku 4.5", "tier": "balanced", "context_length": 200_000, "pricing": {"prompt": "0.80", "completion": "4.00"}, "description": "Fast Claude with strong instruction following"},
    {"id": "openai/gpt-4o-mini", "name": "GPT-4o Mini", "tier": "balanced", "context_length": 128_000, "pricing": {"prompt": "0.15", "completion": "0.60"}, "description": "Efficient OpenAI model for content tasks"},
    # Premium
    {"id": "anthropic/claude-sonnet-4-6", "name": "Claude Sonnet 4.6", "tier": "premium", "context_length": 200_000, "pricing": {"prompt": "3.00", "completion": "15.00"}, "description": "Best for nuanced content and brand voice"},
    {"id": "openai/gpt-4o", "name": "GPT-4o", "tier": "premium", "context_length": 128_000, "pricing": {"prompt": "5.00", "completion": "15.00"}, "description": "OpenAI flagship, best overall quality"},
    {"id": "google/gemini-2.5-pro-preview", "name": "Gemini 2.5 Pro Preview", "tier": "premium", "context_length": 1_000_000, "pricing": {"prompt": "3.50", "completion": "10.50"}, "description": "Latest Google frontier model"},
]

@app.get("/models/available")
async def get_models(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    await get_tenant(x_api_key, authorization)
    return OPENROUTER_MODELS


@app.get("/config/content-model")
async def get_content_model(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await get_tenant(x_api_key, authorization)
    doc = await db["configs"].find_one({"tenant_id": tenant.tenant_id, "key": "content_model"}, {"_id": 0})
    model_id = doc["value"] if doc else "google/gemini-2.5-flash"
    return {"model_id": model_id}


class ContentModelRequest(BaseModel):
    model_id: str

@app.put("/config/content-model")
async def put_content_model(
    req: ContentModelRequest,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await get_tenant(x_api_key, authorization)
    await db["configs"].update_one(
        {"tenant_id": tenant.tenant_id, "key": "content_model"},
        {"$set": {"value": req.model_id, "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return {"saved": True, "model_id": req.model_id}
