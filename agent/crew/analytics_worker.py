"""Analytics collection worker — runs weekly via n8n."""
import os
from datetime import datetime, timezone

import httpx

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
POSTIZ_URL = os.getenv("POSTIZ_URL", "http://postiz:3000")
POSTIZ_SECRET = os.getenv("POSTIZ_SECRET", "")
OWNER_TENANT_ID = os.getenv("OWNER_TENANT_ID", "")


async def collect_analytics_data():
    """Pull performance data from Postiz and store in Supabase."""
    if not POSTIZ_SECRET:
        return

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{POSTIZ_URL}/api/analytics",
            headers={"Authorization": f"Bearer {POSTIZ_SECRET}"},
            params={"days": 7},
        )
        if resp.status_code != 200:
            return
        data = resp.json()

    posts = data.get("posts", [])
    if not posts or not SUPABASE_URL:
        return

    records = [
        {
            "tenant_id": OWNER_TENANT_ID,
            "postiz_id": p.get("id", ""),
            "platform": p.get("platform", ""),
            "template_id": p.get("template_id", ""),
            "topic": p.get("topic", ""),
            "impressions": p.get("impressions", 0),
            "clicks": p.get("clicks", 0),
            "likes": p.get("likes", 0),
            "shares": p.get("shares", 0),
            "profile_visits": p.get("profile_visits", 0),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        for p in posts
    ]

    async with httpx.AsyncClient(timeout=15) as client:
        await client.post(
            f"{SUPABASE_URL}/rest/v1/posts_performance",
            headers={
                "apikey": SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                "Prefer": "return=minimal",
            },
            json=records,
        )
