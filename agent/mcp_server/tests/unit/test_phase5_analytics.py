"""Phase 5 TDD tests: Analytics, Feedback & Calendar."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest
from datetime import datetime, timezone


class FakeCollection:
    """In-memory MongoDB collection double that filters on simple equality queries."""

    def __init__(self, docs=None):
        self._docs = list(docs or [])
        self._query = None

    def _matches(self, doc: dict, query: dict) -> bool:
        for k, v in query.items():
            if isinstance(v, dict):
                continue  # skip operators like $gte for simplicity
            if doc.get(k) != v:
                return False
        return True

    def find(self, query=None, projection=None):
        clone = FakeCollection(self._docs)
        clone._query = query or {}
        return clone

    async def to_list(self, length=None):
        filtered = [d for d in self._docs if self._matches(d, self._query or {})]
        return list(filtered[:length] if length else filtered)

    async def find_one(self, query=None, projection=None):
        for d in self._docs:
            if self._matches(d, query or {}):
                return d
        return None


class FakeDb:
    def __init__(self, collections=None):
        self._collections = collections or {}

    def __getitem__(self, name):
        return self._collections.get(name, FakeCollection())


class TestGetRunAnalytics:
    """get_run_analytics computes cost_per_post from tool_call log."""

    def setup_method(self):
        from services.analytics_service import get_run_analytics
        self.get_run_analytics = get_run_analytics

    @pytest.mark.asyncio
    async def test_returns_zero_cost_per_post_when_no_posts(self):
        db = FakeDb({
            "tool_calls": FakeCollection([{"run_id": "r1", "cost_usd": 0.05}]),
            "posts": FakeCollection([]),
        })
        result = await self.get_run_analytics(db, "r1")
        assert result["cost_per_post"] == 0
        assert result["post_count"] == 0

    @pytest.mark.asyncio
    async def test_computes_cost_per_post_correctly(self):
        db = FakeDb({
            "tool_calls": FakeCollection([
                {"run_id": "r1", "cost_usd": 0.06},
                {"run_id": "r1", "cost_usd": 0.04},
            ]),
            "posts": FakeCollection([
                {"run_id": "r1", "platform": "linkedin"},
                {"run_id": "r1", "platform": "instagram"},
            ]),
        })
        result = await self.get_run_analytics(db, "r1")
        assert result["post_count"] == 2
        assert abs(result["cost_per_post"] - 0.05) < 1e-6

    @pytest.mark.asyncio
    async def test_returns_total_cost(self):
        db = FakeDb({
            "tool_calls": FakeCollection([
                {"run_id": "r2", "cost_usd": 0.10},
                {"run_id": "r2", "cost_usd": 0.05},
            ]),
            "posts": FakeCollection([{"run_id": "r2", "platform": "twitter"}]),
        })
        result = await self.get_run_analytics(db, "r2")
        assert abs(result["total_cost_usd"] - 0.15) < 1e-6

    @pytest.mark.asyncio
    async def test_zero_cost_when_no_tool_calls(self):
        db = FakeDb({
            "tool_calls": FakeCollection([]),
            "posts": FakeCollection([{"run_id": "r3"}]),
        })
        result = await self.get_run_analytics(db, "r3")
        assert result["total_cost_usd"] == 0
        assert result["cost_per_post"] == 0


class TestGetProjectAnalytics:
    """get_project_analytics returns best_platform and avg_engagement."""

    def setup_method(self):
        from services.analytics_service import get_project_analytics
        self.get_project_analytics = get_project_analytics

    @pytest.mark.asyncio
    async def test_best_platform_is_platform_with_most_approved_posts(self):
        db = FakeDb({
            "posts": FakeCollection([
                {"project_id": "p1", "platform": "linkedin", "status": "approved"},
                {"project_id": "p1", "platform": "linkedin", "status": "approved"},
                {"project_id": "p1", "platform": "instagram", "status": "approved"},
            ]),
        })
        result = await self.get_project_analytics(db, "p1")
        assert result["best_platform"] == "linkedin"

    @pytest.mark.asyncio
    async def test_returns_unknown_best_platform_when_no_posts(self):
        db = FakeDb({"posts": FakeCollection([])})
        result = await self.get_project_analytics(db, "p2")
        assert result["best_platform"] == "unknown"
        assert result["total_posts"] == 0

    @pytest.mark.asyncio
    async def test_avg_engagement_per_platform_present(self):
        db = FakeDb({
            "posts": FakeCollection([
                {"project_id": "p3", "platform": "linkedin", "status": "approved", "performance_rating": "high"},
                {"project_id": "p3", "platform": "instagram", "status": "approved", "performance_rating": "low"},
            ]),
        })
        result = await self.get_project_analytics(db, "p3")
        assert "avg_engagement_per_platform" in result
        assert isinstance(result["avg_engagement_per_platform"], dict)

    @pytest.mark.asyncio
    async def test_total_posts_counts_all_statuses(self):
        db = FakeDb({
            "posts": FakeCollection([
                {"project_id": "p4", "platform": "linkedin", "status": "queued"},
                {"project_id": "p4", "platform": "linkedin", "status": "approved"},
                {"project_id": "p4", "platform": "twitter", "status": "queued"},
            ]),
        })
        result = await self.get_project_analytics(db, "p4")
        assert result["total_posts"] == 3


class TestGetOptimalTimesFromData:
    """get_optimal_times_from_data reads high-rated post schedule times."""

    def setup_method(self):
        from services.analytics_service import get_optimal_times_from_data
        self.get_optimal_times_from_data = get_optimal_times_from_data

    @pytest.mark.asyncio
    async def test_returns_none_when_no_high_rated_posts(self):
        db = FakeDb({"posts": FakeCollection([
            {"project_id": "p1", "platform": "linkedin", "performance_rating": "low"},
        ])})
        result = await self.get_optimal_times_from_data(db, "p1", "linkedin")
        assert result is None or result.get("best_hours") == []

    @pytest.mark.asyncio
    async def test_extracts_hours_from_high_rated_post_schedule(self):
        db = FakeDb({"posts": FakeCollection([
            {
                "project_id": "p2",
                "platform": "linkedin",
                "performance_rating": "high",
                "scheduled_at": "2026-06-17T09:00:00+05:00",
            },
            {
                "project_id": "p2",
                "platform": "linkedin",
                "performance_rating": "high",
                "scheduled_at": "2026-06-18T09:00:00+05:00",
            },
        ])})
        result = await self.get_optimal_times_from_data(db, "p2", "linkedin")
        assert result is not None
        assert "best_hours" in result
        assert len(result["best_hours"]) > 0

    @pytest.mark.asyncio
    async def test_ignores_medium_and_low_rated_posts(self):
        db = FakeDb({"posts": FakeCollection([
            {"project_id": "p3", "platform": "instagram", "performance_rating": "medium", "scheduled_at": "2026-06-17T14:00:00+05:00"},
            {"project_id": "p3", "platform": "instagram", "performance_rating": "low", "scheduled_at": "2026-06-17T22:00:00+05:00"},
        ])})
        result = await self.get_optimal_times_from_data(db, "p3", "instagram")
        assert result is None or result.get("best_hours") == []

    @pytest.mark.asyncio
    async def test_returns_best_days_from_high_rated_posts(self):
        db = FakeDb({"posts": FakeCollection([
            {
                "project_id": "p4",
                "platform": "linkedin",
                "performance_rating": "high",
                "scheduled_at": "2026-06-16T09:00:00+05:00",  # Tuesday
            },
        ])})
        result = await self.get_optimal_times_from_data(db, "p4", "linkedin")
        assert result is not None
        assert "best_days" in result
        assert len(result["best_days"]) > 0
