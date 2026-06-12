"""Pattern extraction — analyses post performance and updates content strategy."""
import os
from datetime import datetime, timezone

import httpx

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
MCP_URL = os.getenv("MCP_SERVER_URL", "http://mcp-server:8000")
OWNER_KEY = os.getenv("OWNER_API_KEY", "")


async def extract_patterns(tenant_id: str) -> dict:
    """Analyse 30-day performance, derive strategy changes, update Supabase."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return {}

    # Query last 30 days of performance
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/posts_performance",
            headers={
                "apikey": SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            },
            params={
                "tenant_id": f"eq.{tenant_id}",
                "order": "recorded_at.desc",
                "limit": "100",
            },
        )
        posts = resp.json() if resp.status_code == 200 else []

    if not posts:
        return {}

    # Build summary
    by_template: dict[str, list[int]] = {}
    by_day: dict[str, list[int]] = {}
    by_platform: dict[str, list[int]] = {}

    for p in posts:
        imp = p.get("impressions", 0)
        tmpl = p.get("template_id", "unknown")
        platform = p.get("platform", "unknown")
        recorded = p.get("recorded_at", "")
        try:
            day = datetime.fromisoformat(recorded).strftime("%A")
        except Exception:
            day = "Unknown"

        by_template.setdefault(tmpl, []).append(imp)
        by_day.setdefault(day, []).append(imp)
        by_platform.setdefault(platform, []).append(imp)

    best_template = max(by_template, key=lambda k: sum(by_template[k]) / len(by_template[k])) if by_template else ""
    best_day = max(by_day, key=lambda k: sum(by_day[k]) / len(by_day[k])) if by_day else ""
    best_platform = max(by_platform, key=lambda k: sum(by_platform[k]) / len(by_platform[k])) if by_platform else ""

    summary = (
        f"30-day analysis: best template={best_template}, "
        f"best day={best_day}, best platform={best_platform}, "
        f"total posts analysed={len(posts)}"
    )

    changes: dict = {
        "best_performing_template": best_template,
        "best_performing_day": best_day,
        "performance_baseline": {
            "best_template": best_template,
            "best_day": best_day,
            "best_platform": best_platform,
            "posts_analysed": len(posts),
        },
    }

    # Ask LLM for strategy suggestions
    if OPENROUTER_API_KEY:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
                json={
                    "model": "google/gemini-flash-1.5",
                    "messages": [
                        {
                            "role": "user",
                            "content": (
                                f"Based on this 30-day performance data: {summary}\n"
                                "What should change in the content strategy for next week?\n"
                                "Return JSON with keys: topic_focus, format_preference, "
                                "platform_priority (list), tone_notes, avoid_topics (list)"
                            ),
                        }
                    ],
                },
            )
            if resp.status_code == 200:
                import json, re
                content = resp.json()["choices"][0]["message"]["content"]
                match = re.search(r"\{.*\}", content, re.DOTALL)
                if match:
                    try:
                        llm_changes = json.loads(match.group())
                        changes.update(llm_changes)
                    except Exception:
                        pass

    # Push to MCP update_strategy tool
    async with httpx.AsyncClient(timeout=15) as client:
        await client.post(
            f"{MCP_URL}/mcp",
            headers={"X-API-Key": OWNER_KEY, "Content-Type": "application/json"},
            json={"method": "tools/call", "params": {"name": "update_strategy", "arguments": {"changes": changes}}},
        )

    return changes
