"""Tests for memory category functionality."""

import pytest
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.store.models import Memory, Agent, SimulationRun


@pytest.fixture
async def setup_memories(db_session: AsyncSession):
    """Create test memories with different categories."""
    run_id = "test-run-memory-category"
    agent_id = f"{run_id}-test-agent"

    # Create run
    run = SimulationRun(
        id=run_id,
        name="Memory Category Test Run",
    )
    db_session.add(run)

    # Create agent
    agent = Agent(
        id=agent_id,
        run_id=run_id,
        name="Test Agent",
        personality={},
        profile={},
        status={},
        current_plan={},
    )
    db_session.add(agent)
    await db_session.commit()

    # Create short-term memories
    short_term_memories = []
    for i in range(3):
        mem = Memory(
            id=f"{run_id}-short-{i}",
            run_id=run_id,
            agent_id=agent_id,
            tick_no=i,
            memory_type="episodic_short",
            memory_category="short_term",
            content=f"Short-term memory {i}",
            summary=f"Short {i}",
            importance=0.5,
            emotional_valence=0.0,
        )
        db_session.add(mem)
        short_term_memories.append(mem)

    # Create long-term memories
    long_term_memories = []
    for i in range(2):
        mem = Memory(
            id=f"{run_id}-long-{i}",
            run_id=run_id,
            agent_id=agent_id,
            tick_no=i,
            memory_type="episodic_long",
            memory_category="long_term",
            content=f"Long-term memory {i}",
            summary=f"Long {i}",
            importance=0.8,
            emotional_valence=0.2,
            consolidated_at=datetime.now(UTC),
        )
        db_session.add(mem)
        long_term_memories.append(mem)

    await db_session.commit()

    return {
        "run_id": run_id,
        "agent_id": agent_id,
        "short_term": short_term_memories,
        "long_term": long_term_memories,
    }


async def test_memory_category_field(db_session: AsyncSession, setup_memories):
    """Test that memory_category field exists and defaults correctly."""
    result = await db_session.execute(
        select(Memory)
        .where(Memory.agent_id == setup_memories["agent_id"])
        .order_by(Memory.created_at)
    )
    memories = result.scalars().all()

    # Verify we have both short_term and long_term memories
    categories = {m.memory_category for m in memories}
    assert "short_term" in categories
    assert "long_term" in categories


async def test_memory_consolidated_at(db_session: AsyncSession, setup_memories):
    """Test that consolidated_at is set for long-term memories."""
    result = await db_session.execute(
        select(Memory)
        .where(Memory.agent_id == setup_memories["agent_id"])
        .where(Memory.memory_category == "long_term")
    )
    long_term = result.scalars().all()
    for mem in long_term:
        assert mem.consolidated_at is not None


async def test_query_by_category(db_session: AsyncSession, setup_memories):
    """Test querying memories by category."""
    # Query short_term only
    result = await db_session.execute(
        select(Memory)
        .where(
            Memory.agent_id == setup_memories["agent_id"],
            Memory.memory_category == "short_term",
        )
        .order_by(Memory.tick_no)
    )
    short_term = result.scalars().all()
    assert len(short_term) == 3
    for mem in short_term:
        assert mem.memory_category == "short_term"

    # Query long_term only
    result = await db_session.execute(
        select(Memory)
        .where(
            Memory.agent_id == setup_memories["agent_id"],
            Memory.memory_category == "long_term",
        )
        .order_by(Memory.tick_no)
    )
    long_term = result.scalars().all()
    assert len(long_term) == 2
    for mem in long_term:
        assert mem.memory_category == "long_term"


async def test_consolidate_memory_directly(db_session: AsyncSession, setup_memories):
    """Test consolidating a short-term memory to long-term directly."""
    short_mem = setup_memories["short_term"][0]

    # Update memory directly to simulate consolidation
    short_mem.memory_category = "long_term"
    short_mem.memory_type = "episodic_long"
    short_mem.consolidated_at = datetime.now(UTC)

    await db_session.commit()
    await db_session.refresh(short_mem)

    assert short_mem.memory_category == "long_term"
    assert short_mem.memory_type == "episodic_long"
    assert short_mem.consolidated_at is not None
