"""MCP Memory Tools for TrumanWorld Agents.

This module provides MCP tools that allow agents to query their memories
on-demand, rather than having all memories injected into the prompt.

The server is created dynamically per-agent with the agent's runtime context
(database engine, agent_id, run_id) to enable memory queries.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from mcp.server import Server
from mcp.types import Tool, TextContent

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)


def _format_memory_result(memories: list[dict[str, Any]]) -> str:
    """Format memory records for display to agent."""
    if not memories:
        return "没有找到相关记忆。"

    lines = ["找到以下记忆："]
    for i, mem in enumerate(memories, 1):
        tick_info = f"Tick {mem.get('tick_no', '?')}"
        category_info = mem.get("memory_category", "unknown")
        summary = mem.get("summary") or mem.get("content", "")[:50]
        lines.append(f"{i}. [{tick_info}] [{category_info}] {summary}")
        if mem.get("related_agent_name"):
            lines.append(f"   相关人物: {mem['related_agent_name']}")
    return "\n".join(lines)


async def _search_memories(
    engine: "AsyncEngine",
    agent_id: str,
    query: str,
    limit: int = 5,
    category: str = "long_term",
) -> list[dict[str, Any]]:
    """Search agent's memories by keyword.

    Args:
        engine: Database engine
        agent_id: Agent ID
        query: Search keyword
        limit: Max results
        category: Memory category to search ("short_term", "long_term", or "all")
    """
    from sqlalchemy import select, or_
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.store.models import Memory, Agent

    async with AsyncSession(engine) as session:
        agents_result = await session.execute(select(Agent.id, Agent.name))
        agent_names = {row.id: row.name for row in agents_result}

        pattern = f"%{query}%"
        stmt = select(Memory).where(
            Memory.agent_id == agent_id,
            or_(
                Memory.content.ilike(pattern),
                Memory.summary.ilike(pattern),
            ),
        )

        # Filter by category unless searching all
        if category != "all":
            stmt = stmt.where(Memory.memory_category == category)

        stmt = stmt.order_by(Memory.created_at.desc()).limit(limit)
        result = await session.execute(stmt)
        memories = result.scalars().all()

        return [
            {
                "id": m.id,
                "content": m.content,
                "summary": m.summary,
                "tick_no": m.tick_no,
                "memory_type": m.memory_type,
                "memory_category": m.memory_category,
                "importance": m.importance,
                "related_agent_id": m.related_agent_id,
                "related_agent_name": agent_names.get(m.related_agent_id),
            }
            for m in memories
        ]


async def _get_recent_memories(
    engine: "AsyncEngine",
    agent_id: str,
    limit: int = 5,
    category: str = "all",
) -> list[dict[str, Any]]:
    """Get agent's most recent memories.

    Args:
        engine: Database engine
        agent_id: Agent ID
        limit: Max results
        category: Memory category filter (long_term, short_term, all)
    """
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.store.models import Memory, Agent

    async with AsyncSession(engine) as session:
        agents_result = await session.execute(select(Agent.id, Agent.name))
        agent_names = {row.id: row.name for row in agents_result}

        stmt = select(Memory).where(Memory.agent_id == agent_id)
        if category != "all":
            stmt = stmt.where(Memory.memory_category == category)
        stmt = stmt.order_by(Memory.created_at.desc()).limit(limit)
        result = await session.execute(stmt)
        memories = result.scalars().all()

        return [
            {
                "id": m.id,
                "content": m.content,
                "summary": m.summary,
                "tick_no": m.tick_no,
                "memory_type": m.memory_type,
                "memory_category": m.memory_category,
                "importance": m.importance,
                "related_agent_id": m.related_agent_id,
                "related_agent_name": agent_names.get(m.related_agent_id),
            }
            for m in memories
        ]


async def _get_memories_about_agent(
    engine: "AsyncEngine",
    agent_id: str,
    other_agent_id: str,
    run_id: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Get memories involving another specific agent."""
    from sqlalchemy import select, or_
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.store.models import Memory, Agent

    async with AsyncSession(engine) as session:
        # Resolve agent ID if short name provided
        resolved_id = other_agent_id
        if not other_agent_id.startswith(run_id):
            result = await session.execute(
                select(Agent).where(
                    Agent.run_id == run_id,
                    or_(
                        Agent.id == other_agent_id,
                        Agent.name.ilike(f"%{other_agent_id}%"),
                    ),
                )
            )
            agent = result.scalar_one_or_none()
            if agent:
                resolved_id = agent.id

        # Get other agent's name
        other_agent = await session.get(Agent, resolved_id)
        other_name = other_agent.name if other_agent else resolved_id

        result = await session.execute(
            select(Memory)
            .where(
                Memory.agent_id == agent_id,
                Memory.related_agent_id == resolved_id,
            )
            .order_by(Memory.created_at.desc())
            .limit(limit)
        )
        memories = result.scalars().all()

        return [
            {
                "id": m.id,
                "content": m.content,
                "summary": m.summary,
                "tick_no": m.tick_no,
                "memory_type": m.memory_type,
                "importance": m.importance,
                "related_agent_id": m.related_agent_id,
                "related_agent_name": other_name,
            }
            for m in memories
        ]


