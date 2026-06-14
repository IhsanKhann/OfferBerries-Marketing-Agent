"""Stage-aware pipeline execution with human-in-the-loop support.

In 'controlled' mode each stage pauses after completion and waits for
human approval via the /runs/{id}/stage/{stage}/approve endpoint before
proceeding to the next stage.

In 'automated' mode all enabled stages run without pausing.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from models import (
    AgentRun,
    StageState,
    StageStatus,
    STAGE_ORDER,
    STAGE_TO_CONFIG_FIELD,
)

logger = logging.getLogger("crew.pipeline")

# In-memory synchronisation primitives, keyed by "{run_id}:{stage}"
_resume_events: dict[str, asyncio.Event] = {}
_edited_outputs: dict[str, dict] = {}
_cancelled: set[str] = set()


# ── Public control API (called by HTTP handlers) ───────────────────────────

def get_or_create_resume_event(run_id: str, stage: str) -> asyncio.Event:
    key = f"{run_id}:{stage}"
    if key not in _resume_events:
        _resume_events[key] = asyncio.Event()
    return _resume_events[key]


def signal_resume(run_id: str, stage: str, edited_output: Optional[dict] = None) -> bool:
    """Unblock a paused stage.  Returns False if no event was waiting."""
    key = f"{run_id}:{stage}"
    if edited_output is not None:
        _edited_outputs[key] = edited_output
    event = _resume_events.get(key)
    if event:
        event.set()
        return True
    return False


def cancel_run(run_id: str):
    _cancelled.add(run_id)
    for stage in STAGE_ORDER:
        event = _resume_events.get(f"{run_id}:{stage}")
        if event:
            event.set()


def is_cancelled(run_id: str) -> bool:
    return run_id in _cancelled


# ── Main pipeline coroutine ────────────────────────────────────────────────

async def execute_pipeline(run: AgentRun, db, redis_client):
    """Execute the agent pipeline stage by stage.

    Stores each stage's output in MongoDB before optionally pausing.
    Applies human edits to the AgentState before the next stage runs.
    """
    from graph import AgentState, research_node, content_node, visual_node, queue_node

    run_id = run.id

    state: AgentState = {
        "topic": run.topic,
        "platform_filter": run.platforms,
        "brief": None,
        "competitor_data": [],
        "platform_content": {},
        "visual_assets": {},
        "queued_posts": [],
        "errors": [],
        "run_id": run_id,
        "dry_run": False,
    }

    # Pre-populate with user-provided content when content stage is skipped
    if run.provided_content and not run.stages_enabled.content_generation:
        for platform in run.platforms:
            state["platform_content"][platform] = {
                "platform": platform,
                "copy": run.provided_content,
                "hashtags": [],
                "cta": "",
                "word_count": len(run.provided_content.split()),
                "estimated_reading_time": 1,
            }

    node_map = {
        "research": research_node,
        "content_generation": content_node,
        "visual_generation": visual_node,
        "scheduling": queue_node,
    }

    await _set_overall_status(db, redis_client, run_id, "running")

    for stage_name in STAGE_ORDER:
        if is_cancelled(run_id):
            await _set_overall_status(db, redis_client, run_id, "cancelled")
            _cleanup(run_id)
            return

        config_field = STAGE_TO_CONFIG_FIELD.get(stage_name, stage_name)
        enabled = getattr(run.stages_enabled, config_field, True)

        if not enabled:
            await _set_stage(db, redis_client, run_id, stage_name, StageState(
                status=StageStatus.SKIPPED,
                completed_at=datetime.now(timezone.utc),
            ))
            continue

        node = node_map.get(stage_name)
        if not node:
            continue

        # Save pre-stage state snapshot (enables re-run on reject)
        await _save_snapshot(db, run_id, state)
        await _set_current_stage(db, run_id, stage_name)
        await _set_stage(db, redis_client, run_id, stage_name, StageState(
            status=StageStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        ))

        try:
            state = await node(state)
        except Exception as exc:
            logger.error("Stage %s failed for run %s: %s", stage_name, run_id, exc)
            await _set_stage(db, redis_client, run_id, stage_name, StageState(
                status=StageStatus.FAILED,
                error={"message": str(exc)},
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
            ))
            await _set_overall_status(db, redis_client, run_id, "failed")
            _cleanup(run_id)
            return

        output = _extract_output(stage_name, state)

        post_status = StageStatus.PAUSED if run.execution_mode == "controlled" else StageStatus.APPROVED
        await _set_stage(db, redis_client, run_id, stage_name, StageState(
            status=post_status,
            output=output,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        ))

        if run.execution_mode == "controlled":
            await _set_overall_status(db, redis_client, run_id, "paused_for_review")
            event = get_or_create_resume_event(run_id, stage_name)
            await event.wait()
            event.clear()
            _resume_events.pop(f"{run_id}:{stage_name}", None)

            if is_cancelled(run_id):
                await _set_overall_status(db, redis_client, run_id, "cancelled")
                _cleanup(run_id)
                return

            edit_key = f"{run_id}:{stage_name}"
            edited = _edited_outputs.pop(edit_key, None)
            if edited is not None:
                state = _apply_edit(stage_name, state, edited)

            await _set_stage_status(db, redis_client, run_id, stage_name, StageStatus.APPROVED)
            await _set_overall_status(db, redis_client, run_id, "running")

    await _set_overall_status(db, redis_client, run_id, "completed")
    _cleanup(run_id)


async def rerun_stage(run: AgentRun, stage_name: str, db, redis_client):
    """Re-execute a single stage using the saved pre-stage state snapshot."""
    from graph import AgentState, research_node, content_node, visual_node, queue_node

    node_map = {
        "research": research_node,
        "content_generation": content_node,
        "visual_generation": visual_node,
        "scheduling": queue_node,
    }
    node = node_map.get(stage_name)
    if not node:
        return

    snapshot = run.state_snapshot or {}
    state: AgentState = {
        "topic": run.topic,
        "platform_filter": run.platforms,
        "brief": snapshot.get("brief"),
        "competitor_data": snapshot.get("competitor_data", []),
        "platform_content": snapshot.get("platform_content", {}),
        "visual_assets": snapshot.get("visual_assets", {}),
        "queued_posts": [],
        "errors": [],
        "run_id": run.id,
        "dry_run": False,
    }

    await _set_stage(db, redis_client, run.id, stage_name, StageState(
        status=StageStatus.RUNNING,
        started_at=datetime.now(timezone.utc),
    ))
    await _set_overall_status(db, redis_client, run.id, "running")

    try:
        state = await node(state)
    except Exception as exc:
        logger.error("Stage re-run %s failed for run %s: %s", stage_name, run.id, exc)
        await _set_stage(db, redis_client, run.id, stage_name, StageState(
            status=StageStatus.FAILED,
            error={"message": str(exc)},
            completed_at=datetime.now(timezone.utc),
        ))
        await _set_overall_status(db, redis_client, run.id, "failed")
        return

    output = _extract_output(stage_name, state)
    await _set_stage(db, redis_client, run.id, stage_name, StageState(
        status=StageStatus.PAUSED,
        output=output,
        completed_at=datetime.now(timezone.utc),
    ))
    await _set_overall_status(db, redis_client, run.id, "paused_for_review")

    # Store updated snapshot for potential further re-runs
    await _save_snapshot(db, run.id, state)


# ── State helpers ──────────────────────────────────────────────────────────

def _extract_output(stage_name: str, state: dict) -> Any:
    if stage_name == "research":
        return state.get("brief") or {}
    if stage_name == "content_generation":
        return state.get("platform_content") or {}
    if stage_name == "visual_generation":
        return state.get("visual_assets") or {}
    if stage_name == "scheduling":
        return {"queued_posts": state.get("queued_posts") or []}
    return {}


def _apply_edit(stage_name: str, state: dict, edited: dict) -> dict:
    if stage_name == "research":
        state["brief"] = edited
    elif stage_name == "content_generation":
        state["platform_content"] = edited
    elif stage_name == "visual_generation":
        state["visual_assets"] = edited
    return state


def _cleanup(run_id: str):
    _cancelled.discard(run_id)
    for stage in STAGE_ORDER:
        _resume_events.pop(f"{run_id}:{stage}", None)
        _edited_outputs.pop(f"{run_id}:{stage}", None)


# ── MongoDB / Redis persistence ────────────────────────────────────────────

async def _set_overall_status(db, redis_client, run_id: str, status: str):
    await db["agent_runs"].update_one(
        {"_id": run_id},
        {"$set": {"overall_status": status, "updated_at": datetime.now(timezone.utc)}},
    )
    await _publish(redis_client, run_id, {"type": "status_change", "status": status})


async def _set_current_stage(db, run_id: str, stage: str):
    await db["agent_runs"].update_one(
        {"_id": run_id},
        {"$set": {"current_stage": stage, "updated_at": datetime.now(timezone.utc)}},
    )


async def _set_stage(db, redis_client, run_id: str, stage: str, stage_state: StageState):
    await db["agent_runs"].update_one(
        {"_id": run_id},
        {"$set": {
            f"stages.{stage}": stage_state.model_dump(mode="json"),
            "updated_at": datetime.now(timezone.utc),
        }},
    )
    await _publish(redis_client, run_id, {
        "type": "stage_update",
        "stage": stage,
        "status": stage_state.status.value,
    })


async def _set_stage_status(db, redis_client, run_id: str, stage: str, status: StageStatus):
    await db["agent_runs"].update_one(
        {"_id": run_id},
        {"$set": {
            f"stages.{stage}.status": status.value,
            "updated_at": datetime.now(timezone.utc),
        }},
    )
    await _publish(redis_client, run_id, {
        "type": "stage_update", "stage": stage, "status": status.value,
    })


async def _save_snapshot(db, run_id: str, state: dict):
    safe = {
        "brief": state.get("brief"),
        "competitor_data": state.get("competitor_data", []),
        "platform_content": state.get("platform_content", {}),
        "visual_assets": state.get("visual_assets", {}),
    }
    await db["agent_runs"].update_one(
        {"_id": run_id},
        {"$set": {"state_snapshot": safe}},
    )


async def _publish(redis_client, run_id: str, event: dict):
    try:
        await redis_client.publish(f"run:{run_id}:events", json.dumps(event))
    except Exception:
        pass
