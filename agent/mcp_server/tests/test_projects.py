"""P-CS: Tests for projects CRUD and context seeding — TDD Phase 2."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── AgentRun model — project_id field ─────────────────────────────────────────

class TestAgentRunProjectId:
    def test_project_id_defaults_to_none(self):
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../crew"))
        from models import AgentRun
        run = AgentRun(tenant_id="t1", topic="payroll", platforms=["linkedin"])
        assert run.project_id is None

    def test_project_id_can_be_set(self):
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../crew"))
        from models import AgentRun
        run = AgentRun(
            tenant_id="t1", topic="payroll", platforms=["linkedin"],
            project_id="proj-abc"
        )
        assert run.project_id == "proj-abc"

    def test_project_id_round_trips_through_mongo(self):
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../crew"))
        from models import AgentRun
        run = AgentRun(tenant_id="t1", topic="payroll", platforms=["linkedin"], project_id="proj-abc")
        doc = run.to_mongo()
        assert doc.get("project_id") == "proj-abc"
        restored = AgentRun.from_mongo(doc)
        assert restored.project_id == "proj-abc"

    def test_create_run_request_accepts_project_id(self):
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../crew"))
        from models import CreateRunRequest
        req = CreateRunRequest(topic="payroll", project_id="proj-abc")
        assert req.project_id == "proj-abc"

    def test_create_run_request_project_id_defaults_to_none(self):
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../crew"))
        from models import CreateRunRequest
        req = CreateRunRequest(topic="payroll")
        assert req.project_id is None