async def _get_memories_by_location(
    engine: "AsyncEngine",
    agent_id: str,
    location_id: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Get memories that occurred at a specific location."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.store.models import Memory, Agent, Location

    async with AsyncSession(engine) as session:
        location = await session.get(Location, location_id)
        location_name = location.name if location else location_id

        agents_result = await session.execute(select(Agent.id, Agent.name))
        agent_names = {row.id: row.name for row in agents_result}

        result = await session.execute(
            select(Memory)
            .where(
                Memory.agent_id == agent_id,
                Memory.location_id == location_id,
            )
            .order_by(Memory.created_at.desc())
            .limit(limit)
        )
        memories = result.scalars().all()

        return [
            {
                "id": m.id,
                "content": m.content,
                "summary": m.summary,
                "tick_no": m.tick_no,
                "memory_type": m.memory_type,
                "importance": m.importance,
                "location_id": m.location_id,
                "location_name": location_name,
                "related_agent_id": m.related_agent_id,
                "related_agent_name": agent_names.get(m.related_agent_id),
            }
            for m in memories
        ]


# Tool definitions
MEMORY_TOOLS_DEFS = [
    Tool(
        name="search_memories",
        description="""搜索你的记忆。当你需要回忆过去发生的事情时调用。

使用场景：
- 想回忆某个关键词相关的事情
- 不确定具体时间或人物，但有印象
- 搜索特定类型的事件

参数：
- query: 搜索关键词（如人名、地点、事件类型）
- limit: 返回条数，默认5
- category: 记忆类别，默认 long_term（长期记忆), short_term(临时记忆), all(所有)""",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "limit": {"type": "integer", "description": "返回条数，默认5", "default": 5},
                "category": {
                    "type": "string",
                    "description": "记忆类别: long_term(长期记忆,搜索)、 short_term(临时记忆,最近发生), all(所有)",
                    "enum": ["long_term", "short_term", "all"],
                    "default": "long_term",
                },
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="get_recent_memories",
        description="""获取你最近的记忆。当你需要快速回顾近期发生的事情时调用。

使用场景：
- 刚醒来，想回顾最近做了什么
- 需要了解最近的状态变化
- 做日常决策前快速回顾

参数：
- limit: 返回条数，默认5""",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "返回条数，默认5", "default": 5},
            },
        },
    ),
    Tool(
        name="get_memories_about_agent",
        description="""获取与某人的交互记忆。当你准备和某人交谈时调用。

使用场景：
- 准备和某人交谈前，回忆之前的对话
- 想了解和某人的关系历史
- 需要根据过往经历决定如何互动

参数：
- other_agent_id: 对方的ID或名字
- limit: 返回条数，默认5""",
        inputSchema={
            "type": "object",
            "properties": {
                "other_agent_id": {"type": "string", "description": "对方的ID或名字"},
                "limit": {"type": "integer", "description": "返回条数，默认5", "default": 5},
            },
            "required": ["other_agent_id"],
        },
    ),
    Tool(
        name="get_memories_by_location",
        description="""获取在某地点的记忆。当你准备前往某地点时调用。

使用场景：
- 准备去某地前，回忆那里的经历
- 想了解在某地发生过什么
- 决定是否要去某地

参数：
- location_id: 地点ID
- limit: 返回条数，默认5""",
        inputSchema={
            "type": "object",
            "properties": {
                "location_id": {"type": "string", "description": "地点ID"},
                "limit": {"type": "integer", "description": "返回条数，默认5", "default": 5},
            },
            "required": ["location_id"],
        },
    ),
]


def create_memory_mcp_server(
    engine: "AsyncEngine",
    agent_id: str,
    run_id: str,
) -> Server:
    """Create an MCP server with memory tools for a specific agent.

    This creates a new MCP server instance with handlers bound to the
    provided database engine and agent context.

    Args:
        engine: SQLAlchemy async engine for database access
        agent_id: The agent whose memories will be queried
        run_id: The simulation run ID for context resolution

    Returns:
        Configured MCP Server instance
    """
    server = Server("trumanworld-memory")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """Return available memory tools."""
        return MEMORY_TOOLS_DEFS

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Execute a memory tool call."""
        try:
            if name == "search_memories":
                memories = await _search_memories(
                    engine,
                    agent_id,
                    arguments["query"],
                    arguments.get("limit", 5),
                    arguments.get("category", "long_term"),
                )
                return [TextContent(type="text", text=_format_memory_result(memories))]

            elif name == "get_recent_memories":
                memories = await _get_recent_memories(engine, agent_id, arguments.get("limit", 5))
                return [TextContent(type="text", text=_format_memory_result(memories))]

            elif name == "get_memories_about_agent":
                memories = await _get_memories_about_agent(
                    engine,
                    agent_id,
                    arguments["other_agent_id"],
                    run_id,
                    arguments.get("limit", 5),
                )
                return [TextContent(type="text", text=_format_memory_result(memories))]

            elif name == "get_memories_by_location":
                memories = await _get_memories_by_location(
                    engine, agent_id, arguments["location_id"], arguments.get("limit", 5)
                )
                return [TextContent(type="text", text=_format_memory_result(memories))]

            else:
                return [TextContent(type="text", text=f"未知工具: {name}")]

        except Exception as e:
            logger.error(f"Error executing memory tool {name}: {e}")
            return [TextContent(type="text", text=f"查询记忆时出错: {e}")]

    return server
