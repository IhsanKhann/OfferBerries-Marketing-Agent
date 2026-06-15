"""Research and competitor-scraping tools."""
import json
import logging
import os

import httpx
from fastapi import HTTPException

from constants import PERPLEXITY_COSTS
from schemas import CompetitorPost, ResearchBrief
from services.perplexity_client import PerplexityError, get_perplexity_client

logger = logging.getLogger("mcp_server")


async def tool_research_trends(
    topic: str,
    platform: str = "all",
    model: str = "sonar",
    recency_filter: str = "week",
    run_id: str = "",
    tenant_id: str = "",
) -> dict:
    import main as _m

    client = get_perplexity_client()
    try:
        result = await client.research(topic=topic, platform=platform, model=model)
    except PerplexityError as exc:
        logger.warning("Perplexity error [%s]: %s", exc.error_type, exc.message)
        await _m.log_tool_call(
            tenant_id=tenant_id, tool_name="research_trends", status="error",
            run_id=run_id, provider="perplexity", model=model,
        )
        raise HTTPException(status_code=503, detail=exc.to_dict())

    cost_usd = PERPLEXITY_COSTS.get(model, PERPLEXITY_COSTS["sonar"])
    await _m.log_tool_call(
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
        generated_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
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
