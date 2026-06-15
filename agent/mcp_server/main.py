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
    await _seed_research_models()


async def _seed_research_models() -> None:
    """Seed research_models collection on first boot if empty."""
    if db is None:
        return
    count = await db["research_models"].count_documents({})
    if count == 0:
        await db["research_models"].insert_many(RESEARCH_MODELS_SEED)
        logger.info("Seeded %d research models", len(RESEARCH_MODELS_SEED))


async def _seed_voice_profiles_for_tenant(tenant_id: str) -> None:
    """Seed default voice profiles for a tenant if they have none."""
    count = await db["voice_profiles"].count_documents({"tenant_id": tenant_id})
    if count == 0:
        now = datetime.now(timezone.utc)
        docs = [
            {**p, "id": str(uuid.uuid4()), "tenant_id": tenant_id, "is_active": True, "created_at": now}
            for p in DEFAULT_VOICE_PROFILES
        ]
        await db["voice_profiles"].insert_many(docs)
        logger.info("Seeded %d voice profiles for tenant %s", len(docs), tenant_id)


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

# ── Pricing tables (used for cost tracking) ───────────────────────────────

OPENROUTER_PRICING: dict[str, tuple[float, float]] = {
    # (prompt_per_1M_usd, completion_per_1M_usd)
    "google/gemini-2.5-flash":                  (0.075, 0.30),
    "meta-llama/llama-3.1-8b-instruct:free":    (0.0,   0.0),
    "mistralai/mistral-7b-instruct:free":        (0.0,   0.0),
    "google/gemini-2.5-pro":                    (1.25,  10.00),
    "anthropic/claude-haiku-4-5":               (0.80,  4.00),
    "openai/gpt-4o-mini":                       (0.15,  0.60),
    "anthropic/claude-sonnet-4-6":              (3.00,  15.00),
    "openai/gpt-4o":                            (5.00,  15.00),
    "google/gemini-2.5-pro-preview":            (3.50,  10.50),
}

PERPLEXITY_COSTS: dict[str, float] = {
    "sonar":                0.0014,
    "sonar-pro":            0.004,
    "sonar-deep-research":  0.056,
    "sonar-reasoning":      0.005,
}


def _compute_openrouter_cost(model_id: str, prompt_tokens: int, completion_tokens: int) -> float:
    prompt_price, completion_price = OPENROUTER_PRICING.get(model_id, (0.0, 0.0))
    return round(
        (prompt_tokens * prompt_price + completion_tokens * completion_price) / 1_000_000, 8
    )


# ── Extended Pydantic models ───────────────────────────────────────────────

class VoiceProfile(BaseModel):
    tone: str = "professional"
    personality: str = ""
    writing_style: str = ""
    avoid_phrases: list[str] = []
    platform_overrides: dict[str, str] = {}
    example_ctas: list[str] = []


class VoiceProfileDoc(BaseModel):
    id: str = ""
    tenant_id: str = ""
    name: str
    is_default: bool = False
    system_prompt: Optional[str] = None
    hashtag_style: str = "contextual"   # branded|contextual|educational|discovery
    cta_type: str = "contextual"        # demo|learn_more|engagement|contextual
    tone: str = "adaptive"
    is_active: bool = True


class VoiceProfileCreateRequest(BaseModel):
    name: str
    system_prompt: Optional[str] = None
    hashtag_style: str = "contextual"
    cta_type: str = "contextual"
    tone: str = "adaptive"
    is_default: bool = False


class VoiceProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    system_prompt: Optional[str] = None
    hashtag_style: Optional[str] = None
    cta_type: Optional[str] = None
    tone: Optional[str] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None


class ResearchModel(BaseModel):
    id: str
    display_name: str
    provider: str = "perplexity"
    cost_usd_per_call: float
    credits_per_call: int
    tier_required: str   # free|starter|pro
    is_active: bool = True


class ResearchModelPatch(BaseModel):
    display_name: Optional[str] = None
    cost_usd_per_call: Optional[float] = None
    credits_per_call: Optional[int] = None
    tier_required: Optional[str] = None
    is_active: Optional[bool] = None


