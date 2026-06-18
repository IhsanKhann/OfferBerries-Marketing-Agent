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
import os
import uuid
from datetime import datetime, timezone

import httpx
from typing import Any, Optional

from models import (
    AgentRun,
    StageState,
    StageStatus,
    STAGE_ORDER,
    STAGE_TO_CONFIG_FIELD,
)

logger = logging.getLogger("crew.pipeline")

# Control signals are stored in Redis (not in process memory) so they survive a
# crash/restart and work across the web process and the arq worker process.
_SIGNAL_TTL = 86400
_POLL_INTERVAL = 2.0
_CANCELLED = object()  # sentinel returned by _wait_for_resume on cancellation


def _cancel_key(run_id: str) -> str:
    return f"run:{run_id}:cancel"


def _resume_key(run_id: str, stage: str) -> str:
    return f"run:{run_id}:resume:{stage}"


def _edit_key(run_id: str, stage: str) -> str:
    return f"run:{run_id}:edit:{stage}"


# ── Public control API (called by HTTP handlers, in the web process) ────────

async def signal_resume(redis_client, run_id: str, stage: str, edited_output: Optional[dict] = None) -> bool:
    """Unblock a paused stage by writing a Redis signal the worker polls for."""
    if edited_output is not None:
        await redis_client.set(_edit_key(run_id, stage), json.dumps(edited_output), ex=_SIGNAL_TTL)
    await redis_client.set(_resume_key(run_id, stage), "1", ex=_SIGNAL_TTL)
    return True


async def cancel_run(redis_client, run_id: str) -> None:
    await redis_client.set(_cancel_key(run_id), "1", ex=_SIGNAL_TTL)


async def is_cancelled(redis_client, run_id: str) -> bool:
    return bool(await redis_client.exists(_cancel_key(run_id)))


async def _wait_for_resume(redis_client, run_id: str, stage: str):
    """Poll Redis until the stage is resumed or the run is cancelled.

    Returns the edited output dict (or None) on resume, or the _CANCELLED
    sentinel if the run was cancelled while paused.
    """
    resume_key = _resume_key(run_id, stage)
    edit_key = _edit_key(run_id, stage)
    while True:
        if await redis_client.exists(_cancel_key(run_id)):
            return _CANCELLED
        if await redis_client.exists(resume_key):
            edited_raw = await redis_client.get(edit_key)
            await redis_client.delete(resume_key, edit_key)
            if edited_raw:
                try:
                    return json.loads(edited_raw)
                except (ValueError, TypeError):
                    return None
            return None
        await asyncio.sleep(_POLL_INTERVAL)


async def _clear_signals(redis_client, run_id: str) -> None:
    keys = [_cancel_key(run_id)]
    for stage in STAGE_ORDER:
        keys.append(_resume_key(run_id, stage))
        keys.append(_edit_key(run_id, stage))
    try:
        await redis_client.delete(*keys)
    except Exception:
        pass


# ── Config helpers ─────────────────────────────────────────────────────────

async def _get_config(db, tenant_id: str, key: str, default: str) -> str:
    """Read a tenant config value (configs collection) with a fallback default."""
    try:
        doc = await db["configs"].find_one({"tenant_id": tenant_id, "key": key})
        if doc and doc.get("value"):
            return doc["value"]
    except Exception:
        pass
    return default


# ── Topic extraction ───────────────────────────────────────────────────────

async def _extract_topic(raw_topic: str, model: str = "anthropic/claude-sonnet-4-6") -> str:
    """Turn a conversational request into a clean 3-8 word research topic so the
    agent researches/markets the product, not the user's literal sentence."""
    key = os.getenv("OPENROUTER_API_KEY", "")
    if not key or not raw_topic.strip():
        return raw_topic
    system = "You extract clean research topics from conversational user inputs."
    user = (
        "Extract the core research topic from this request, as a clean 3-8 word phrase "
        "suitable for a Perplexity search query. Remove conversational filler. "
        "Return ONLY the topic phrase, nothing else.\n"
        f'Input: "{raw_topic}"'
    )
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": model,
                    "max_tokens": 40,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
            )
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"].strip()
        clean = text.split("\n")[0].strip().strip('"').strip()
        return clean or raw_topic
    except Exception as exc:
        logger.warning("Topic extraction failed (%s); using raw topic", exc)
        return raw_topic


# ── Post persistence ───────────────────────────────────────────────────────

