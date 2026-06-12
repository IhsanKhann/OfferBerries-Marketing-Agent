"""FastAPI wrapper around the LangGraph agent."""
import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import redis.asyncio as aioredis
from fastapi import FastAPI, Header, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel

from graph import AgentState, build_graph

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
