"""Tests for memory_constants module."""

import pytest

from app.sim.memory_constants import (
    MemoryCategory,
    calculate_event_importance,
    calculate_memory_importance,
    determine_memory_category,
    should_consolidate_memory,
)


class TestMemoryCategory:
    """Tests for MemoryCategory enum."""

    def test_all_categories_returns_three_categories(self):
        """Should return all three category types."""
        categories = MemoryCategory.all_categories()
        assert len(categories) == 3
        assert MemoryCategory.SHORT_TERM in categories
        assert MemoryCategory.MEDIUM_TERM in categories
        assert MemoryCategory.LONG_TERM in categories


class TestCalculateEventImportance:
    """Tests for calculate_event_importance function."""

    def test_talk_event_has_default_importance(self):
        """Talk events should have moderate objective salience."""
        importance = calculate_event_importance("talk", {})
        assert importance == 0.55

    def test_work_event_has_medium_importance(self):
        """Routine work should stay low salience."""
        importance = calculate_event_importance("work", {})
        assert importance == 0.2

    def test_move_event_has_low_importance(self):
        """Movement should be almost pure noise."""
        importance = calculate_event_importance("move", {})
        assert importance == 0.08

    def test_rest_event_has_low_importance(self):
        """Rest should be the lowest salience routine event."""
        importance = calculate_event_importance("rest", {})
        assert importance == 0.03

    def test_unknown_event_type_has_default_importance(self):
        """Unknown events should be treated as mildly notable."""
        importance = calculate_event_importance("unknown_type", {})
        assert importance == 0.3

    def test_rejected_talk_is_no_longer_scored_as_near_long_term(self):
        """Rejected talk should be notable but clearly below successful talk."""
        importance = calculate_event_importance("talk_rejected", {})
        assert importance == 0.32

    def test_rejected_move_stays_close_to_minor_interruption(self):
        """Rejected move should not outrank meaningful social memories."""
        importance = calculate_event_importance("move_rejected", {})
        assert importance == 0.18

    def test_emotional_content_increases_importance(self):
        """Talk with emotional content should have increased importance."""
        normal_importance = calculate_event_importance("talk", {"message": "你好"})
        emotional_importance = calculate_event_importance(
            "talk", {"message": "我真的很喜欢你"}
        )
        assert emotional_importance > normal_importance

    def test_long_conversation_increases_importance(self):
        """Long conversations should have increased importance."""
        short_msg = "你好" * 10  # ~20 chars
        long_msg = "这是一段很长的对话内容" * 10  # >100 chars

        short_importance = calculate_event_importance("talk", {"message": short_msg})
        long_importance = calculate_event_importance("talk", {"message": long_msg})

        assert long_importance > short_importance

    def test_first_interaction_increases_importance(self):
        """First interaction should have increased importance."""
        normal = calculate_event_importance("talk", {})
        first = calculate_event_importance("talk", {}, is_first_interaction=True)
        assert first > normal
        assert first == pytest.approx(0.65)

    def test_importance_clamped_to_max_1(self):
        """Importance should never exceed 1.0."""
        # Use all multipliers together to try to exceed 1.0
        importance = calculate_event_importance(
            "talk",
            {"message": "我喜欢你，爱死你了，真的很开心" * 50},
            is_first_interaction=True,
        )
        assert importance <= 1.0

    def test_importance_never_negative(self):
        """Importance should never be negative."""
        importance = calculate_event_importance("unknown", {})
        assert importance >= 0.0


