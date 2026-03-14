"""Cached MCP Memory Tools for TrumanWorld Agents.

This module provides MCP tools that query pre-loaded memory cache instead of
creating database sessions, avoiding greenlet conflicts with anyio task groups.

Usage:
    from app.agent.memory_cache import MemoryCache
    from app.agent.memory_mcp_server_cached import create_memory_mcp_server_cached

    # Pre-load memory cache during Phase 1
    cache = MemoryCache(agent_snapshot.memory_cache)

    # Create MCP server with cache (no DB session needed)
    server = create_memory_mcp_server_cached(cache)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from mcp.server import Server
from mcp.types import TextContent, Tool

if TYPE_CHECKING:
    from app.agent.memory_cache import MemoryCache

logger = logging.getLogger(__name__)

# Tool definitions (same as original memory_mcp_server)
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
- category: 记忆类别，默认 long_term（长期记忆), medium_term(中期记忆), short_term(临时记忆), all(所有)""",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "limit": {"type": "integer", "description": "返回条数，默认5", "default": 5},
                "category": {
                    "type": "string",
                    "description": "记忆类别: long_term(长期记忆,搜索)、 medium_term(中期记忆)、 short_term(临时记忆,最近发生), all(所有)",
                    "enum": ["long_term", "medium_term", "short_term", "all"],
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
                "category": {
                    "type": "string",
                    "description": "记忆类别: long_term(长期记忆), medium_term(中期记忆), short_term(临时记忆,默认), all(所有)",
                    "enum": ["long_term", "medium_term", "short_term", "all"],
                    "default": "short_term",
                },
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


def create_memory_mcp_server_cached(cache: MemoryCache) -> Server:
    """Create an MCP server with memory tools using pre-loaded cache.

    This version uses MemoryCache instead of creating database sessions,
    avoiding greenlet_spawn conflicts with anyio task groups.

    Args:
        cache: Pre-loaded MemoryCache instance

    Returns:
        Configured MCP Server instance
    """
    server = Server("trumanworld-memory-cached")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """Return available memory tools."""
        return MEMORY_TOOLS_DEFS

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Execute a memory tool call using cached data."""
        try:
            if name == "search_memories":
                memories = cache.search_memories(
                    query=arguments["query"],
                    category=arguments.get("category", "long_term"),
                    limit=arguments.get("limit", 5),
                )
                return [TextContent(type="text", text=cache.format_for_display(memories))]

            elif name == "get_recent_memories":
                memories = cache.get_recent_memories(
                    category=arguments.get("category", "short_term"),
                    limit=arguments.get("limit", 5),
                )
                return [TextContent(type="text", text=cache.format_for_display(memories))]

            elif name == "get_memories_about_agent":
                memories = cache.get_memories_about_agent(
                    other_agent_id=arguments["other_agent_id"],
                    limit=arguments.get("limit", 5),
                )
                return [TextContent(type="text", text=cache.format_for_display(memories))]

            elif name == "get_memories_by_location":
                memories = cache.get_memories_by_location(
                    location_id=arguments["location_id"],
                    limit=arguments.get("limit", 5),
                )
                return [TextContent(type="text", text=cache.format_for_display(memories))]

            else:
                return [TextContent(type="text", text=f"未知工具: {name}")]

        except Exception as e:
            logger.error(f"Error executing memory tool {name}: {e}")
            return [TextContent(type="text", text=f"查询记忆时出错: {e}")]

    return server
