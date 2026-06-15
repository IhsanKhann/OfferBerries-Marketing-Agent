"""Analytics retrieval and strategy update tools."""
import logging
import os
from datetime import datetime, timezone

import httpx

from schemas import AnalyticsReport, StrategyDoc

logger = logging.getLogger("mcp_server")


async def tool_get_analytics(platform: str = "all", days: int = 7, tenant_id: str = "", db_ref=None) -> dict:
    from datetime import timedelta
    import main as _m

    _db = db_ref if db_ref is not None else _m.db

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
    import main as _m

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

    await _m.db["configs"].update_one(
        {"tenant_id": tenant_id, "key": "strategy"},
        {"$set": {"value": strategy, "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return strategy
