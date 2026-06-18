"""arq worker process for durable pipeline execution.

Runs the agent pipeline outside the web process so a web restart never orphans
an in-flight run. Control signals (resume/cancel/edit) are exchanged with the
web process through Redis keys (see pipeline.py).

Start with:  arq worker.WorkerSettings
"""
import logging
import os

import redis.asyncio as aioredis
from arq.connections import RedisSettings
from motor.motor_asyncio import AsyncIOMotorClient

from models import AgentRun
from pipeline import execute_pipeline, rerun_stage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("crew.worker")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
MONGODB_URI = os.getenv("MONGODB_URI", "")
MONGODB_DB = os.getenv("MONGODB_DB", "offerberries_agent")


async def _load_run(db, run_id: str):
    doc = await db["agent_runs"].find_one({"_id": run_id})
    if not doc:
        logger.warning("Run %s not found — skipping job", run_id)
        return None
    return AgentRun.from_mongo(doc)


async def execute_pipeline_job(ctx, run_id: str):
    run = await _load_run(ctx["db"], run_id)
    if run:
        await execute_pipeline(run, ctx["db"], ctx["redis_client"])


async def rerun_stage_job(ctx, run_id: str, stage: str):
    run = await _load_run(ctx["db"], run_id)
    if run:
        await rerun_stage(run, stage, ctx["db"], ctx["redis_client"])


async def on_startup(ctx):
    ctx["mongo"] = AsyncIOMotorClient(MONGODB_URI)
    ctx["db"] = ctx["mongo"][MONGODB_DB]
    ctx["redis_client"] = aioredis.from_url(REDIS_URL, decode_responses=True)
    logger.info("crew worker started")


async def on_shutdown(ctx):
    mongo = ctx.get("mongo")
    if mongo:
        mongo.close()
    rc = ctx.get("redis_client")
    if rc:
        await rc.close()


class WorkerSettings:
    functions = [execute_pipeline_job, rerun_stage_job]
    on_startup = on_startup
    on_shutdown = on_shutdown
    redis_settings = RedisSettings.from_dsn(REDIS_URL)
    # Controlled-mode runs can pause for human review, so allow long jobs.
    job_timeout = 3600
    max_jobs = 10
    keep_result = 3600
