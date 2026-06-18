"""Analytics service: run-level and project-level analytics helpers."""
from __future__ import annotations
from collections import Counter, defaultdict
from datetime import datetime, timezone


async def get_run_analytics(db, run_id: str) -> dict:
    """Compute cost_per_post and total_cost_usd for a single run."""
    tool_calls = await db["tool_calls"].find({"run_id": run_id}, {"_id": 0}).to_list(length=1000)
    posts = await db["posts"].find({"run_id": run_id}, {"_id": 0}).to_list(length=1000)

    total_cost = sum(tc.get("cost_usd", 0) or 0 for tc in tool_calls)
    post_count = len(posts)
    cost_per_post = (total_cost / post_count) if post_count > 0 else 0

    return {
        "run_id": run_id,
        "post_count": post_count,
        "total_cost_usd": total_cost,
        "cost_per_post": cost_per_post,
    }


async def get_project_analytics(db, project_id: str) -> dict:
    """Return best_platform and avg_engagement_per_platform for a project."""
    posts = await db["posts"].find({"project_id": project_id}, {"_id": 0}).to_list(length=5000)

    approved_by_platform: Counter = Counter()
    rating_by_platform: dict[str, list[str]] = defaultdict(list)

    for p in posts:
        plat = p.get("platform", "unknown")
        if p.get("status") == "approved":
            approved_by_platform[plat] += 1
        rating = p.get("performance_rating")
        if rating:
            rating_by_platform[plat].append(rating)

    best_platform = approved_by_platform.most_common(1)[0][0] if approved_by_platform else "unknown"

    _score = {"high": 3, "medium": 2, "low": 1}
    avg_engagement: dict[str, float] = {}
    for plat, ratings in rating_by_platform.items():
        scores = [_score.get(r, 0) for r in ratings]
        avg_engagement[plat] = sum(scores) / len(scores) if scores else 0.0

    return {
        "project_id": project_id,
        "total_posts": len(posts),
        "best_platform": best_platform,
        "avg_engagement_per_platform": avg_engagement,
    }


async def get_optimal_times_from_data(db, project_id: str, platform: str) -> dict | None:
    """Derive best posting hours/days from high-rated posts' scheduled_at."""
    posts = await db["posts"].find(
        {"project_id": project_id, "platform": platform, "performance_rating": "high"},
        {"_id": 0},
    ).to_list(length=500)

    if not posts:
        return None

    hours: list[int] = []
    days: list[str] = []
    _day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    for p in posts:
        raw = p.get("scheduled_at", "")
        if not raw:
            continue
        try:
            dt = datetime.fromisoformat(str(raw))
            hours.append(dt.hour)
            days.append(_day_names[dt.weekday()])
        except (ValueError, TypeError):
            pass

    if not hours:
        return {"best_hours": [], "best_days": []}

    hour_counter = Counter(hours)
    day_counter = Counter(days)
    best_hours = [h for h, _ in hour_counter.most_common(3)]
    best_days = [d for d, _ in day_counter.most_common(3)]

    return {"best_hours": best_hours, "best_days": best_days}