class VisualBrief(BaseModel):
    headline: str = ""
    subtext: str = ""
    visual_mood: str = "professional, clean"
    color_directive: str = ""
    layout_hint: str = "announcement"


class TemplateDoc(BaseModel):
    template_id: str
    name: str
    platform: str
    thumbnail_url: str = ""
    preview_url: str = ""
    is_default: bool = False
    layout_tags: list[str] = []
    html_content: str = ""
    variables: list[str] = []


class TemplateUploadRequest(BaseModel):
    template_id: str
    name: str
    platform: str
    html_content: str
    thumbnail_url: str = ""
    layout_tags: list[str] = []


# ── Seed data ──────────────────────────────────────────────────────────────

RESEARCH_MODELS_SEED: list[dict] = [
    {
        "id": "sonar", "display_name": "Sonar (Standard)", "provider": "perplexity",
        "cost_usd_per_call": 0.0014, "credits_per_call": 1, "tier_required": "free", "is_active": True,
    },
    {
        "id": "sonar-pro", "display_name": "Sonar Pro", "provider": "perplexity",
        "cost_usd_per_call": 0.004, "credits_per_call": 4, "tier_required": "starter", "is_active": True,
    },
    {
        "id": "sonar-deep-research", "display_name": "Deep Research", "provider": "perplexity",
        "cost_usd_per_call": 0.056, "credits_per_call": 56, "tier_required": "pro", "is_active": True,
    },
]

DEFAULT_VOICE_PROFILES: list[dict] = [
    {
        "name": "General / Adaptive", "is_default": True,
        "system_prompt": None, "hashtag_style": "contextual", "cta_type": "contextual", "tone": "adaptive",
    },
    {
        "name": "OfferBerries Official", "is_default": False,
        "system_prompt": (
            "You are writing for OfferBerries, a Pakistani B2B SaaS company. "
            "Be professional, honest, and direct. Focus on real ROI for SMBs. "
            "Never use corporate buzzwords."
        ),
        "hashtag_style": "branded", "cta_type": "demo", "tone": "professional",
    },
]

TIER_ORDER: dict[str, int] = {"free": 0, "starter": 1, "pro": 2}
HASHTAG_STYLE_VALUES = {"branded", "contextual", "educational", "discovery"}
CTA_TYPE_VALUES = {"demo", "learn_more", "engagement", "contextual"}


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
                {"name": "research_trends",      "description": "Research trending topics on social media"},
                {"name": "scrape_competitor",    "description": "Scrape competitor posts via Apify"},
                {"name": "generate_content",     "description": "Generate platform-specific content copy"},
                {"name": "generate_visual_brief","description": "LLM-driven visual art direction brief"},
                {"name": "generate_visual",      "description": "Render a visual asset from a template"},
                {"name": "queue_post",           "description": "Queue a post in Postiz for scheduling"},
                {"name": "get_analytics",        "description": "Retrieve analytics from Postiz"},
                {"name": "update_strategy",      "description": "Update the weekly content strategy doc"},
            ]
        }

    if method == "tools/call":
        tool_name = params.get("name", "")
        args = params.get("arguments", {})
        run_id = args.pop("__run_id", "")  # injected by graph.py, not a real tool arg
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
        return await tool_research_trends(run_id=run_id, tenant_id=tenant.tenant_id, **args)
    if name == "scrape_competitor":
        return await tool_scrape_competitor(**args)
    if name == "generate_content":
        brief = ResearchBrief(**args["brief"]) if isinstance(args.get("brief"), dict) else args.get("brief")
        return await tool_generate_content(
            brief=brief,
            platform=args.get("platform", "linkedin"),
            product=args.get("product", "full_erp"),
            model=args.get("model", "google/gemini-2.5-flash"),
            tenant_id=tenant.tenant_id,
            run_id=run_id,
        )
    if name == "generate_visual_brief":
        return await tool_generate_visual_brief(
            brief=args.get("brief", {}),
            content=args.get("content", {}),
            platform=args.get("platform", "linkedin"),
            brand_context=args.get("brand_context", {}),
            run_id=run_id,
            tenant_id=tenant.tenant_id,
        )
    if name == "generate_visual":
        content = PlatformContent(**args["content"]) if isinstance(args.get("content"), dict) else args.get("content")
        return await tool_generate_visual(
            content=content,
            template_id=args.get("template_id", "linkedin-single"),
            source=args.get("source", "template"),
            visual_brief=args.get("visual_brief"),
        )
    if name == "queue_post":
        return await tool_queue_post(tenant_id=tenant.tenant_id, **args)
    if name == "get_analytics":
        return await tool_get_analytics(**args)
    if name == "update_strategy":
        return await tool_update_strategy(tenant_id=tenant.tenant_id, changes=args.get("changes", {}))
    raise HTTPException(status_code=400, detail=f"Unknown tool: {name}")