class TestCalculateMemoryImportance:
    """Tests for subjective memory scoring."""

    def test_target_memory_is_stronger_than_actor_for_same_event(self):
        actor_score = calculate_memory_importance(
            event_importance=0.55,
            perspective="actor",
            relationship_strength=0.2,
        )
        target_score = calculate_memory_importance(
            event_importance=0.55,
            perspective="target",
            relationship_strength=0.2,
        )
        assert target_score > actor_score

    def test_goal_and_location_relevance_raise_subjective_importance(self):
        baseline = calculate_memory_importance(
            event_importance=0.2,
            perspective="observer",
            relationship_strength=0.0,
        )
        boosted = calculate_memory_importance(
            event_importance=0.2,
            perspective="observer",
            relationship_strength=0.0,
            goal_relevance=True,
            location_relevance=True,
        )
        assert boosted > baseline

    def test_subjective_importance_is_clamped(self):
        score = calculate_memory_importance(
            event_importance=0.95,
            perspective="target",
            relationship_strength=1.0,
            goal_relevance=True,
            location_relevance=True,
        )
        assert score <= 1.0

    def test_high_relevance_talk_no_longer_saturates_to_one_too_easily(self):
        score = calculate_memory_importance(
            event_importance=0.67,
            perspective="target",
            relationship_strength=0.4,
            goal_relevance=False,
            location_relevance=True,
        )
        assert score < 1.0
        assert score == pytest.approx(0.88)

    def test_extreme_case_can_still_reach_top_band_without_flattening_all_scores(self):
        score = calculate_memory_importance(
            event_importance=0.95,
            perspective="target",
            relationship_strength=1.0,
            goal_relevance=True,
            location_relevance=True,
        )
        assert score == pytest.approx(0.98)


class TestDetermineMemoryCategory:
    """Tests for determine_memory_category function."""

    def test_high_importance_becomes_long_term(self):
        """Strongly relevant memories should immediately become long_term."""
        category = determine_memory_category(importance=0.9)
        assert category == MemoryCategory.LONG_TERM

    def test_medium_importance_becomes_medium_term(self):
        """Mid-salience memories should become medium_term."""
        category = determine_memory_category(importance=0.6)
        assert category == MemoryCategory.MEDIUM_TERM

    def test_previously_long_term_borderline_score_now_stays_medium_term(self):
        category = determine_memory_category(importance=0.8)
        assert category == MemoryCategory.MEDIUM_TERM

    def test_low_importance_new_memory_is_short_term(self):
        """Low importance new memory (tick_age=0) should be short_term."""
        category = determine_memory_category(importance=0.1, tick_age=0)
        assert category == MemoryCategory.SHORT_TERM

    def test_old_short_memory_becomes_medium_term(self):
        """Memory older than 30 minutes should become medium_term."""
        # tick_minutes=5, so 6 ticks = 30 minutes
        category = determine_memory_category(importance=0.1, tick_age=6, tick_minutes=5)
        assert category == MemoryCategory.MEDIUM_TERM

    def test_very_old_memory_becomes_long_term(self):
        """Memory older than 6 hours should become long_term."""
        # tick_minutes=5, so 72 ticks = 360 minutes = 6 hours
        category = determine_memory_category(importance=0.1, tick_age=73, tick_minutes=5)
        assert category == MemoryCategory.LONG_TERM


class TestShouldConsolidateMemory:
    """Tests for should_consolidate_memory function."""

    def test_long_term_memory_should_not_consolidate(self):
        """Long_term memory should never need consolidation."""
        result = should_consolidate_memory(
            MemoryCategory.LONG_TERM, importance=0.5, access_count=10, tick_age=100
        )
        assert result is False

    def test_high_access_count_triggers_consolidation(self):
        """Memory accessed 3+ times should be consolidated."""
        result = should_consolidate_memory(
            MemoryCategory.SHORT_TERM, importance=0.3, access_count=3, tick_age=1
        )
        assert result is True

    def test_high_importance_old_memory_consolidates(self):
        """High importance memory (> 0.6) older than 1 hour should consolidate."""
        # tick_minutes=5, so 12 ticks = 60 minutes
        result = should_consolidate_memory(
            MemoryCategory.SHORT_TERM, importance=0.7, access_count=0, tick_age=12
        )
        assert result is True

    def test_short_term_2_hours_old_consolidates(self):
        """Short_term memory 2+ hours old should consolidate."""
        # tick_minutes=5, so 24 ticks = 120 minutes = 2 hours
        result = should_consolidate_memory(
            MemoryCategory.SHORT_TERM, importance=0.3, access_count=0, tick_age=24
        )
        assert result is True

    def test_new_unaccessed_memory_should_not_consolidate(self):
        """New unaccessed memory should not consolidate."""
        result = should_consolidate_memory(
            MemoryCategory.SHORT_TERM, importance=0.3, access_count=0, tick_age=1
        )
        assert result is False
