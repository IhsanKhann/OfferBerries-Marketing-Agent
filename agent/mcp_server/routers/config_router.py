"""Config REST endpoints: brand voice, strategy, content model, research model, voice profile, templates."""
import base64
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx
import main as _m
from fastapi import APIRouter, Header, HTTPException

from constants import DEFAULT_TEMPLATES, PERPLEXITY_COSTS
from schemas import (
    BrandVoiceRequest,
    ContentModelRequest,
    ResearchModelRequest,
    StrategyDoc,
    TemplateDoc,
    TemplateUploadRequest,
    VoiceProfile,
)
from tools.visual import _renderer_public_url

router = APIRouter()

_VAR_RE = re.compile(r"\{\{(\w+)\}\}")


# ── Brand voice ───────────────────────────────────────────────────────────────

@router.get("/config/brand-voice")
async def get_brand_voice(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await _m.get_tenant(x_api_key, authorization)
    doc = await _m.db["configs"].find_one(
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


@router.put("/config/brand-voice")
async def put_brand_voice(
    req: BrandVoiceRequest,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await _m.get_tenant(x_api_key, authorization)
    await _m.db["configs"].update_one(
        {"tenant_id": tenant.tenant_id, "key": "brand_voice"},
        {"$set": {"value": req.content, "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return {"saved": True}


# ── Strategy ──────────────────────────────────────────────────────────────────

@router.get("/config/strategy")
async def get_strategy(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await _m.get_tenant(x_api_key, authorization)
    doc = await _m.db["configs"].find_one(
        {"tenant_id": tenant.tenant_id, "key": "strategy"}, {"_id": 0}
    )
    if doc:
        data = doc.get("value", {})
        return StrategyDoc(**{k: v for k, v in data.items() if k in StrategyDoc.model_fields}).model_dump()
    return StrategyDoc(tenant_id=tenant.tenant_id).model_dump()


# ── Content model ─────────────────────────────────────────────────────────────

@router.get("/config/content-model")
async def get_content_model(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await _m.get_tenant(x_api_key, authorization)
    doc = await _m.db["configs"].find_one({"tenant_id": tenant.tenant_id, "key": "content_model"}, {"_id": 0})
    return {"model_id": doc["value"] if doc else "google/gemini-2.5-flash"}


@router.put("/config/content-model")
async def put_content_model(
    req: ContentModelRequest,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await _m.get_tenant(x_api_key, authorization)
    await _m.db["configs"].update_one(
        {"tenant_id": tenant.tenant_id, "key": "content_model"},
        {"$set": {"value": req.model_id, "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return {"saved": True, "model_id": req.model_id}


# ── Research model ────────────────────────────────────────────────────────────

@router.get("/config/research-model")
async def get_research_model(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await _m.get_tenant(x_api_key, authorization)
    doc = await _m.db["configs"].find_one({"tenant_id": tenant.tenant_id, "key": "research_model"}, {"_id": 0})
    return {"model_id": doc["value"] if doc else "sonar"}


@router.put("/config/research-model")
async def put_research_model(
    req: ResearchModelRequest,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    if req.model_id not in PERPLEXITY_COSTS:
        raise HTTPException(status_code=400, detail=f"Unknown research model: {req.model_id}")
    tenant = await _m.get_tenant(x_api_key, authorization)
    await _m.db["configs"].update_one(
        {"tenant_id": tenant.tenant_id, "key": "research_model"},
        {"$set": {"value": req.model_id, "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return {"saved": True, "model_id": req.model_id}


# ── Voice profile config ──────────────────────────────────────────────────────

@router.get("/config/voice-profile")
async def get_voice_profile(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await _m.get_tenant(x_api_key, authorization)
    doc = await _m.db["configs"].find_one({"tenant_id": tenant.tenant_id, "key": "voice_profile"}, {"_id": 0})
    if doc and isinstance(doc.get("value"), dict):
        try:
            return VoiceProfile(**doc["value"]).model_dump()
        except Exception:
            pass
    return VoiceProfile().model_dump()


@router.put("/config/voice-profile")
async def put_voice_profile(
    req: VoiceProfile,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await _m.get_tenant(x_api_key, authorization)
    await _m.db["configs"].update_one(
        {"tenant_id": tenant.tenant_id, "key": "voice_profile"},
        {"$set": {"value": req.model_dump(), "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return {"saved": True}


# ── Templates ─────────────────────────────────────────────────────────────────

@router.get("/config/templates")
async def get_templates(
    platform: Optional[str] = None,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await _m.get_tenant(x_api_key, authorization)
    query: dict = {"tenant_id": tenant.tenant_id}
    if platform:
        query["$or"] = [{"platform": platform}, {"platform": "all"}]
    cursor = _m.db["templates"].find(query, {"_id": 0}).sort("name", 1)
    templates = await cursor.to_list(length=100)
    if not templates:
        templates = [t for t in DEFAULT_TEMPLATES if not platform or t["platform"] in (platform, "all")]
    return templates


@router.post("/config/templates", status_code=201)
async def create_template(
    req: TemplateDoc,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await _m.get_tenant(x_api_key, authorization)
    doc = {**req.model_dump(), "tenant_id": tenant.tenant_id, "created_at": datetime.now(timezone.utc)}
    await _m.db["templates"].update_one(
        {"tenant_id": tenant.tenant_id, "template_id": req.template_id},
        {"$set": doc},
        upsert=True,
    )
    return {"saved": True, "template_id": req.template_id}


@router.put("/config/templates/{template_id}")
async def update_template(
    template_id: str,
    req: TemplateDoc,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await _m.get_tenant(x_api_key, authorization)
    result = await _m.db["templates"].update_one(
        {"tenant_id": tenant.tenant_id, "template_id": template_id},
        {"$set": {**req.model_dump(), "updated_at": datetime.now(timezone.utc)}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"saved": True}


@router.delete("/config/templates/{template_id}")
async def delete_template(
    template_id: str,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await _m.get_tenant(x_api_key, authorization)
    result = await _m.db["templates"].delete_one(
        {"tenant_id": tenant.tenant_id, "template_id": template_id}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"deleted": True}


@router.post("/config/templates/upload", status_code=201)
async def upload_template(
    req: TemplateUploadRequest,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await _m.get_tenant(x_api_key, authorization)
    variables = list(dict.fromkeys(_VAR_RE.findall(req.html_content)))
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
    await _m.db["templates"].update_one(
        {"tenant_id": tenant.tenant_id, "template_id": req.template_id},
        {"$set": doc},
        upsert=True,
    )
    return {"saved": True, "template_id": req.template_id, "variables": variables}


@router.post("/config/templates/{template_id}/preview")
async def preview_template(
    template_id: str,
    variables: dict = {},
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await _m.get_tenant(x_api_key, authorization)
    doc = await _m.db["templates"].find_one(
        {"tenant_id": tenant.tenant_id, "template_id": template_id}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Template not found")

    html = doc.get("html_content", "")
    for k, v in variables.items():
        html = html.replace("{{" + k + "}}", str(v))

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
    await _m.db["templates"].update_one(
        {"tenant_id": tenant.tenant_id, "template_id": template_id},
        {"$set": {"preview_url": preview_url, "updated_at": datetime.now(timezone.utc)}},
    )
    return {"preview_url": preview_url, "template_id": template_id}