# ── Tool implementations ───────────────────────────────────────────────────

async def tool_research_trends(
    topic: str,
    platform: str = "all",
    model: str = "sonar",
    recency_filter: str = "week",
    run_id: str = "",
    tenant_id: str = "",
) -> dict:
    """Research trending angles via Perplexity.

    Raises HTTPException with a typed error body on any failure — never
    returns mock/fallback data in production.
    """
    client = get_perplexity_client()
    try:
        result = await client.research(topic=topic, platform=platform, model=model)
    except PerplexityError as exc:
        logger.warning("Perplexity error [%s]: %s", exc.error_type, exc.message)
        await log_tool_call(
            tenant_id=tenant_id, tool_name="research_trends", status="error",
            run_id=run_id, provider="perplexity", model=model,
        )
        raise HTTPException(status_code=503, detail=exc.to_dict())

    cost_usd = PERPLEXITY_COSTS.get(model, PERPLEXITY_COSTS["sonar"])
    await log_tool_call(
        tenant_id=tenant_id, tool_name="research_trends", status="success",
        run_id=run_id, provider="perplexity", model=model, cost_usd=cost_usd,
    )

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
            "recency_filter": recency_filter,
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


def build_content_prompt(
    topic_str: str,
    angles: list,
    pain_points: list,
    hooks: list,
    platform: str,
    product: str,
    voice: Optional[VoiceProfileDoc],
    extra_context: str = "",
) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) using voice profile enums."""
    char_limit = PLATFORM_CHAR_LIMITS.get(platform, 1300)

    hashtag_style_rules: dict[str, str] = {
        "branded": "Use OfferBerries brand hashtags + 2-3 niche topic-specific tags.",
        "contextual": "Mix 2 broad professional + 2-3 niche topic-specific hashtags. Contextual to post.",
        "educational": "Use educational/how-to hashtags: #TipsFor{topic}, #LearnAbout, etc.",
        "discovery": "Use high-volume discovery hashtags (reach > niche). Max 10 on Instagram, 3 elsewhere.",
    }
    cta_type_rules: dict[str, str] = {
        "demo": "End with a clear product demo CTA: 'Book a free demo', 'Start your free trial'.",
        "learn_more": "End with 'Learn more', 'Read the full guide', or link to a resource.",
        "engagement": "End with an engagement question to spark comments. No product push.",
        "contextual": (
            "Pick the most appropriate CTA: educational → question/link; "
            "pain-point → 'See how we solve this'; product pitch → 'Book a demo'."
        ),
    }

    hs = (voice.hashtag_style if voice else "contextual") or "contextual"
    ct = (voice.cta_type if voice else "contextual") or "contextual"
    hashtag_rule = hashtag_style_rules.get(hs, hashtag_style_rules["contextual"])
    cta_rule = cta_type_rules.get(ct, cta_type_rules["contextual"])

    platform_instructions: dict[str, str] = {
        "linkedin": f"Professional, insight-driven, educational tone. End with a question. Max {char_limit} chars.",
        "twitter": "Punchy, opinionated. Use line breaks. Max 4 tweets at 280 chars each. Thread format.",
        "instagram": "Visual-first caption, story-driven.",
        "youtube": "60-second script. Hook in first 3 seconds. Problem→Solution→CTA.",
        "email": "Subject line + 150-word body. One CTA link.",
    }

    if voice and voice.system_prompt:
        system_prompt = voice.system_prompt
    else:
        tone = voice.tone if voice else "professional"
        system_prompt = (
            f"You write social media content for Pakistani SMBs. Tone: {tone}. "
            "Be honest and direct. Avoid corporate buzzwords."
        )

    user_prompt = (
        f"Platform: {platform}\n"
        f"Platform instructions: {platform_instructions.get(platform, '')}\n"
        f"Topic: {topic_str}\n"
        f"Trending angles: {angles}\n"
        f"Pain points: {pain_points}\n"
        f"Suggested hooks: {hooks}\n"
        f"Product: {product}\n"
        + (f"Extra context: {extra_context}\n" if extra_context else "")
        + f"\nHashtag rules: {hashtag_rule}\n"
        f"CTA rules: {cta_rule}\n\n"
        "Return your response as valid JSON with exactly this structure (no markdown, no extra keys):\n"
        '{\n'
        '    "copy": "the full social media post copy here (no hashtags inline — keep them separate)",\n'
        '    "hashtags": ["#TopicHashtag1", "#TopicHashtag2"],\n'
        '    "cta": "the call to action text"\n'
        '}'
    )
    return system_prompt, user_prompt


def build_flux_prompt(visual_brief: VisualBrief, platform: str, brand_colors: Optional[list[str]] = None) -> str:
    """Build a detailed Flux image generation prompt from a visual brief."""
    colors = brand_colors or ["#4F46E5 indigo", "#FFFFFF white"]
    color_str = ", ".join(colors[:3])
    negative = (
        "ugly, blurry, watermark, text errors, cluttered, stock photo, people, faces, "
        "low quality, distorted, nsfw"
    )
    dims = PLATFORM_DIMS.get(platform, (1080, 1080))
    aspect = "square" if dims[0] == dims[1] else "landscape 16:9"

    prompt = (
        f"Professional {visual_brief.layout_hint} social media graphic, {aspect} format. "
        f'Large headline text: "{visual_brief.headline}". '
        f'Supporting text: "{visual_brief.subtext}". '
        f"Color palette: {color_str}. "
        f"{visual_brief.color_directive}. "
        f"Style: {visual_brief.visual_mood}. "
        "Clean modern corporate design. Minimalist. No stock photos. No random people. "
        f"Optimised for {platform}. "
        f"NEGATIVE PROMPT — exclude: {negative}."
    )
    return prompt


async def tool_generate_content(
    brief: ResearchBrief,
    platform: str,
    product: str = "full_erp",
    model: str = "google/gemini-2.5-flash",
    tenant_id: str = "",
    run_id: str = "",
) -> dict:
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
    if not openrouter_key:
        logger.warning("OPENROUTER_API_KEY not set — content generation unavailable")
        raise HTTPException(status_code=503, detail="Content generation API key not configured")

    # Load active VoiceProfileDoc from voice_profiles collection (default profile)
    voice_doc: Optional[VoiceProfileDoc] = None
    if tenant_id:
        await _seed_voice_profiles_for_tenant(tenant_id)
        vp_raw = await db["voice_profiles"].find_one(
            {"tenant_id": tenant_id, "is_default": True, "is_active": True}
        )
        if not vp_raw:
            vp_raw = await db["voice_profiles"].find_one({"tenant_id": tenant_id, "is_active": True})
        if vp_raw:
            vp_raw.pop("_id", None)
            try:
                voice_doc = VoiceProfileDoc(**vp_raw)
            except Exception:
                pass

    char_limit = PLATFORM_CHAR_LIMITS.get(platform, 1300)
    actual_model = "anthropic/claude-sonnet-4-6" if model == "premium" else model

    topic_str = brief.topic if isinstance(brief, ResearchBrief) else brief.get("topic", "")
    angles = brief.trending_angles if isinstance(brief, ResearchBrief) else brief.get("trending_angles", [])
    pain_points = brief.pain_points if isinstance(brief, ResearchBrief) else brief.get("pain_points", [])
    hooks = brief.suggested_hooks if isinstance(brief, ResearchBrief) else brief.get("suggested_hooks", [])

    system_prompt, user_prompt = build_content_prompt(
        topic_str=topic_str, angles=angles, pain_points=pain_points, hooks=hooks,
        platform=platform, product=product, voice=voice_doc,
    )

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {openrouter_key}"},
            json={
                "model": actual_model,
                "max_tokens": 1200,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
        )
        resp.raise_for_status()
        resp_body = resp.json()
        raw = resp_body["choices"][0]["message"]["content"].strip()

    # Capture real token usage and compute cost
    usage = resp_body.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    cost_usd = _compute_openrouter_cost(actual_model, prompt_tokens, completion_tokens)
    await log_tool_call(
        tenant_id=tenant_id, tool_name="generate_content", status="success",
        run_id=run_id, provider="openrouter", model=actual_model,
        prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, cost_usd=cost_usd,
    )

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


async def tool_generate_visual_brief(
    brief: dict,
    content: dict,
    platform: str,
    brand_context: dict = {},
    run_id: str = "",
    tenant_id: str = "",
) -> dict:
    """Generate a structured visual art-direction brief via LLM."""
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
    if not openrouter_key:
        return VisualBrief().model_dump()

    model = "google/gemini-2.5-flash"
    copy_text = content.get("copy", "")[:400]
    top_angle = (brief.get("trending_angles") or [""])[0]
    brand_name = brand_context.get("name", "OfferBerries")
    brand_color = brand_context.get("primary_color", "#4F46E5 indigo")

    prompt = f"""You are a visual art director creating a brief for a {platform} social media post.

