"""Scheduler service: optimal post times and topic rotation helpers."""
from __future__ import annotations

# Optimal posting times per platform in PKT (UTC+5).
# Each slot: {"hour": int, "minute": int, "day": str | None}
# day=None means any day of week is fine.
_OPTIMAL_SLOTS: dict[str, list[dict]] = {
    "instagram": [
        {"hour": 9,  "minute": 0, "day": None},
        {"hour": 12, "minute": 0, "day": None},
        {"hour": 19, "minute": 0, "day": None},
    ],
    "linkedin": [
        {"hour": 8,  "minute": 0, "day": "Tuesday"},
        {"hour": 9,  "minute": 0, "day": "Wednesday"},
        {"hour": 10, "minute": 0, "day": "Thursday"},
    ],
    "twitter": [
        {"hour": 10, "minute": 0, "day": None},
        {"hour": 14, "minute": 0, "day": None},
    ],
    "youtube": [
        {"hour": 15, "minute": 0, "day": "Friday"},
        {"hour": 12, "minute": 0, "day": "Saturday"},
    ],
    "email": [
        {"hour": 9, "minute": 0, "day": "Tuesday"},
        {"hour": 9, "minute": 0, "day": "Thursday"},
    ],
}

_DEFAULT_SLOT = [{"hour": 9, "minute": 0, "day": None}]


def get_optimal_post_time(platform: str, timezone: str = "Asia/Karachi") -> list[dict]:
    """Return optimal PKT posting slots for a platform.

    Each dict has keys: hour (int), minute (int), day (str|None).
    Unknown platforms fall back to 9am any day.
    """
    return _OPTIMAL_SLOTS.get(platform, _DEFAULT_SLOT)


def next_rotation_topic(topics: list[str], run_index: int) -> str:
    """Return the next topic from a rotation list using modulo index.

    Empty list returns empty string so callers can gate on it.
    """
    if not topics:
        return ""
    return topics[run_index % len(topics)]


async def list_scheduled_projects(db, tenant_id: str) -> list[dict]:
    """Return projects with schedule_enabled=True for a tenant."""
    cursor = db["projects"].find(
        {"tenant_id": tenant_id, "schedule_enabled": True, "is_active": True},
        {"_id": 0},
    )
    return await cursor.to_list(length=200)
