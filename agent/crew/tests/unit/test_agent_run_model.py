"""Unit tests for AgentRun model — B1 requirement."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from models import (
    AgentRun,
    StageState,
    StageStatus,
    StagesConfig,
    STAGE_ORDER,
)


# ── StagesConfig tests ─────────────────────────────────────────────────────

class TestStagesConfig:
    def test_defaults(self):
        cfg = StagesConfig()
        assert cfg.research is True
        assert cfg.content_generation is True
        assert cfg.visual_generation is True
        assert cfg.scheduling is False

    def test_all_disabled(self):
        cfg = StagesConfig(
            research=False,
            content_generation=False,
            visual_generation=False,
            scheduling=False,
        )
        assert not any([cfg.research, cfg.content_generation, cfg.visual_generation, cfg.scheduling])

    def test_partial_disable(self):
        cfg = StagesConfig(visual_generation=False, scheduling=True)
        assert cfg.research is True
        assert cfg.visual_generation is False
        assert cfg.scheduling is True


# ── StageState transition tests ────────────────────────────────────────────

class TestStageStateTransitions:
    def test_pending_can_go_to_running(self):
        s = StageState(status=StageStatus.PENDING)
        assert s.can_transition_to(StageStatus.RUNNING)

    def test_pending_can_go_to_skipped(self):
        s = StageState(status=StageStatus.PENDING)
        assert s.can_transition_to(StageStatus.SKIPPED)

    def test_pending_cannot_go_to_approved(self):
        s = StageState(status=StageStatus.PENDING)
        assert not s.can_transition_to(StageStatus.APPROVED)

    def test_running_can_go_to_paused(self):
        s = StageState(status=StageStatus.RUNNING)
        assert s.can_transition_to(StageStatus.PAUSED)

    def test_running_can_go_to_approved(self):
        s = StageState(status=StageStatus.RUNNING)
        assert s.can_transition_to(StageStatus.APPROVED)

    def test_running_can_go_to_failed(self):
        s = StageState(status=StageStatus.RUNNING)
        assert s.can_transition_to(StageStatus.FAILED)

    def test_paused_can_go_to_approved(self):
        s = StageState(status=StageStatus.PAUSED)
        assert s.can_transition_to(StageStatus.APPROVED)

    def test_paused_can_rerun(self):
        s = StageState(status=StageStatus.PAUSED)
        assert s.can_transition_to(StageStatus.RUNNING)

    def test_approved_has_no_valid_transitions(self):
        s = StageState(status=StageStatus.APPROVED)
        for target in StageStatus:
            assert not s.can_transition_to(target)

    def test_skipped_has_no_valid_transitions(self):
        s = StageState(status=StageStatus.SKIPPED)
        for target in StageStatus:
            assert not s.can_transition_to(target)

    def test_failed_can_rerun(self):
        s = StageState(status=StageStatus.FAILED)
        assert s.can_transition_to(StageStatus.RUNNING)


# ── AgentRun model tests ───────────────────────────────────────────────────

class TestAgentRun:
    def test_default_stages_created(self):
        run = AgentRun(tenant_id="t1", topic="payroll", platforms=["linkedin"])
        assert set(run.stages.keys()) == set(STAGE_ORDER)

    def test_default_status_pending(self):
        run = AgentRun(tenant_id="t1", topic="payroll", platforms=["linkedin"])
        assert run.overall_status == "pending"

    def test_default_execution_mode_automated(self):
        run = AgentRun(tenant_id="t1", topic="payroll", platforms=["linkedin"])
        assert run.execution_mode == "automated"

    def test_get_stage_returns_stage_state(self):
        run = AgentRun(tenant_id="t1", topic="payroll", platforms=["linkedin"])
        stage = run.get_stage("research")
        assert isinstance(stage, StageState)
        assert stage.status == StageStatus.PENDING

    def test_to_mongo_renames_id_to_underscore_id(self):
        run = AgentRun(tenant_id="t1", topic="payroll", platforms=["linkedin"])
        doc = run.to_mongo()
        assert "_id" in doc
        assert "id" not in doc

    def test_from_mongo_restores_id(self):
        run = AgentRun(tenant_id="t1", topic="payroll", platforms=["linkedin"])
        doc = run.to_mongo()
        restored = AgentRun.from_mongo(doc)
        assert restored.id == run.id
        assert restored.tenant_id == run.tenant_id

    def test_controlled_mode_set(self):
        run = AgentRun(
            tenant_id="t1",
            topic="payroll",
            platforms=["linkedin"],
            execution_mode="controlled",
        )
        assert run.execution_mode == "controlled"

    def test_provided_content_stored(self):
        run = AgentRun(
            tenant_id="t1",
            topic="payroll",
            platforms=["linkedin"],
            provided_content="Custom post copy",
            stages_enabled=StagesConfig(content_generation=False),
        )
        assert run.provided_content == "Custom post copy"
        assert not run.stages_enabled.content_generation

    def test_unique_ids_per_instance(self):
        r1 = AgentRun(tenant_id="t1", topic="a", platforms=[])
        r2 = AgentRun(tenant_id="t1", topic="a", platforms=[])
        assert r1.id != r2.id

    def test_stage_order_constant(self):
        assert STAGE_ORDER == [
            "research", "content_generation", "visual_generation", "scheduling"
        ]
