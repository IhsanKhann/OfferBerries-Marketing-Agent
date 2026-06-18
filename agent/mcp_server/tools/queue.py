"""Post queueing tool."""
import hashlib
import logging
import os
import uuid
from datetime import datetime, timezone

import httpx

from schemas import QueuedPost

logger = logging.getLogger("mcp_server")


async def tool_queue_post(
    platform: str,
    caption: str,
    image_path: str,
    scheduled_at: str,
    tenant_id: str,
    run_id: str,
    preview_url: str = "",
) -> dict:
    import main as _m

    postiz_secret = os.getenv("POSTIZ_SECRET", "")
    postiz_url = os.getenv("POSTIZ_URL", "http://postiz:3000")

    mock_id = str(uuid.uuid4())
    if not postiz_secret:
        queued = QueuedPost(postiz_id=mock_id, platform=platform, scheduled_at=scheduled_at, preview_url=preview_url)
    else:
        postiz_id = mock_id
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{postiz_url}/api/posts",
                    headers={"Authorization": f"Bearer {postiz_secret}"},
                    json={"content": caption, "date": scheduled_at, "platform": platform},
                )
                if resp.status_code < 400:
                    postiz_id = resp.json().get("id", mock_id)
                else:
                    logger.warning(f"Postiz returned {resp.status_code}, using mock ID")
        except Exception as e:
            logger.warning(f"Postiz unavailable: {e}, using mock ID")
        queued = QueuedPost(postiz_id=postiz_id, platform=platform, scheduled_at=scheduled_at, preview_url=preview_url)

    now = datetime.now(timezone.utc)
    fields = {
        "tenant_id": tenant_id,
        "run_id": run_id,
        "platform": platform,
        "caption": caption,
        "caption_hash": hashlib.sha256(caption.encode()).hexdigest(),
        "postiz_id": queued.postiz_id,
        "preview_url": preview_url,
        "scheduled_at": scheduled_at,
        "status": "scheduled",
        "updated_at": now,
    }
    # Upsert onto the post already persisted at content time (Fix 4) so we update
    # it to "scheduled" instead of creating a duplicate. Fall back to insert when
    # no run_id is available (legacy callers).
    if run_id:
        await _m.db["posts"].update_one(
            {"run_id": run_id, "platform": platform},
            {"$set": fields, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
    else:
        await _m.db["posts"].insert_one({**fields, "created_at": now})

    return queued.model_dump()
