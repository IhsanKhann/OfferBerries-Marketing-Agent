"""Integration tests for stage-aware pipeline execution — B1 requirement.

All graph node functions are mocked so no external API calls are made.
MongoDB and Redis are represented by lightweight async fakes.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from models import AgentRun, StageStatus, StagesConfig, STAGE_ORDER
from pipeline import (
    execute_pipeline,
    rerun_stage,
    signal_resume,
    cancel_run,
    is_cancelled,
    _resume_events,
    _cancelled,
)


# ── Lightweight fakes ──────────────────────────────────────────────────────

class FakeCollection:
    """In-memory MongoDB collection fake."""

    def __init__(self):
        self._docs: dict = {}
        self.update_calls: list = []
        self.create_index = AsyncMock()

    async def insert_one(self, doc):
        _id = doc.get("_id", "unknown")
        self._docs[_id] = dict(doc)

    async def find_one(self, query):
        _id = query.get("_id") if isinstance(query, dict) else query
        return self._docs.get(_id)

    async def update_one(self, query, update):
        _id = query.get("_id")
        if _id not in self._docs:
            return
        self.update_calls.append((_id, update))
        doc = self._docs[_id]
        set_fields = update.get("$set", {})
        for key, val in set_fields.items():
            if "." in key:
                parts = key.split(".", 1)
                if parts[0] not in doc:
                    doc[parts[0]] = {}
                doc[parts[0]][parts[1]] = val
            else:
                doc[key] = val


class FakeDB:
    def __init__(self):
        self._colls: dict[str, FakeCollection] = {}

    def __getitem__(self, name: str) -> FakeCollection:
        if name not in self._colls:
            self._colls[name] = FakeCollection()
        return self._colls[name]


class FakeRedis:
    def __init__(self):
        self.published: list = []

    async def publish(self, channel: str, message: str):
        self.published.append((channel, json.loads(message)))

    async def subscribe(self, *args):
        pass


# ── Node stubs ──────────────────────────────────────────────────────────────

async def stub_research(state):
    state["brief"] = {
        "topic": state["topic"],
        "trending_angles": ["EOBI compliance", "Payroll automation"],
        "pain_points": ["Manual errors"],
        "suggested_hooks": ["Did you know?"],
        "platform_notes": {},
        "generated_at": "2026-06-14T00:00:00Z",
    }
    return state


async def stub_content(state):
    for platform in state.get("platform_filter", ["linkedin"]):
        state["platform_content"][platform] = {
            "platform": platform,
            "copy": f"Great post about {state['topic']} for {platform}",
            "hashtags": ["#Payroll"],
            "cta": "Learn more",
            "word_count": 10,
            "estimated_reading_time": 1,
        }
    return state


async def stub_visual(state):
    for platform in state.get("platform_filter", ["linkedin"]):
        state["visual_assets"][platform] = {"url": f"https://img/{platform}.png"}
    return state


async def stub_queue(state):
    state["queued_posts"] = [{"id": "p1", "status": "queued"}]
    return state


NODE_PATCHES = {
    "pipeline.research_node": stub_research,
    "pipeline.content_node": stub_content,
    "pipeline.visual_node": stub_visual,
    "pipeline.queue_node": stub_queue,
}


def _patch_nodes():
    """Return a list of active patch context managers for all graph nodes."""
    import pipeline as _pipeline
    patches = []
    for attr, stub in [
        ("research_node", stub_research),
        ("content_node", stub_content),
        ("visual_node", stub_visual),
        ("queue_node", stub_queue),
    ]:
        patches.append(patch.object(_pipeline, attr, stub, create=True))
    return patches


def _apply_patches(patches):
    for p in patches:
        p.start()
    return patches


def _stop_patches(patches):
    for p in patches:
        p.stop()


async def _run_pipeline_with_stubs(run: AgentRun, db, redis):
    """Patches graph imports inside pipeline and runs execute_pipeline."""
    import pipeline as _pl
    patches = _apply_patches(_patch_nodes())
    try:
        # Patch the graph imports inside execute_pipeline
        with patch.dict("sys.modules", {"graph": MagicMock(
            AgentState=dict,
            research_node=stub_research,
            content_node=stub_content,
            visual_node=stub_visual,
            queue_node=stub_queue,
        )}):
            await execute_pipeline(run, db, redis)
    finally:
        _stop_patches(patches)


# ── Test fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def db():
    return FakeDB()


@pytest.fixture
def redis():
    return FakeRedis()


@pytest.fixture
def automated_run():
    return AgentRun(
        tenant_id="t1",
        topic="payroll",
        platforms=["linkedin"],
        execution_mode="automated",
    )


@pytest.fixture
def controlled_run():
    return AgentRun(
        tenant_id="t1",
        topic="payroll",
        platforms=["linkedin"],
        execution_mode="controlled",
    )


# ── Automated pipeline tests ────────────────────────────────────────────────

class TestAutomatedPipeline:
    @pytest.mark.asyncio
    async def test_automated_completes_all_stages(self, db, redis, automated_run):
        coll = db["agent_runs"]
        await coll.insert_one({**automated_run.to_mongo()})

        with patch.dict("sys.modules", {"graph": MagicMock(
            AgentState=dict,
            research_node=stub_research,
            content_node=stub_content,
            visual_node=stub_visual,
            queue_node=stub_queue,
        )}):
            await execute_pipeline(automated_run, db, redis)

        doc = await coll.find_one({"_id": automated_run.id})
        assert doc["overall_status"] == "completed"

    @pytest.mark.asyncio
    async def test_automated_stores_research_output(self, db, redis, automated_run):
        await db["agent_runs"].insert_one({**automated_run.to_mongo()})

        with patch.dict("sys.modules", {"graph": MagicMock(
            AgentState=dict,
            research_node=stub_research,
            content_node=stub_content,
            visual_node=stub_visual,
            queue_node=stub_queue,
        )}):
            await execute_pipeline(automated_run, db, redis)

        doc = await db["agent_runs"].find_one({"_id": automated_run.id})
        assert doc["stages"]["research"]["status"] == StageStatus.APPROVED.value

    @pytest.mark.asyncio
    async def test_automated_all_enabled_stages_run(self, db, redis, automated_run):
        await db["agent_runs"].insert_one({**automated_run.to_mongo()})

        with patch.dict("sys.modules", {"graph": MagicMock(
            AgentState=dict,
            research_node=stub_research,
            content_node=stub_content,
            visual_node=stub_visual,
            queue_node=stub_queue,
        )}):
            await execute_pipeline(automated_run, db, redis)

        doc = await db["agent_runs"].find_one({"_id": automated_run.id})
        for stage in ["research", "content_generation", "visual_generation"]:
            assert doc["stages"][stage]["status"] == StageStatus.APPROVED.value

        # scheduling is disabled by default
        assert doc["stages"]["scheduling"]["status"] == StageStatus.SKIPPED.value

    @pytest.mark.asyncio
    async def test_automated_publishes_completed_event(self, db, redis, automated_run):
        await db["agent_runs"].insert_one({**automated_run.to_mongo()})

        with patch.dict("sys.modules", {"graph": MagicMock(
            AgentState=dict,
            research_node=stub_research,
            content_node=stub_content,
            visual_node=stub_visual,
            queue_node=stub_queue,
        )}):
            await execute_pipeline(automated_run, db, redis)

        status_events = [
            ev for _, ev in redis.published
            if ev.get("type") == "status_change" and ev.get("status") == "completed"
        ]
        assert len(status_events) == 1

    @pytest.mark.asyncio
    async def test_skipped_stage_not_executed(self, db, redis):
        run = AgentRun(
            tenant_id="t1",
            topic="payroll",
            platforms=["linkedin"],
            execution_mode="automated",
            stages_enabled=StagesConfig(visual_generation=False),
        )
        await db["agent_runs"].insert_one({**run.to_mongo()})

        with patch.dict("sys.modules", {"graph": MagicMock(
            AgentState=dict,
            research_node=stub_research,
            content_node=stub_content,
            visual_node=stub_visual,
            queue_node=stub_queue,
        )}):
            await execute_pipeline(run, db, redis)

        doc = await db["agent_runs"].find_one({"_id": run.id})
        assert doc["stages"]["visual_generation"]["status"] == StageStatus.SKIPPED.value
        assert doc["stages"]["research"]["status"] == StageStatus.APPROVED.value


# ── Controlled pipeline tests ───────────────────────────────────────────────

class TestControlledPipeline:
    @pytest.mark.asyncio
    async def test_controlled_pauses_after_first_stage(self, db, redis, controlled_run):
        await db["agent_runs"].insert_one({**controlled_run.to_mongo()})

        pipeline_task = None

        async def run_and_approve():
            nonlocal pipeline_task
            with patch.dict("sys.modules", {"graph": MagicMock(
                AgentState=dict,
                research_node=stub_research,
                content_node=stub_content,
                visual_node=stub_visual,
                queue_node=stub_queue,
            )}):
                pipeline_task = asyncio.create_task(execute_pipeline(controlled_run, db, redis))
                # Give pipeline time to reach research pause
                await asyncio.sleep(0.05)

                # At this point research should be paused
                doc = await db["agent_runs"].find_one({"_id": controlled_run.id})
                research_status = doc["stages"]["research"]["status"]

                # Approve and let it continue through all stages
                for stage in ["research", "content_generation", "visual_generation"]:
                    signal_resume(controlled_run.id, stage)
                    await asyncio.sleep(0.05)

                await pipeline_task
                return research_status

        research_status = await run_and_approve()
        assert research_status == StageStatus.PAUSED.value

    @pytest.mark.asyncio
    async def test_controlled_pauses_emit_paused_for_review_status(self, db, redis, controlled_run):
        await db["agent_runs"].insert_one({**controlled_run.to_mongo()})

        async def approve_all():
            for stage in ["research", "content_generation", "visual_generation"]:
                await asyncio.sleep(0.05)
                signal_resume(controlled_run.id, stage)

        with patch.dict("sys.modules", {"graph": MagicMock(
            AgentState=dict,
            research_node=stub_research,
            content_node=stub_content,
            visual_node=stub_visual,
            queue_node=stub_queue,
        )}):
            await asyncio.gather(
                execute_pipeline(controlled_run, db, redis),
                approve_all(),
            )

        paused_events = [
            ev for _, ev in redis.published
            if ev.get("type") == "status_change" and ev.get("status") == "paused_for_review"
        ]
        assert len(paused_events) >= 1

    @pytest.mark.asyncio
    async def test_controlled_approve_resumes_pipeline(self, db, redis, controlled_run):
        await db["agent_runs"].insert_one({**controlled_run.to_mongo()})

        async def approve_all():
            for stage in ["research", "content_generation", "visual_generation"]:
                await asyncio.sleep(0.05)
                signal_resume(controlled_run.id, stage)

        with patch.dict("sys.modules", {"graph": MagicMock(
            AgentState=dict,
            research_node=stub_research,
            content_node=stub_content,
            visual_node=stub_visual,
            queue_node=stub_queue,
        )}):
            await asyncio.gather(
                execute_pipeline(controlled_run, db, redis),
                approve_all(),
            )

        doc = await db["agent_runs"].find_one({"_id": controlled_run.id})
        assert doc["overall_status"] == "completed"

    @pytest.mark.asyncio
    async def test_edit_propagates_to_next_stage(self, db, redis):
        run = AgentRun(
            tenant_id="t1",
            topic="payroll",
            platforms=["linkedin"],
            execution_mode="controlled",
        )
        await db["agent_runs"].insert_one({**run.to_mongo()})

        captured_state = {}

        async def capturing_content(state):
            captured_state.update(state)
            return await stub_content(state)

        async def approve_with_edit():
            # Research stage: approve with edited brief
            await asyncio.sleep(0.05)
            edited_brief = {
                "topic": "payroll",
                "trending_angles": ["Custom edited trend"],
                "pain_points": [],
                "suggested_hooks": [],
                "platform_notes": {},
                "generated_at": "2026-06-14T00:00:00Z",
            }
            signal_resume(run.id, "research", edited_output=edited_brief)
            # Content and visual stages: plain approve
            for stage in ["content_generation", "visual_generation"]:
                await asyncio.sleep(0.05)
                signal_resume(run.id, stage)

        with patch.dict("sys.modules", {"graph": MagicMock(
            AgentState=dict,
            research_node=stub_research,
            content_node=capturing_content,
            visual_node=stub_visual,
            queue_node=stub_queue,
        )}):
            await asyncio.gather(
                execute_pipeline(run, db, redis),
                approve_with_edit(),
            )

        assert captured_state.get("brief", {}).get("trending_angles") == ["Custom edited trend"]

    @pytest.mark.asyncio
    async def test_cancel_stops_processing(self, db, redis, controlled_run):
        await db["agent_runs"].insert_one({**controlled_run.to_mongo()})

        stages_executed = []

        async def tracking_content(state):
            stages_executed.append("content_generation")
            return await stub_content(state)

        async def cancel_after_research():
            await asyncio.sleep(0.05)
            # Cancel instead of approving
            cancel_run(controlled_run.id)

        with patch.dict("sys.modules", {"graph": MagicMock(
            AgentState=dict,
            research_node=stub_research,
            content_node=tracking_content,
            visual_node=stub_visual,
            queue_node=stub_queue,
        )}):
            await asyncio.gather(
                execute_pipeline(controlled_run, db, redis),
                cancel_after_research(),
            )

        doc = await db["agent_runs"].find_one({"_id": controlled_run.id})
        assert doc["overall_status"] == "cancelled"
        assert "content_generation" not in stages_executed


# ── Stage failure tests ─────────────────────────────────────────────────────

class TestStageFailure:
    @pytest.mark.asyncio
    async def test_failed_stage_sets_overall_status_failed(self, db, redis, automated_run):
        await db["agent_runs"].insert_one({**automated_run.to_mongo()})

        async def failing_research(state):
            raise RuntimeError("Perplexity API down")

        with patch.dict("sys.modules", {"graph": MagicMock(
            AgentState=dict,
            research_node=failing_research,
            content_node=stub_content,
            visual_node=stub_visual,
            queue_node=stub_queue,
        )}):
            await execute_pipeline(automated_run, db, redis)

        doc = await db["agent_runs"].find_one({"_id": automated_run.id})
        assert doc["overall_status"] == "failed"
        assert doc["stages"]["research"]["status"] == StageStatus.FAILED.value

    @pytest.mark.asyncio
    async def test_failed_stage_stores_error_message(self, db, redis, automated_run):
        await db["agent_runs"].insert_one({**automated_run.to_mongo()})

        async def failing_research(state):
            raise RuntimeError("Perplexity API down")

        with patch.dict("sys.modules", {"graph": MagicMock(
            AgentState=dict,
            research_node=failing_research,
            content_node=stub_content,
            visual_node=stub_visual,
            queue_node=stub_queue,
        )}):
            await execute_pipeline(automated_run, db, redis)

        doc = await db["agent_runs"].find_one({"_id": automated_run.id})
        assert "Perplexity API down" in doc["stages"]["research"]["error"]["message"]


# ── Rerun tests ─────────────────────────────────────────────────────────────

class TestRerunStage:
    @pytest.mark.asyncio
    async def test_rerun_executes_stage_again(self, db, redis):
        run = AgentRun(
            tenant_id="t1",
            topic="payroll",
            platforms=["linkedin"],
            execution_mode="controlled",
            state_snapshot={"brief": None, "competitor_data": [], "platform_content": {}, "visual_assets": {}},
        )
        await db["agent_runs"].insert_one({**run.to_mongo()})

        with patch.dict("sys.modules", {"graph": MagicMock(
            AgentState=dict,
            research_node=stub_research,
            content_node=stub_content,
            visual_node=stub_visual,
            queue_node=stub_queue,
        )}):
            await rerun_stage(run, "research", db, redis)

        doc = await db["agent_runs"].find_one({"_id": run.id})
        assert doc["stages"]["research"]["status"] == StageStatus.PAUSED.value
        assert doc["overall_status"] == "paused_for_review"

    @pytest.mark.asyncio
    async def test_rerun_saves_new_snapshot(self, db, redis):
        run = AgentRun(
            tenant_id="t1",
            topic="payroll",
            platforms=["linkedin"],
            state_snapshot={"brief": None, "competitor_data": [], "platform_content": {}, "visual_assets": {}},
        )
        await db["agent_runs"].insert_one({**run.to_mongo()})

        with patch.dict("sys.modules", {"graph": MagicMock(
            AgentState=dict,
            research_node=stub_research,
            content_node=stub_content,
            visual_node=stub_visual,
            queue_node=stub_queue,
        )}):
            await rerun_stage(run, "research", db, redis)

        doc = await db["agent_runs"].find_one({"_id": run.id})
        # Snapshot should now contain the research output
        assert doc["state_snapshot"] is not None
        assert doc["state_snapshot"].get("brief") is not None
