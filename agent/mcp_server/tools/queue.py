"""Post queueing tool — saves to MongoDB; n8n handles publishing."""
import hashlib
import logging
import uuid
from datetime import datetime, timezone

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

    post_id = str(uuid.uuid4())
    queued = QueuedPost(
        postiz_id=post_id,
        platform=platform,
        scheduled_at=scheduled_at,
        preview_url=preview_url,
    )

    now = datetime.now(timezone.utc)
    fields = {
        "tenant_id": tenant_id,
        "run_id": run_id,
        "platform": platform,
        "caption": caption,
        "caption_hash": hashlib.sha256(caption.encode()).hexdigest(),
        "postiz_id": post_id,
        "preview_url": preview_url,
        "scheduled_at": scheduled_at,
        "status": "scheduled",
        "updated_at": now,
    }
    if run_id:
        await _m.db["posts"].update_one(
            {"run_id": run_id, "platform": platform},
            {"$set": fields, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
    else:
        await _m.db["posts"].insert_one({**fields, "created_at": now})

    logger.info("Queued %s post %s for %s", platform, post_id, scheduled_at)
    return queued.model_dump()
