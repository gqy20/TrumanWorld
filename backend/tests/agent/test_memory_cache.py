"""Tests for MemoryCache - in-memory memory query for MCP tools."""

from datetime import UTC, datetime, timedelta

import pytest

from app.agent.memory_cache import MemoryCache


def test_format_memory_result_handles_empty_and_populated_records():
    cache = MemoryCache()
    assert cache.format_for_display([]) == "没有找到相关记忆。"

    formatted = cache.format_for_display(
        [
            {
                "tick_no": 5,
                "memory_category": "long_term",
                "summary": "Talked with Bob",
                "related_agent_name": "Bob",
            }
        ]
    )

    assert "找到以下记忆：" in formatted
    assert "[Tick 5] [long_term] Talked with Bob" in formatted
    assert "相关人物: Bob" in formatted


def test_search_memories_filters_by_query_and_category():
    """Test searching memories by query string and category."""
    cache_data = {
        "short_term": [
            {
                "id": "mem-short-cafe",
                "content": "Served coffee at the cafe.",
                "summary": "Served coffee",
                "tick_no": 6,
                "memory_category": "short_term",
            }
        ],
        "long_term": [
            {
                "id": "mem-long-bob",
                "content": "Talked with Bob about the cafe renovation.",
                "summary": "Talked with Bob",
                "tick_no": 5,
                "memory_category": "long_term",
                "related_agent_id": "agent-bob",
                "related_agent_name": "Bob",
            },
            {
                "id": "mem-long-park",
                "content": "Walked alone in the park.",
                "summary": "Park walk",
                "tick_no": 3,
                "memory_category": "long_term",
            },
        ],
        "all": [
            {
                "id": "mem-short-cafe",
                "content": "Served coffee at the cafe.",
                "summary": "Served coffee",
                "tick_no": 6,
                "memory_category": "short_term",
            },
            {
                "id": "mem-long-bob",
                "content": "Talked with Bob about the cafe renovation.",
                "summary": "Talked with Bob",
                "tick_no": 5,
                "memory_category": "long_term",
                "related_agent_id": "agent-bob",
                "related_agent_name": "Bob",
            },
            {
                "id": "mem-long-park",
                "content": "Walked alone in the park.",
                "summary": "Park walk",
                "tick_no": 3,
                "memory_category": "long_term",
            },
        ],
    }

    cache = MemoryCache(cache_data)

    # Search in long_term only
    results = cache.search_memories(query="Bob", category="long_term", limit=5)
    assert [memory["id"] for memory in results] == ["mem-long-bob"]
    assert results[0]["related_agent_name"] == "Bob"

    # Search in all categories
    results = cache.search_memories(query="cafe", category="all", limit=5)
    assert len(results) == 2  # mem-short-cafe and mem-long-bob

    # Search with no matches
    results = cache.search_memories(query="nonexistent", category="all", limit=5)
    assert results == []


def test_get_recent_memories_respects_category_and_limit():
    """Test getting recent memories with category filter."""
    cache_data = {
        "short_term": [
            {"id": "st1", "tick_no": 10, "memory_category": "short_term"},
            {"id": "st2", "tick_no": 9, "memory_category": "short_term"},
        ],
        "long_term": [
            {"id": "lt1", "tick_no": 8, "memory_category": "long_term"},
            {"id": "lt2", "tick_no": 7, "memory_category": "long_term"},
            {"id": "lt3", "tick_no": 6, "memory_category": "long_term"},
        ],
        "all": [
            {"id": "st1", "tick_no": 10, "memory_category": "short_term"},
            {"id": "st2", "tick_no": 9, "memory_category": "short_term"},
            {"id": "lt1", "tick_no": 8, "memory_category": "long_term"},
            {"id": "lt2", "tick_no": 7, "memory_category": "long_term"},
            {"id": "lt3", "tick_no": 6, "memory_category": "long_term"},
        ],
    }

    cache = MemoryCache(cache_data)

    # Get all recent
    results = cache.get_recent_memories(category="all", limit=3)
    assert [m["id"] for m in results] == ["st1", "st2", "lt1"]

    # Get long_term only
    results = cache.get_recent_memories(category="long_term", limit=2)
    assert [m["id"] for m in results] == ["lt1", "lt2"]

    # Get short_term only
    results = cache.get_recent_memories(category="short_term", limit=5)
    assert [m["id"] for m in results] == ["st1", "st2"]


def test_get_memories_about_agent():
    """Test getting memories about a specific agent."""
    cache_data = {
        "about_others": {
            "agent-bob": [
                {"id": "mem-bob-1", "tick_no": 5, "related_agent_id": "agent-bob"},
                {"id": "mem-bob-2", "tick_no": 3, "related_agent_id": "agent-bob"},
            ],
            "agent-charlie": [
                {"id": "mem-charlie-1", "tick_no": 4, "related_agent_id": "agent-charlie"},
            ],
        },
    }

    cache = MemoryCache(cache_data)

    # Get memories about Bob
    results = cache.get_memories_about_agent(other_agent_id="agent-bob", limit=5)
    assert [m["id"] for m in results] == ["mem-bob-1", "mem-bob-2"]

    # Get memories about Charlie with limit
    results = cache.get_memories_about_agent(other_agent_id="agent-charlie", limit=1)
    assert [m["id"] for m in results] == ["mem-charlie-1"]

    # Get memories about non-existent agent
    results = cache.get_memories_about_agent(other_agent_id="agent-none", limit=5)
    assert results == []


def test_get_memories_by_location():
    """Test getting memories by location."""
    cache_data = {
        "all": [
            {"id": "mem-cafe-1", "tick_no": 5, "location_id": "loc-cafe"},
            {"id": "mem-park-1", "tick_no": 4, "location_id": "loc-park"},
            {"id": "mem-cafe-2", "tick_no": 3, "location_id": "loc-cafe"},
            {"id": "mem-home-1", "tick_no": 2, "location_id": "loc-home"},
        ],
    }

    cache = MemoryCache(cache_data)

    # Get memories at cafe
    results = cache.get_memories_by_location(location_id="loc-cafe", limit=5)
    assert [m["id"] for m in results] == ["mem-cafe-1", "mem-cafe-2"]

    # Get memories at park with limit
    results = cache.get_memories_by_location(location_id="loc-park", limit=1)
    assert [m["id"] for m in results] == ["mem-park-1"]

    # Get memories at non-existent location
    results = cache.get_memories_by_location(location_id="loc-none", limit=5)
    assert results == []


def test_memory_cache_with_empty_data():
    """Test MemoryCache handles empty or None data gracefully."""
    # None data
    cache = MemoryCache(None)
    assert cache.search_memories("query") == []
    assert cache.get_recent_memories() == []
    assert cache.get_memories_about_agent("agent") == []
    assert cache.get_memories_by_location("loc") == []

    # Empty dict
    cache = MemoryCache({})
    assert cache.search_memories("query") == []
    assert cache.get_recent_memories() == []