async def _persist_posts(db, run, state: dict):
    """Persist generated posts to the `posts` collection as soon as content is
    produced — independent of the (optional) scheduling stage. Idempotent per
    (run_id, platform). Hashtags/cta/hook are stored as separate fields."""
    platform_content = state.get("platform_content") or {}
    visual_assets = state.get("visual_assets") or {}
    now = datetime.now(timezone.utc)
    for platform, content in platform_content.items():
        if platform == "linkedin_carousel" or not isinstance(content, dict):
            continue
        copy_text = content.get("copy", "") or ""
        hook = copy_text.split("\n", 1)[0].strip() if copy_text else ""
        visual_url = (visual_assets.get(platform) or {}).get("url") if isinstance(visual_assets.get(platform), dict) else None
        try:
            await db["posts"].update_one(
                {"run_id": run.id, "platform": platform},
                {
                    "$set": {
                        "run_id": run.id,
                        "tenant_id": run.tenant_id,
                        "platform": platform,
                        "copy": copy_text,
                        "caption": copy_text,          # legacy field kept populated
                        "hashtags": content.get("hashtags", []) or [],
                        "cta": content.get("cta", "") or "",
                        "hook": hook,
                        "visual_url": visual_url,
                        "preview_url": visual_url or "",
                        "status": "pending_review",
                        "updated_at": now,
                    },
                    "$setOnInsert": {
                        "postiz_id": str(uuid.uuid4()),
                        "scheduled_at": now.isoformat(),
                        "created_at": now,
                    },
                },
                upsert=True,
            )
        except Exception as exc:
            logger.error("Persisting post for run %s/%s failed: %s", run.id, platform, exc)


async def _update_post_visuals(db, run_id: str, visual_assets: dict):
    """Attach generated visual URLs to the run's already-persisted posts."""
    now = datetime.now(timezone.utc)
    for platform, asset in (visual_assets or {}).items():
        if not isinstance(asset, dict):
            continue
        url = asset.get("url")
        if not url:
            continue
        try:
            await db["posts"].update_one(
                {"run_id": run_id, "platform": platform},
                {"$set": {"visual_url": url, "preview_url": url, "updated_at": now}},
            )
        except Exception as exc:
            logger.error("Updating post visual for run %s/%s failed: %s", run_id, platform, exc)


async def _persist_stage_artifacts(db, run, stage_name: str, state: dict):
    if stage_name == "content_generation":
        await _persist_posts(db, run, state)
    elif stage_name == "visual_generation":
        await _update_post_visuals(db, run.id, state.get("visual_assets") or {})


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

    # Resolve tenant-configured models (Settings page writes these to configs)
    state["content_model"] = await _get_config(
        db, run.tenant_id, "content_model", "anthropic/claude-sonnet-4-6"
    )
    state["research_model"] = await _get_config(db, run.tenant_id, "research_model", "sonar")

    # Sanitize the conversational topic into a clean research query
    raw_topic = run.topic
    clean_topic = await _extract_topic(raw_topic, state["content_model"])
    state["raw_topic"] = raw_topic
    state["topic"] = clean_topic
    if clean_topic != raw_topic:
        logger.info("[%s] Topic extracted: %r -> %r", run_id, raw_topic, clean_topic)
    await db["agent_runs"].update_one(
        {"_id": run_id},
        {"$set": {"raw_topic": raw_topic, "clean_topic": clean_topic}},
    )

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
        if await is_cancelled(redis_client, run_id):
            await _set_overall_status(db, redis_client, run_id, "cancelled")
            await _clear_signals(redis_client, run_id)
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
            await _clear_signals(redis_client, run_id)
            return

        output = _extract_output(stage_name, state)

        # Persist generated posts/visuals immediately — do not wait for scheduling
        await _persist_stage_artifacts(db, run, stage_name, state)

        post_status = StageStatus.PAUSED if run.execution_mode == "controlled" else StageStatus.APPROVED
        await _set_stage(db, redis_client, run_id, stage_name, StageState(
            status=post_status,
            output=output,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        ))

        if run.execution_mode == "controlled":
            await _set_overall_status(db, redis_client, run_id, "paused_for_review")
            edited = await _wait_for_resume(redis_client, run_id, stage_name)

            if edited is _CANCELLED:
                await _set_overall_status(db, redis_client, run_id, "cancelled")
                await _clear_signals(redis_client, run_id)
                return

            if edited is not None:
                state = _apply_edit(stage_name, state, edited)
                # Re-persist so human edits are reflected in the queued posts
                await _persist_stage_artifacts(db, run, stage_name, state)

            await _set_stage_status(db, redis_client, run_id, stage_name, StageStatus.APPROVED)
            await _set_overall_status(db, redis_client, run_id, "running")

    await _set_overall_status(db, redis_client, run_id, "completed")
    await _clear_signals(redis_client, run_id)


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
    topic_doc = await db["agent_runs"].find_one({"_id": run.id}, {"clean_topic": 1})
    topic = (topic_doc or {}).get("clean_topic") or run.topic
    state: AgentState = {
        "topic": topic,
        "platform_filter": run.platforms,
        "brief": snapshot.get("brief"),
        "competitor_data": snapshot.get("competitor_data", []),
        "platform_content": snapshot.get("platform_content", {}),
        "visual_assets": snapshot.get("visual_assets", {}),
        "queued_posts": [],
        "errors": [],
        "run_id": run.id,
        "dry_run": False,
        "content_model": await _get_config(db, run.tenant_id, "content_model", "anthropic/claude-sonnet-4-6"),
        "research_model": await _get_config(db, run.tenant_id, "research_model", "sonar"),
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
