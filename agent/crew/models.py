"""Data models for agent run management — Group B."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    APPROVED = "approved"
    FAILED = "failed"
    SKIPPED = "skipped"


class StageState(BaseModel):
    status: StageStatus = StageStatus.PENDING
    output: Optional[Any] = None
    error: Optional[dict] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Valid transitions: pending→running, running→paused|approved|failed,
    # paused→approved, any→skipped
    def can_transition_to(self, target: StageStatus) -> bool:
        allowed: dict[StageStatus, set[StageStatus]] = {
            StageStatus.PENDING:  {StageStatus.RUNNING, StageStatus.SKIPPED},
            StageStatus.RUNNING:  {StageStatus.PAUSED, StageStatus.APPROVED, StageStatus.FAILED},
            StageStatus.PAUSED:   {StageStatus.APPROVED, StageStatus.RUNNING},
            StageStatus.APPROVED: set(),
            StageStatus.FAILED:   {StageStatus.RUNNING},
            StageStatus.SKIPPED:  set(),
        }
        return target in allowed.get(self.status, set())


class StagesConfig(BaseModel):
    research: bool = True
    content_generation: bool = True
    visual_generation: bool = True
    scheduling: bool = False


STAGE_ORDER: list[str] = [
    "research",
    "content_generation",
    "visual_generation",
    "scheduling",
]

STAGE_TO_CONFIG_FIELD: dict[str, str] = {
    "research": "research",
    "content_generation": "content_generation",
    "visual_generation": "visual_generation",
    "scheduling": "scheduling",
}


def _default_stages() -> dict[str, dict]:
    return {stage: StageState().model_dump() for stage in STAGE_ORDER}


class AgentRun(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str
    topic: str
    platforms: list[str]
    project_id: Optional[str] = None
    stages_enabled: StagesConfig = Field(default_factory=StagesConfig)
    execution_mode: Literal["automated", "controlled"] = "automated"
    stages: dict[str, Any] = Field(default_factory=_default_stages)
    current_stage: str = "research"
    overall_status: Literal[
        "pending", "running", "paused_for_review", "completed", "failed", "cancelled"
    ] = "pending"
    provided_content: Optional[str] = None
    state_snapshot: Optional[dict] = None  # full AgentState before each stage (for re-run)
    created_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))

    def get_stage(self, stage: str) -> StageState:
        raw = self.stages.get(stage, {})
        if isinstance(raw, StageState):
            return raw
        return StageState(**raw)

    def to_mongo(self) -> dict:
        d = self.model_dump(mode="json")
        d["_id"] = d.pop("id")
        return d

    @classmethod
    def from_mongo(cls, doc: dict) -> AgentRun:
        doc = dict(doc)
        doc["id"] = str(doc.pop("_id"))
        return cls(**doc)


# ── Request / response schemas ─────────────────────────────────────────────

class CreateRunRequest(BaseModel):
    topic: str
    platforms: list[str] = ["linkedin", "instagram"]
    execution_mode: Literal["automated", "controlled"] = "automated"
    stages_enabled: StagesConfig = Field(default_factory=StagesConfig)
    provided_content: Optional[str] = None
    project_id: Optional[str] = None


class EditStageRequest(BaseModel):
    output: dict


class ApproveStageRequest(BaseModel):
    edited_output: Optional[dict] = None
