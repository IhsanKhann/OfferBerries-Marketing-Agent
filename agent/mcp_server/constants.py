"""Constants, pricing tables, and seed data for the MCP server."""
from schemas import TemplateDoc

REQUIRED_ENV = [
    "MONGODB_URI", "MONGODB_DB", "REDIS_URL",
    "OWNER_API_KEY", "OWNER_TENANT_ID",
    "OPENROUTER_API_KEY",
    "MCP_SERVER_URL",
]

OPENROUTER_PRICING: dict[str, tuple[float, float]] = {
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

PLATFORM_DIMS = {
    "linkedin":  (1080, 1080),
    "twitter":   (1600, 900),
    "instagram": (1080, 1080),
    "youtube":   (1280, 720),
    "email":     (600, 200),
}

PLATFORM_CHAR_LIMITS = {
    "linkedin":  1300,
    "twitter":   280,
    "instagram": 2200,
    "youtube":   500,
    "email":     300,
}

TIER_ORDER: dict[str, int] = {"free": 0, "starter": 1, "pro": 2}
HASHTAG_STYLE_VALUES = {"branded", "contextual", "educational", "discovery"}
CTA_TYPE_VALUES = {"demo", "learn_more", "engagement", "contextual"}

PLAN_PRICES = {"starter_pkr": 4999, "pro_pkr": 14999}

OPENROUTER_MODELS = [
    {"id": "google/gemini-2.5-flash", "name": "Gemini 2.5 Flash", "tier": "fast", "context_length": 1_000_000, "pricing": {"prompt": "0.075", "completion": "0.30"}, "description": "Fast and cost-effective, great for drafts"},
    {"id": "meta-llama/llama-3.1-8b-instruct:free", "name": "Llama 3.1 8B (Free)", "tier": "fast", "context_length": 131_072, "pricing": {"prompt": "0", "completion": "0"}, "description": "Free tier, limited quality"},
    {"id": "mistralai/mistral-7b-instruct:free", "name": "Mistral 7B (Free)", "tier": "fast", "context_length": 32_768, "pricing": {"prompt": "0", "completion": "0"}, "description": "Free, good for simple tasks"},
    {"id": "google/gemini-2.5-pro", "name": "Gemini 2.5 Pro", "tier": "balanced", "context_length": 1_000_000, "pricing": {"prompt": "1.25", "completion": "10.00"}, "description": "Excellent reasoning and long context"},
    {"id": "anthropic/claude-haiku-4-5", "name": "Claude Haiku 4.5", "tier": "balanced", "context_length": 200_000, "pricing": {"prompt": "0.80", "completion": "4.00"}, "description": "Fast Claude with strong instruction following"},
    {"id": "openai/gpt-4o-mini", "name": "GPT-4o Mini", "tier": "balanced", "context_length": 128_000, "pricing": {"prompt": "0.15", "completion": "0.60"}, "description": "Efficient OpenAI model for content tasks"},
    {"id": "anthropic/claude-sonnet-4-6", "name": "Claude Sonnet 4.6", "tier": "premium", "context_length": 200_000, "pricing": {"prompt": "3.00", "completion": "15.00"}, "description": "Best for nuanced content and brand voice"},
    {"id": "openai/gpt-4o", "name": "GPT-4o", "tier": "premium", "context_length": 128_000, "pricing": {"prompt": "5.00", "completion": "15.00"}, "description": "OpenAI flagship, best overall quality"},
    {"id": "google/gemini-2.5-pro-preview", "name": "Gemini 2.5 Pro Preview", "tier": "premium", "context_length": 1_000_000, "pricing": {"prompt": "3.50", "completion": "10.50"}, "description": "Latest Google frontier model"},
]

RESEARCH_MODELS_SEED: list[dict] = [
    {"id": "sonar", "display_name": "Sonar (Standard)", "provider": "perplexity", "cost_usd_per_call": 0.0014, "credits_per_call": 1, "tier_required": "free", "is_active": True},
    {"id": "sonar-pro", "display_name": "Sonar Pro", "provider": "perplexity", "cost_usd_per_call": 0.004, "credits_per_call": 4, "tier_required": "starter", "is_active": True},
    {"id": "sonar-deep-research", "display_name": "Deep Research", "provider": "perplexity", "cost_usd_per_call": 0.056, "credits_per_call": 56, "tier_required": "pro", "is_active": True},
]

DEFAULT_VOICE_PROFILES: list[dict] = [
    {"name": "General / Adaptive", "is_default": True, "system_prompt": None, "hashtag_style": "contextual", "cta_type": "contextual", "tone": "adaptive"},
    {"name": "OfferBerries Official", "is_default": False, "system_prompt": ("You are writing for OfferBerries, a Pakistani B2B SaaS company. Be professional, honest, and direct. Focus on real ROI for SMBs. Never use corporate buzzwords."), "hashtag_style": "branded", "cta_type": "demo", "tone": "professional"},
]

DEFAULT_TEMPLATES = [
    TemplateDoc(template_id="linkedin-single",   name="LinkedIn Single",   platform="linkedin",  is_default=True).model_dump(),
    TemplateDoc(template_id="twitter-stat-card", name="Twitter Stat Card", platform="twitter",   is_default=True).model_dump(),
    TemplateDoc(template_id="instagram-quote",   name="Instagram Quote",   platform="instagram", is_default=True).model_dump(),
    TemplateDoc(template_id="youtube-thumbnail", name="YouTube Thumbnail", platform="youtube",   is_default=True).model_dump(),
    TemplateDoc(template_id="email-header",      name="Email Header",      platform="email",     is_default=True).model_dump(),
    TemplateDoc(template_id="announcement-card", name="Announcement Card", platform="all",       is_default=True).model_dump(),
]


def compute_openrouter_cost(model_id: str, prompt_tokens: int, completion_tokens: int) -> float:
    prompt_price, completion_price = OPENROUTER_PRICING.get(model_id, (0.0, 0.0))
    return round(
        (prompt_tokens * prompt_price + completion_tokens * completion_price) / 1_000_000, 8
    )
