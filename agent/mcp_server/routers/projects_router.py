"""Projects CRUD endpoints."""
import uuid
from datetime import datetime, timezone
from typing import Optional

import main as _m
from fastapi import APIRouter, Header, HTTPException

from schemas import ProjectCreateRequest, ProjectUpdateRequest

router = APIRouter()


@router.get("/projects")
async def list_projects(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await _m.get_tenant(x_api_key, authorization)
    cursor = _m.db["projects"].find(
        {"tenant_id": tenant.tenant_id, "is_active": True}, {"_id": 0}
    ).sort("name", 1)
    projects = await cursor.to_list(length=200)

    if projects:
        project_ids = [p["id"] for p in projects]
        pipeline = [
            {"$match": {"project_id": {"$in": project_ids}}},
            {"$group": {"_id": "$project_id", "count": {"$sum": 1}}},
        ]
        counts: dict[str, int] = {}
        async for doc in _m.db["agent_runs"].aggregate(pipeline):
            counts[doc["_id"]] = doc["count"]
        for p in projects:
            p["run_count"] = counts.get(p["id"], 0)
            for k in ("created_at", "updated_at", "archived_at"):
                if p.get(k) and hasattr(p[k], "isoformat"):
                    p[k] = p[k].isoformat()

    return projects


@router.post("/projects", status_code=201)
async def create_project(
    req: ProjectCreateRequest,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await _m.get_tenant(x_api_key, authorization)
    project_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    doc = {
        **req.model_dump(),
        "id": project_id,
        "tenant_id": tenant.tenant_id,
        "starred": False,
        "is_active": True,
        "archived_at": None,
        "created_at": now,
        "updated_at": now,
    }
    await _m.db["projects"].insert_one(doc)
    doc.pop("_id", None)
    doc["run_count"] = 0
    for k in ("created_at", "updated_at"):
        if doc.get(k) and hasattr(doc[k], "isoformat"):
            doc[k] = doc[k].isoformat()
    return doc


@router.get("/projects/{project_id}")
async def get_project(
    project_id: str,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await _m.get_tenant(x_api_key, authorization)
    doc = await _m.db["projects"].find_one(
        {"id": project_id, "tenant_id": tenant.tenant_id, "is_active": True}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Project not found")
    for k in ("created_at", "updated_at", "archived_at"):
        if doc.get(k) and hasattr(doc[k], "isoformat"):
            doc[k] = doc[k].isoformat()
    return doc


@router.patch("/projects/{project_id}")
async def update_project(
    project_id: str,
    req: ProjectUpdateRequest,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await _m.get_tenant(x_api_key, authorization)
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    updates["updated_at"] = datetime.now(timezone.utc)
    result = await _m.db["projects"].update_one(
        {"id": project_id, "tenant_id": tenant.tenant_id, "is_active": True},
        {"$set": updates},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"updated": True, "id": project_id}


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: str,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant = await _m.get_tenant(x_api_key, authorization)
    doc = await _m.db["projects"].find_one(
        {"id": project_id, "tenant_id": tenant.tenant_id}, {"id": 1}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Project not found")
    await _m.db["projects"].update_one(
        {"id": project_id, "tenant_id": tenant.tenant_id},
        {"$set": {"is_active": False, "archived_at": datetime.now(timezone.utc)}},
    )
    return {"deleted": True, "id": project_id}