Post copy (excerpt): {copy_text}
Key research angle: {top_angle}
Brand: {brand_name}
Brand primary color: {brand_color}

Return ONLY valid JSON — no markdown, no extra text:
{{
  "headline": "short punchy headline for visual (max 8 words)",
  "subtext": "supporting line (max 12 words)",
  "visual_mood": "2-3 adjectives, e.g. professional clean trustworthy",
  "color_directive": "e.g. dominant indigo white text high contrast",
  "layout_hint": "one of: stat-card | quote-card | announcement | illustration | data-visual"
}}"""

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {openrouter_key}"},
            json={"model": model, "max_tokens": 200, "messages": [{"role": "user", "content": prompt}]},
        )
        resp.raise_for_status()
        resp_body = resp.json()
        raw = resp_body["choices"][0]["message"]["content"].strip()

    usage = resp_body.get("usage", {})
    cost_usd = _compute_openrouter_cost(model, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
    await log_tool_call(
        tenant_id=tenant_id, tool_name="generate_visual_brief", status="success",
        run_id=run_id, provider="openrouter", model=model,
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
        cost_usd=cost_usd,
    )

    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("```").strip()
    try:
        data = json.loads(cleaned)
        return VisualBrief(**{k: v for k, v in data.items() if k in VisualBrief.model_fields}).model_dump()
    except Exception:
        return VisualBrief(headline=copy_text[:60]).model_dump()


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
    visual_brief: Optional[dict] = None,
) -> dict:
    platform = content.platform if isinstance(content, PlatformContent) else content.get("platform", "linkedin")
    copy = content.copy if isinstance(content, PlatformContent) else content.get("copy", "")

    # Build enriched prompt from visual brief if available
    vb = VisualBrief(**visual_brief) if visual_brief else None
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
        if vb and vb.headline:
            od_prompt = (
                f"{vb.layout_hint}: \"{vb.headline}\" — {vb.subtext}. "
                f"{vb.color_directive}. {vb.visual_mood}."
            )
        else:
            od_prompt = copy
        async with httpx.AsyncClient(timeout=90) as client:
            od_resp = await client.post(
                f"{od_url}/api/generate",
                headers={"Authorization": f"Bearer {od_token}"},
                json={"prompt": od_prompt, "skill": template_id, "design_system": "offerberries"},
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
        if vb and vb.headline:
            flux_prompt = build_flux_prompt(vb, platform)
        else:
            flux_prompt = f"Professional social media graphic: {copy[:200]}"
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(
                "https://fal.run/fal-ai/flux/dev",
                headers={"Authorization": f"Key {fal_key}"},
                json={"prompt": flux_prompt, "image_size": size_map.get(platform, "square_hd")},
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


# ── C1: Research model config ──────────────────────────────────────────────

class ResearchModelRequest(BaseModel):
    model_id: str

@app.get("/config/research-model")
async def get_research_model(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await get_tenant(x_api_key, authorization)
    doc = await db["configs"].find_one({"tenant_id": tenant.tenant_id, "key": "research_model"}, {"_id": 0})
    return {"model_id": doc["value"] if doc else "sonar"}

@app.put("/config/research-model")
async def put_research_model(
    req: ResearchModelRequest,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    if req.model_id not in PERPLEXITY_COSTS:
        raise HTTPException(status_code=400, detail=f"Unknown research model: {req.model_id}")
    tenant = await get_tenant(x_api_key, authorization)
    await db["configs"].update_one(
        {"tenant_id": tenant.tenant_id, "key": "research_model"},
        {"$set": {"value": req.model_id, "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return {"saved": True, "model_id": req.model_id}


# ── C2: Voice profile config ───────────────────────────────────────────────

@app.get("/config/voice-profile")
async def get_voice_profile(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await get_tenant(x_api_key, authorization)
    doc = await db["configs"].find_one({"tenant_id": tenant.tenant_id, "key": "voice_profile"}, {"_id": 0})
    if doc and isinstance(doc.get("value"), dict):
        try:
            return VoiceProfile(**doc["value"]).model_dump()
        except Exception:
            pass
    return VoiceProfile().model_dump()

@app.put("/config/voice-profile")
async def put_voice_profile(
    req: VoiceProfile,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await get_tenant(x_api_key, authorization)
    await db["configs"].update_one(
        {"tenant_id": tenant.tenant_id, "key": "voice_profile"},
        {"$set": {"value": req.model_dump(), "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return {"saved": True}


# ── D2: Template library CRUD ──────────────────────────────────────────────

DEFAULT_TEMPLATES = [
    TemplateDoc(template_id="linkedin-single",    name="LinkedIn Single",    platform="linkedin",   is_default=True).model_dump(),
    TemplateDoc(template_id="twitter-stat-card",  name="Twitter Stat Card",  platform="twitter",    is_default=True).model_dump(),
    TemplateDoc(template_id="instagram-quote",    name="Instagram Quote",    platform="instagram",  is_default=True).model_dump(),
    TemplateDoc(template_id="youtube-thumbnail",  name="YouTube Thumbnail",  platform="youtube",    is_default=True).model_dump(),
    TemplateDoc(template_id="email-header",       name="Email Header",       platform="email",      is_default=True).model_dump(),
    TemplateDoc(template_id="announcement-card",  name="Announcement Card",  platform="all",        is_default=True).model_dump(),
]

@app.get("/config/templates")
async def get_templates(
    platform: Optional[str] = None,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await get_tenant(x_api_key, authorization)
    query: dict = {"tenant_id": tenant.tenant_id}
    if platform:
        query["$or"] = [{"platform": platform}, {"platform": "all"}]
    cursor = db["templates"].find(query, {"_id": 0}).sort("name", 1)
    templates = await cursor.to_list(length=100)
    if not templates:
        templates = [t for t in DEFAULT_TEMPLATES if not platform or t["platform"] in (platform, "all")]
    return templates

@app.post("/config/templates", status_code=201)
async def create_template(
    req: TemplateDoc,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await get_tenant(x_api_key, authorization)
    doc = {**req.model_dump(), "tenant_id": tenant.tenant_id, "created_at": datetime.now(timezone.utc)}
    await db["templates"].update_one(
        {"tenant_id": tenant.tenant_id, "template_id": req.template_id},
        {"$set": doc},
        upsert=True,
    )
    return {"saved": True, "template_id": req.template_id}

@app.put("/config/templates/{template_id}")
async def update_template(
    template_id: str,
    req: TemplateDoc,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await get_tenant(x_api_key, authorization)
    result = await db["templates"].update_one(
        {"tenant_id": tenant.tenant_id, "template_id": template_id},
        {"$set": {**req.model_dump(), "updated_at": datetime.now(timezone.utc)}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"saved": True}

@app.delete("/config/templates/{template_id}")
async def delete_template(
    template_id: str,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await get_tenant(x_api_key, authorization)
    result = await db["templates"].delete_one(
        {"tenant_id": tenant.tenant_id, "template_id": template_id}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"deleted": True}


# ── D2: Template upload + preview ──────────────────────────────────────────

_VAR_RE = re.compile(r"\{\{(\w+)\}\}")


@app.post("/config/templates/upload", status_code=201)
async def upload_template(
    req: TemplateUploadRequest,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    """Upload an HTML template; auto-extracts {{variable}} placeholders."""
    tenant = await get_tenant(x_api_key, authorization)
    variables = list(dict.fromkeys(_VAR_RE.findall(req.html_content)))  # unique, ordered
    doc = {
        "template_id": req.template_id,
        "name": req.name,
        "platform": req.platform,
        "thumbnail_url": req.thumbnail_url,
        "preview_url": "",
        "is_default": False,
        "layout_tags": req.layout_tags,
        "html_content": req.html_content,
        "variables": variables,
        "tenant_id": tenant.tenant_id,
        "created_at": datetime.now(timezone.utc),
    }
    await db["templates"].update_one(
        {"tenant_id": tenant.tenant_id, "template_id": req.template_id},
        {"$set": doc},
        upsert=True,
    )
    return {"saved": True, "template_id": req.template_id, "variables": variables}


@app.post("/config/templates/{template_id}/preview")
async def preview_template(
    template_id: str,
    variables: dict = {},
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    """Render a template preview PNG by injecting variable values."""
    tenant = await get_tenant(x_api_key, authorization)
    doc = await db["templates"].find_one(
        {"tenant_id": tenant.tenant_id, "template_id": template_id}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Template not found")

    html = doc.get("html_content", "")
    for k, v in variables.items():
        html = html.replace("{{" + k + "}}", str(v))

    import base64
    renderer_url = os.getenv("RENDERER_URL", "http://renderer:3001")
    html_b64 = base64.b64encode(html.encode()).decode()
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{renderer_url}/render",
            json={"template_id": "_od_html_", "content_data": {"__html_b64": html_b64}, "width": 1080, "height": 1080},
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Renderer failed")
        filename = resp.headers.get("x-output-filename", f"{uuid.uuid4()}.png")

    preview_url = _renderer_public_url(filename, renderer_url)
    await db["templates"].update_one(
        {"tenant_id": tenant.tenant_id, "template_id": template_id},
        {"$set": {"preview_url": preview_url, "updated_at": datetime.now(timezone.utc)}},
    )
    return {"preview_url": preview_url, "template_id": template_id}


# ── C1: Research models collection ────────────────────────────────────────

@app.get("/research-models")
async def list_research_models(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    """User-facing: return active models allowed for tenant's tier."""
    tenant = await get_tenant(x_api_key, authorization)
    tier = tenant.tier if tenant.tier != "owner" else "pro"
    tier_level = TIER_ORDER.get(tier, 2)
    cursor = db["research_models"].find({"is_active": True}, {"_id": 0})
    models = await cursor.to_list(length=50)
    if not models:
        models = RESEARCH_MODELS_SEED
    allowed = [m for m in models if TIER_ORDER.get(m.get("tier_required", "free"), 0) <= tier_level]
    return allowed


