"""Pydantic models for the MCP server."""
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel


class PerformanceRating(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


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
    hashtag_style: str = "contextual"
    cta_type: str = "contextual"
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
    tier_required: str
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


class BrandVoiceRequest(BaseModel):
    content: str


class ContentModelRequest(BaseModel):
    model_id: str


class ResearchModelRequest(BaseModel):
    model_id: str


class CreateApiKeyRequest(BaseModel):
    tenant_id: str
    tier: str = "starter"
    label: str = ""


class CheckoutRequest(BaseModel):
    plan: str
    tenant_email: str


class ProjectDoc(BaseModel):
    id: str = ""
    tenant_id: str = ""
    name: str
    description: Optional[str] = None
    brand_voice: Optional[str] = None
    default_platforms: list[str] = []
    default_model: str = "sonar-pro"
    default_steps: list[str] = ["research", "content_generation", "visual_generation"]
    color: str = "#6366F1"
    icon: str = "📁"
    starred: bool = False
    is_active: bool = True
    archived_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    schedule_enabled: bool = False
    schedule_frequency: Optional[str] = None
    schedule_cron: Optional[str] = None
    schedule_platforms: list[str] = []
    schedule_topic_rotation: list[str] = []
    schedule_auto_approve: bool = False


class ProjectCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    brand_voice: Optional[str] = None
    default_platforms: list[str] = ["linkedin", "instagram"]
    default_model: str = "sonar-pro"
    default_steps: list[str] = ["research", "content_generation", "visual_generation"]
    color: str = "#6366F1"
    icon: str = "📁"


class ProjectUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    brand_voice: Optional[str] = None
    default_platforms: Optional[list[str]] = None
    default_model: Optional[str] = None
    default_steps: Optional[list[str]] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    starred: Optional[bool] = None
    schedule_enabled: Optional[bool] = None
    schedule_frequency: Optional[str] = None
    schedule_cron: Optional[str] = None
    schedule_platforms: Optional[list[str]] = None
    schedule_topic_rotation: Optional[list[str]] = None
    schedule_auto_approve: Optional[bool] = None
