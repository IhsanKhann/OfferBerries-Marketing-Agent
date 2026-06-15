"""Queue, render, and analytics REST endpoints."""
import os
from datetime import datetime, timezone
from typing import Optional

import httpx
import main as _m
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import Response as FastAPIResponse

from tools.analytics import tool_get_analytics

router = APIRouter()


@router.get("/queue")
async def rest_get_queue(
    platform: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await _m.get_tenant(x_api_key, authorization)
    query: dict = {"tenant_id": tenant.tenant_id}
    if platform and platform != "all":
        query["platform"] = platform
    if status:
        query["status"] = status
    cursor = _m.db["posts"].find(query, {"_id": 0}).sort("created_at", -1).limit(limit)
    posts = await cursor.to_list(length=limit)
    for p in posts:
        if "created_at" in p:
            p["created_at"] = p["created_at"].isoformat() if hasattr(p["created_at"], "isoformat") else str(p["created_at"])
    return posts


@router.post("/queue/{post_id}/approve")
async def rest_approve_post(
    post_id: str,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await _m.get_tenant(x_api_key, authorization)
    result = await _m.db["posts"].update_one(
        {"postiz_id": post_id, "tenant_id": tenant.tenant_id},
        {"$set": {"status": "approved", "approved_at": datetime.now(timezone.utc)}},
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"approved": True, "post_id": post_id}


@router.delete("/queue/{post_id}")
async def rest_delete_post(
    post_id: str,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await _m.get_tenant(x_api_key, authorization)
    result = await _m.db["posts"].delete_one(
        {"postiz_id": post_id, "tenant_id": tenant.tenant_id}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"deleted": True, "post_id": post_id}


@router.post("/render")
async def render_template(
    request: Request,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    await _m.get_tenant(x_api_key, authorization)
    renderer_url = os.getenv("RENDERER_URL", "http://renderer:3001")
    body = await request.body()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{renderer_url}/render",
            content=body,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
    return FastAPIResponse(content=resp.content, media_type="image/png")


@router.get("/analytics")
async def rest_get_analytics(
    platform: str = "all",
    days: int = 7,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await _m.get_tenant(x_api_key, authorization)
    return await tool_get_analytics(platform=platform, days=days, tenant_id=tenant.tenant_id)