@app.get("/admin/research-models")
async def admin_list_research_models(
    x_api_key: Optional[str] = Header(None),
):
    _require_owner(x_api_key)
    cursor = db["research_models"].find({}, {"_id": 0})
    models = await cursor.to_list(length=50)
    return models or RESEARCH_MODELS_SEED


@app.post("/admin/research-models", status_code=201)
async def admin_create_research_model(
    req: ResearchModel,
    x_api_key: Optional[str] = Header(None),
):
    _require_owner(x_api_key)
    if req.tier_required not in TIER_ORDER:
        raise HTTPException(status_code=400, detail=f"Invalid tier_required: {req.tier_required}")
    doc = {**req.model_dump(), "created_at": datetime.now(timezone.utc)}
    await db["research_models"].update_one({"id": req.id}, {"$set": doc}, upsert=True)
    return {"saved": True, "id": req.id}


@app.patch("/admin/research-models/{model_id}")
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
    result = await db["research_models"].update_one({"id": model_id}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Research model not found")
    return {"updated": True, "id": model_id}


# ── C2: Voice profiles CRUD ────────────────────────────────────────────────

def _require_owner(x_api_key: Optional[str]):
    owner_key = os.getenv("OWNER_API_KEY", "")
    if not owner_key or x_api_key != owner_key:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/voice-profiles")
async def list_voice_profiles(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await get_tenant(x_api_key, authorization)
    await _seed_voice_profiles_for_tenant(tenant.tenant_id)
    cursor = db["voice_profiles"].find(
        {"tenant_id": tenant.tenant_id, "is_active": True}, {"_id": 0}
    ).sort("name", 1)
    profiles = await cursor.to_list(length=100)
    return profiles


@app.post("/voice-profiles", status_code=201)
async def create_voice_profile(
    req: VoiceProfileCreateRequest,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await get_tenant(x_api_key, authorization)
    if req.hashtag_style not in HASHTAG_STYLE_VALUES:
        raise HTTPException(status_code=400, detail=f"Invalid hashtag_style: {req.hashtag_style}")
    if req.cta_type not in CTA_TYPE_VALUES:
        raise HTTPException(status_code=400, detail=f"Invalid cta_type: {req.cta_type}")
    profile_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    if req.is_default:
        await db["voice_profiles"].update_many(
            {"tenant_id": tenant.tenant_id}, {"$set": {"is_default": False}}
        )
    doc = {
        **req.model_dump(), "id": profile_id,
        "tenant_id": tenant.tenant_id, "is_active": True, "created_at": now,
    }
    await db["voice_profiles"].insert_one(doc)
    doc.pop("_id", None)
    return doc


@app.patch("/voice-profiles/{profile_id}")
async def update_voice_profile(
    profile_id: str,
    req: VoiceProfileUpdateRequest,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await get_tenant(x_api_key, authorization)
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    if "hashtag_style" in updates and updates["hashtag_style"] not in HASHTAG_STYLE_VALUES:
        raise HTTPException(status_code=400, detail=f"Invalid hashtag_style: {updates['hashtag_style']}")
    if "cta_type" in updates and updates["cta_type"] not in CTA_TYPE_VALUES:
        raise HTTPException(status_code=400, detail=f"Invalid cta_type: {updates['cta_type']}")
    updates["updated_at"] = datetime.now(timezone.utc)
    result = await db["voice_profiles"].update_one(
        {"id": profile_id, "tenant_id": tenant.tenant_id}, {"$set": updates}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Voice profile not found")
    return {"updated": True, "id": profile_id}


@app.delete("/voice-profiles/{profile_id}")
async def delete_voice_profile(
    profile_id: str,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await get_tenant(x_api_key, authorization)
    doc = await db["voice_profiles"].find_one(
        {"id": profile_id, "tenant_id": tenant.tenant_id}, {"is_default": 1}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Voice profile not found")
    if doc.get("is_default"):
        raise HTTPException(status_code=400, detail="Cannot delete the default voice profile")
    await db["voice_profiles"].update_one(
        {"id": profile_id, "tenant_id": tenant.tenant_id},
        {"$set": {"is_active": False, "deleted_at": datetime.now(timezone.utc)}},
    )
    return {"deleted": True, "id": profile_id}


@app.patch("/voice-profiles/{profile_id}/set-default")
async def set_default_voice_profile(
    profile_id: str,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await get_tenant(x_api_key, authorization)
    doc = await db["voice_profiles"].find_one(
        {"id": profile_id, "tenant_id": tenant.tenant_id, "is_active": True}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Voice profile not found")
    await db["voice_profiles"].update_many(
        {"tenant_id": tenant.tenant_id}, {"$set": {"is_default": False}}
    )
    await db["voice_profiles"].update_one(
        {"id": profile_id}, {"$set": {"is_default": True, "updated_at": datetime.now(timezone.utc)}}
    )
    return {"default_set": True, "id": profile_id}
