"""FastAPI wrapper around the LangGraph agent."""
import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional

import redis.asyncio as aioredis
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel

from graph import AgentState, build_graph
from models import (
    AgentRun,
    ApproveStageRequest,
    CreateRunRequest,
    EditStageRequest,
    StageState,
    StageStatus,
    STAGE_ORDER,
)
from pipeline import (
    cancel_run,
    execute_pipeline,
    is_cancelled,
    rerun_stage,
    signal_resume,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("crew.run_weekly")

app = FastAPI(title="OfferBerries Crew Runner", version="1.0.0")
_start_time = time.time()

OWNER_KEY = os.getenv("OWNER_API_KEY", "")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
MONGODB_URI = os.getenv("MONGODB_URI", "")
MONGODB_DB = os.getenv("MONGODB_DB", "offerberries_agent")

redis_client: Optional[aioredis.Redis] = None
mongo_client: Optional[AsyncIOMotorClient] = None
db = None
agent_graph = None


@app.on_event("startup")
async def startup():
    global redis_client, mongo_client, db, agent_graph
    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    if MONGODB_URI:
        mongo_client = AsyncIOMotorClient(MONGODB_URI)
        db = mongo_client[MONGODB_DB]
    agent_graph = build_graph()


@app.on_event("shutdown")
async def shutdown():
    if redis_client:
        await redis_client.close()
    if mongo_client:
        mongo_client.close()


def _require_owner(x_api_key: Optional[str]):
    if not OWNER_KEY or x_api_key != OWNER_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/health")
async def health():
    return {"status": "ok", "uptime_seconds": int(time.time() - _start_time)}


class RunRequest(BaseModel):
    topic: str
    platform_filter: list[str] = ["linkedin", "twitter", "instagram"]
    dry_run: bool = False


@app.post("/agent/run")
async def start_run(
    req: RunRequest,
    x_api_key: Optional[str] = Header(None),
):
    _require_owner(x_api_key)
    run_id = str(uuid.uuid4())

    initial_state: AgentState = {
        "topic": req.topic,
        "platform_filter": req.platform_filter,
        "brief": None,
        "competitor_data": [],
        "platform_content": {},
        "visual_assets": {},
        "queued_posts": [],
        "errors": [],
        "run_id": run_id,
        "dry_run": req.dry_run,
    }

    await redis_client.setex(
        f"run:{run_id}",
        86400,
        json.dumps({"status": "started", "state": initial_state, "started_at": datetime.now(timezone.utc).isoformat()}),
    )

    asyncio.create_task(_run_agent(run_id, initial_state))

    check_url = f"/agent/status/{run_id}"
    return {"run_id": run_id, "status": "started", "check_url": check_url}


async def _run_agent(run_id: str, initial_state: AgentState):
    try:
        await _update_run(run_id, "running", initial_state)
        final_state = await agent_graph.ainvoke(initial_state)
        await _update_run(run_id, "completed", final_state)
        if db:
            await db["runs"].insert_one({
                "run_id": run_id,
                "status": "completed",
                "state": _serialise(final_state),
                "completed_at": datetime.now(timezone.utc),
            })
    except Exception as e:
        logger.error(f"Agent run {run_id} failed: {e}")
        await _update_run(run_id, "failed", initial_state, error=str(e))
        if db:
            await db["runs"].insert_one({
                "run_id": run_id,
                "status": "failed",
                "error": str(e),
                "completed_at": datetime.now(timezone.utc),
            })


async def _update_run(run_id: str, status: str, state: dict, error: str = ""):
    payload = {"status": status, "state": _serialise(state), "updated_at": datetime.now(timezone.utc).isoformat()}
    if error:
        payload["error"] = error
    await redis_client.setex(f"run:{run_id}", 86400, json.dumps(payload))


def _serialise(obj):
    if isinstance(obj, dict):
        return {k: _serialise(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialise(i) for i in obj]
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


@app.get("/agent/status/{run_id}")
async def get_status(run_id: str, x_api_key: Optional[str] = Header(None)):
    _require_owner(x_api_key)
    raw = await redis_client.get(f"run:{run_id}")
    if not raw:
        if db:
            doc = await db["runs"].find_one({"run_id": run_id})
            if doc:
                doc.pop("_id", None)
                return doc
        raise HTTPException(status_code=404, detail="Run not found")
    return json.loads(raw)


@app.get("/agent/history")
async def get_history(x_api_key: Optional[str] = Header(None)):
    _require_owner(x_api_key)
    if not db:
        return []
    cursor = db["runs"].find({}, {"_id": 0, "run_id": 1, "status": 1, "completed_at": 1}).sort("completed_at", -1).limit(20)
    return await cursor.to_list(length=20)


@app.post("/analytics/collect")
async def collect_analytics(x_api_key: Optional[str] = Header(None)):
    _require_owner(x_api_key)
    try:
        from analytics_worker import collect_analytics_data
        await collect_analytics_data()
        return {"status": "ok"}
    except ImportError:
        return {"status": "ok", "note": "analytics_worker not yet implemented"}


@app.post("/analytics/extract-patterns")
async def extract_patterns_endpoint(x_api_key: Optional[str] = Header(None)):
    _require_owner(x_api_key)
    try:
        from pattern_extractor import extract_patterns
        changes = await extract_patterns(os.getenv("OWNER_TENANT_ID", ""))
        return {"status": "ok", "changes": changes}
    except ImportError:
        return {"status": "ok", "changes": {}, "note": "pattern_extractor not yet implemented"}


# ── Ensure indexes exist on startup ───────────────────────────────────────

async def _ensure_indexes():
    if db is None:
        return
    coll = db["agent_runs"]
    await coll.create_index([("tenant_id", 1), ("overall_status", 1), ("created_at", -1)])


@app.on_event("startup")
async def _extra_startup():
    await _ensure_indexes()


# ── /runs endpoints ────────────────────────────────────────────────────────

def _tenant_id() -> str:
    return os.getenv("OWNER_TENANT_ID", "owner")


@app.post("/runs", status_code=201)
async def create_run(
    req: CreateRunRequest,
    x_api_key: Optional[str] = Header(None),
):
    """Create and immediately start an agent run."""
    _require_owner(x_api_key)
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    run = AgentRun(
        tenant_id=_tenant_id(),
        topic=req.topic,
        platforms=req.platforms,
        execution_mode=req.execution_mode,
        stages_enabled=req.stages_enabled,
        provided_content=req.provided_content,
    )

    await db["agent_runs"].insert_one(run.to_mongo())

    asyncio.create_task(execute_pipeline(run, db, redis_client))

    return {"run_id": run.id, "status": run.overall_status}


@app.get("/runs")
async def list_runs(
    limit: int = 20,
    status: Optional[str] = None,
    x_api_key: Optional[str] = Header(None),
):
    _require_owner(x_api_key)
    if not db:
        return []
    query: dict = {"tenant_id": _tenant_id()}
    if status:
        query["overall_status"] = status
    cursor = db["agent_runs"].find(query, {"state_snapshot": 0}).sort("created_at", -1).limit(limit)
    docs = await cursor.to_list(length=limit)
    for doc in docs:
        doc["id"] = str(doc.pop("_id"))
        for k in ("created_at", "updated_at"):
            if doc.get(k) and hasattr(doc[k], "isoformat"):
                doc[k] = doc[k].isoformat()
    return docs


@app.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    x_api_key: Optional[str] = Header(None),
):
    _require_owner(x_api_key)
    doc = await _fetch_run_doc(run_id)
    doc.pop("state_snapshot", None)
    return doc


@app.get("/runs/{run_id}/stage/{stage}")
async def get_stage_output(
    run_id: str,
    stage: str,
    x_api_key: Optional[str] = Header(None),
):
    _require_owner(x_api_key)
    if stage not in STAGE_ORDER:
        raise HTTPException(status_code=400, detail=f"Unknown stage: {stage}")
    doc = await _fetch_run_doc(run_id)
    stage_data = doc.get("stages", {}).get(stage, {})
    return {"stage": stage, "run_id": run_id, **stage_data}


@app.post("/runs/{run_id}/stage/{stage}/approve")
async def approve_stage(
    run_id: str,
    stage: str,
    req: ApproveStageRequest,
    x_api_key: Optional[str] = Header(None),
):
    _require_owner(x_api_key)
    if stage not in STAGE_ORDER:
        raise HTTPException(status_code=400, detail=f"Unknown stage: {stage}")

    doc = await _fetch_run_doc(run_id)
    stage_status = doc.get("stages", {}).get(stage, {}).get("status")
    if stage_status == StageStatus.APPROVED.value:
        return {"approved": True, "run_id": run_id, "stage": stage, "idempotent": True}
    if stage_status != StageStatus.PAUSED.value:
        raise HTTPException(status_code=409, detail=f"Stage '{stage}' is not paused (status: {stage_status})")

    resumed = signal_resume(run_id, stage, edited_output=req.edited_output)
    return {"approved": True, "run_id": run_id, "stage": stage, "resumed": resumed}


@app.post("/runs/{run_id}/stage/{stage}/edit")
async def edit_stage(
    run_id: str,
    stage: str,
    req: EditStageRequest,
    x_api_key: Optional[str] = Header(None),
):
    _require_owner(x_api_key)
    if stage not in STAGE_ORDER:
        raise HTTPException(status_code=400, detail=f"Unknown stage: {stage}")

    # Store the edit and approve (proceed with edited output)
    resumed = signal_resume(run_id, stage, edited_output=req.output)
    return {"edited": True, "run_id": run_id, "stage": stage, "resumed": resumed}


@app.post("/runs/{run_id}/stage/{stage}/reject")
async def reject_stage(
    run_id: str,
    stage: str,
    x_api_key: Optional[str] = Header(None),
):
    """Re-run a stage from its saved pre-stage state snapshot."""
    _require_owner(x_api_key)
    if stage not in STAGE_ORDER:
        raise HTTPException(status_code=400, detail=f"Unknown stage: {stage}")
    if not db:
        raise HTTPException(status_code=503, detail="Database not available")

    doc = await _fetch_run_doc(run_id)
    run = AgentRun.from_mongo({**doc, "_id": run_id})

    asyncio.create_task(rerun_stage(run, stage, db, redis_client))
    return {"rejected": True, "run_id": run_id, "stage": stage}


@app.post("/runs/{run_id}/resume")
async def resume_run(
    run_id: str,
    x_api_key: Optional[str] = Header(None),
):
    _require_owner(x_api_key)
    doc = await _fetch_run_doc(run_id)
    current_stage = doc.get("current_stage", "research")
    resumed = signal_resume(run_id, current_stage)
    return {"resumed": resumed, "run_id": run_id, "stage": current_stage}


@app.delete("/runs/{run_id}")
async def cancel_run_endpoint(
    run_id: str,
    x_api_key: Optional[str] = Header(None),
):
    _require_owner(x_api_key)
    cancel_run(run_id)
    if db:
        await db["agent_runs"].update_one(
            {"_id": run_id},
            {"$set": {"overall_status": "cancelled", "updated_at": datetime.now(timezone.utc)}},
        )
    return {"cancelled": True, "run_id": run_id}


@app.get("/runs/{run_id}/stream")
async def stream_run_events(
    run_id: str,
    request: Request,
    x_api_key: Optional[str] = Header(None),
):
    """Server-Sent Events stream for real-time stage updates."""
    _require_owner(x_api_key)

    async def event_generator() -> AsyncGenerator[str, None]:
        # Send current state immediately
        doc = await _fetch_run_doc(run_id, raise_404=False)
        if doc:
            yield f"data: {json.dumps({'type': 'snapshot', 'run': doc})}\n\n"

        pubsub = redis_client.pubsub()
        await pubsub.subscribe(f"run:{run_id}:events")
        try:
            while True:
                if await request.is_disconnected():
                    break
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg:
                    yield f"data: {msg['data']}\n\n"
                    data = json.loads(msg["data"])
                    if data.get("status") in ("completed", "failed", "cancelled"):
                        break
                else:
                    yield ": keepalive\n\n"
        finally:
            await pubsub.unsubscribe(f"run:{run_id}:events")
            await pubsub.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Helper ─────────────────────────────────────────────────────────────────

async def _fetch_run_doc(run_id: str, raise_404: bool = True) -> dict:
    if not db:
        if raise_404:
            raise HTTPException(status_code=503, detail="Database not available")
        return {}
    doc = await db["agent_runs"].find_one({"_id": run_id})
    if not doc:
        if raise_404:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
        return {}
    doc["id"] = str(doc.pop("_id"))
    for k in ("created_at", "updated_at"):
        if doc.get(k) and hasattr(doc[k], "isoformat"):
            doc[k] = doc[k].isoformat()
    return doc


# ──────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", default="OfferBerries HR payroll module")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    async def _cli():
        global redis_client, agent_graph
        redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
        agent_graph = build_graph()

        run_id = str(uuid.uuid4())
        state: AgentState = {
            "topic": args.topic,
            "platform_filter": ["linkedin", "twitter"],
            "brief": None,
            "competitor_data": [],
            "platform_content": {},
            "visual_assets": {},
            "queued_posts": [],
            "errors": [],
            "run_id": run_id,
            "dry_run": args.dry_run,
        }
        print(f"Starting run {run_id} for topic: {args.topic}")
        final = await agent_graph.ainvoke(state)
        print(f"Completed. Queued posts: {len(final.get('queued_posts', []))}")
        print(f"Errors: {final.get('errors', [])}")
        await redis_client.close()

    asyncio.run(_cli())
