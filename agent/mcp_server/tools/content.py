"""Content generation tool and prompt builders."""
import json
import logging
import os
import re
from typing import Optional

import httpx
from fastapi import HTTPException

from constants import PLATFORM_CHAR_LIMITS, compute_openrouter_cost
from schemas import PlatformContent, ResearchBrief, VoiceProfileDoc

logger = logging.getLogger("mcp_server")


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


def _parse_content_response(raw: str, topic: str, platform: str) -> tuple[str, list[str], str]:
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
        copy = re.sub(r"#\w+", "", raw).strip()
        return copy, hashtags, ""


async def tool_generate_content(
    brief: ResearchBrief,
    platform: str,
    product: str = "full_erp",
    model: str = "anthropic/claude-sonnet-4-6",
    tenant_id: str = "",
    run_id: str = "",
) -> dict:
    import main as _m

    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
    if not openrouter_key:
        logger.warning("OPENROUTER_API_KEY not set — content generation unavailable")
        raise HTTPException(status_code=503, detail="Content generation API key not configured")

    voice_doc: Optional[VoiceProfileDoc] = None
    if tenant_id:
        await _m._seed_voice_profiles_for_tenant(tenant_id)
        vp_raw = await _m.db["voice_profiles"].find_one(
            {"tenant_id": tenant_id, "is_default": True, "is_active": True}
        )
        if not vp_raw:
            vp_raw = await _m.db["voice_profiles"].find_one({"tenant_id": tenant_id, "is_active": True})
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

    usage = resp_body.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    cost_usd = compute_openrouter_cost(actual_model, prompt_tokens, completion_tokens)
    await _m.log_tool_call(
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
