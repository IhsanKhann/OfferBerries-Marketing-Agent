"""Visual generation tools: briefs, templates, fal.ai, OpenDesign."""
import json
import logging
import os
import re
import uuid
from typing import Optional

import httpx
from fastapi import HTTPException

from constants import PLATFORM_DIMS, compute_openrouter_cost
from schemas import PlatformContent, VisualAsset, VisualBrief

logger = logging.getLogger("mcp_server")


def _renderer_public_url(filename: str, renderer_url: str) -> str:
    domain = os.getenv("DOMAIN", "")
    if domain and domain != "localhost":
        return f"https://agent.{domain}/render-output/{filename}"
    return f"{renderer_url}/output/{filename}"


def build_flux_prompt(visual_brief: VisualBrief, platform: str, brand_colors: Optional[list[str]] = None) -> str:
    colors = brand_colors or ["#4F46E5 indigo", "#FFFFFF white"]
    color_str = ", ".join(colors[:3])
    negative = (
        "ugly, blurry, watermark, text errors, cluttered, stock photo, people, faces, "
        "low quality, distorted, nsfw"
    )
    dims = PLATFORM_DIMS.get(platform, (1080, 1080))
    aspect = "square" if dims[0] == dims[1] else "landscape 16:9"

    return (
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


async def tool_generate_visual_brief(
    brief: dict,
    content: dict,
    platform: str,
    brand_context: dict = {},
    run_id: str = "",
    tenant_id: str = "",
) -> dict:
    import main as _m

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
    cost_usd = compute_openrouter_cost(model, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
    await _m.log_tool_call(
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


async def tool_generate_visual(
    content: PlatformContent,
    template_id: str,
    source: str = "template",
    visual_brief: Optional[dict] = None,
) -> dict:
    platform = content.platform if isinstance(content, PlatformContent) else content.get("platform", "linkedin")
    copy = content.copy if isinstance(content, PlatformContent) else content.get("copy", "")

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
            format="png", width=width, height=height,
            source="template", template_id=template_id,
        ).model_dump()

    if source == "open_design":
        if vb and vb.headline:
            od_prompt = f"{vb.layout_hint}: \"{vb.headline}\" — {vb.subtext}. {vb.color_directive}. {vb.visual_mood}."
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

        import base64
        html_b64 = base64.b64encode(html_content.encode()).decode()
        async with httpx.AsyncClient(timeout=60) as client:
            render_resp = await client.post(
                f"{renderer_url}/render",
                json={"template_id": "_od_html_", "content_data": {"__html_b64": html_b64}, "width": width, "height": height},
            )
            if render_resp.status_code == 200:
                filename = render_resp.headers.get("x-output-filename", f"{uuid.uuid4()}.png")
                return VisualAsset(
                    path=f"/app/output/{filename}",
                    url=_renderer_public_url(filename, renderer_url),
                    format="png", width=width, height=height,
                    source="open_design", template_id=template_id,
                ).model_dump()
        return VisualAsset(format="png", source="open_design", template_id=template_id).model_dump()

    if source == "fal":
        fal_key = os.getenv("FAL_API_KEY", "")
        size_map = {"linkedin": "square_hd", "twitter": "landscape_16_9", "instagram": "square_hd", "youtube": "landscape_16_9"}
        flux_prompt = build_flux_prompt(vb, platform) if (vb and vb.headline) else f"Professional social media graphic: {copy[:200]}"
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
            format="png", width=width, height=height,
            source="fal", template_id=template_id,
        ).model_dump()

    raise HTTPException(status_code=400, detail=f"Unknown source: {source}")
