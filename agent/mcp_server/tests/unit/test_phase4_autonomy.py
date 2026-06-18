"""Phase 4 TDD tests: Autonomy & Scheduled Runs."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest
from schemas import ProjectDoc, ProjectUpdateRequest


class TestProjectScheduleFields:
    """ProjectDoc and ProjectUpdateRequest must carry schedule config fields."""

    def test_project_doc_schedule_enabled_defaults_false(self):
        p = ProjectDoc(name="Test")
        assert p.schedule_enabled is False

    def test_project_doc_schedule_fields_all_present(self):
        p = ProjectDoc(
            name="Test",
            schedule_enabled=True,
            schedule_frequency="weekly",
            schedule_cron="0 9 * * 2",
            schedule_platforms=["linkedin", "instagram"],
            schedule_topic_rotation=["EOBI guide", "Payroll tips"],
            schedule_auto_approve=False,
        )
        assert p.schedule_enabled is True
        assert p.schedule_frequency == "weekly"
        assert p.schedule_cron == "0 9 * * 2"
        assert p.schedule_platforms == ["linkedin", "instagram"]
        assert p.schedule_topic_rotation == ["EOBI guide", "Payroll tips"]
        assert p.schedule_auto_approve is False

    def test_update_request_can_patch_schedule_fields(self):
        req = ProjectUpdateRequest(
            schedule_enabled=True,
            schedule_frequency="daily",
            schedule_auto_approve=True,
        )
        assert req.schedule_enabled is True
        assert req.schedule_frequency == "daily"
        assert req.schedule_auto_approve is True

    def test_update_request_schedule_fields_default_none(self):
        req = ProjectUpdateRequest(name="New Name")
        assert req.schedule_enabled is None
        assert req.schedule_frequency is None
        assert req.schedule_cron is None
        assert req.schedule_platforms is None
        assert req.schedule_topic_rotation is None
        assert req.schedule_auto_approve is None

    def test_topic_rotation_is_list(self):
        p = ProjectDoc(name="T", schedule_topic_rotation=["topic a", "topic b", "topic c"])
        assert len(p.schedule_topic_rotation) == 3
        assert "topic b" in p.schedule_topic_rotation


class TestOptimalPostTime:
    """get_optimal_post_time returns correct PKT slots per platform."""

    def setup_method(self):
        from services.scheduler_service import get_optimal_post_time
        self.get_optimal_post_time = get_optimal_post_time

    def test_instagram_has_three_daily_slots(self):
        slots = self.get_optimal_post_time("instagram")
        assert len(slots) >= 2
        hours = [s["hour"] for s in slots]
        assert 9 in hours  # 9am PKT

    def test_instagram_includes_noon_slot(self):
        slots = self.get_optimal_post_time("instagram")
        hours = [s["hour"] for s in slots]
        assert 12 in hours  # 12pm PKT

    def test_linkedin_best_days_are_weekdays(self):
        slots = self.get_optimal_post_time("linkedin")
        days = [s.get("day") for s in slots if s.get("day")]
        for d in days:
            assert d in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")

    def test_linkedin_morning_hours(self):
        slots = self.get_optimal_post_time("linkedin")
        hours = [s["hour"] for s in slots]
        # LinkedIn best: 8-10am PKT
        assert any(8 <= h <= 10 for h in hours)

    def test_twitter_has_slots(self):
        slots = self.get_optimal_post_time("twitter")
        assert len(slots) >= 1
        assert "hour" in slots[0]

    def test_unknown_platform_returns_default_9am(self):
        slots = self.get_optimal_post_time("tiktok")
        assert slots[0]["hour"] == 9


class TestSchedulerService:
    """list_scheduled_projects and next_rotation_topic helpers."""

    def setup_method(self):
        from services.scheduler_service import next_rotation_topic
        self.next_rotation_topic = next_rotation_topic

    def test_rotation_returns_first_topic_at_index_0(self):
        topics = ["EOBI guide", "Payroll tips", "HR compliance"]
        assert self.next_rotation_topic(topics, 0) == "EOBI guide"

    def test_rotation_wraps_around(self):
        topics = ["A", "B", "C"]
        assert self.next_rotation_topic(topics, 3) == "A"  # 3 % 3 = 0

    def test_rotation_empty_returns_empty_string(self):
        assert self.next_rotation_topic([], 5) == ""

    def test_rotation_single_topic_always_returns_it(self):
        assert self.next_rotation_topic(["Only topic"], 99) == "Only topic"
