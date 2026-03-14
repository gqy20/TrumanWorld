"""Claude SDK Client Connection Pool.

缓存 ClaudeSDKClient 实例，避免每次调用都启动新进程。
测试表明：复用连接可将延迟从 ~7s 降至 ~2s。
"""

from __future__ import annotations

import asyncio
import os
import signal
import time
from dataclasses import dataclass

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

from app.agent.system_prompt import build_system_prompt
from app.cognition.claude.sdk_options import build_sdk_options
from app.infra.logging import get_logger
from app.infra.settings import Settings

logger = get_logger(__name__)


@dataclass
class PooledClient:
    """池化的客户端"""

    agent_id: str
    client: ClaudeSDKClient
    options: ClaudeAgentOptions
    last_used: float
    in_use: bool = False
    error_count: int = 0
    session_id: str | None = None  # SDK session ID，用于恢复对话


class AgentConnectionPool:
    """Agent 连接池，预热并缓存 ClaudeSDKClient 实例。"""

    MAX_ERRORS_BEFORE_RECONNECT = 3
    DEFAULT_IDLE_TIMEOUT = 300.0  # 5 分钟

    def __init__(
        self,
        settings: Settings,
        max_connections: int = 20,
        idle_timeout_seconds: float = DEFAULT_IDLE_TIMEOUT,
    ) -> None:
        self.settings = settings
        self._pool: dict[str, PooledClient] = {}
        self._lock = asyncio.Lock()
        self._max_connections = max_connections
        self._idle_timeout = idle_timeout_seconds
        self._closed = False

    def _build_base_options(self) -> ClaudeAgentOptions:
        return build_sdk_options(
            self.settings,
            max_turns=3,
            max_budget_usd=self.settings.agent_budget_usd,
            model=self.settings.agent_model,
            cwd=str(self.settings.project_root),
            system_prompt=build_system_prompt(),
            permission_mode="bypassPermissions",
        )

    async def warmup(self, agent_ids: list[str]) -> int:
        if self._closed:
            logger.warning("Connection pool is closed, cannot warmup")
            return 0

        options = self._build_base_options()

        async def warmup_one(agent_id: str) -> bool:
            try:
                client = ClaudeSDKClient(options=options)
                await client.connect()
                async with self._lock:
                    self._pool[agent_id] = PooledClient(
                        agent_id=agent_id,
                        client=client,
                        options=options,
                        last_used=time.time(),
                        in_use=False,
                    )
                logger.info(f"Warmed up connection for agent: {agent_id}")
                return True
            except Exception as exc:
                logger.warning(f"Failed to warmup connection for {agent_id}: {exc}")
                return False

        results = await asyncio.gather(*[warmup_one(aid) for aid in agent_ids])
        success_count = sum(1 for result in results if result)
        logger.info(f"Connection pool warmed up: {success_count}/{len(agent_ids)} agents")
        return success_count

    async def acquire(
        self,
        agent_id: str,
        options: ClaudeAgentOptions | None = None,
    ) -> ClaudeSDKClient:
        if self._closed:
            raise RuntimeError("Connection pool is closed")

        async with self._lock:
            if agent_id in self._pool:
                pooled = self._pool[agent_id]
                if not pooled.in_use:
                    if pooled.error_count >= self.MAX_ERRORS_BEFORE_RECONNECT:
                        logger.info(f"Reconnecting client for {agent_id} due to errors")
                        try:
                            await pooled.client.disconnect()
                        except Exception:
                            pass
                        del self._pool[agent_id]
                    else:
                        pooled.in_use = True
                        pooled.last_used = time.time()
                        logger.debug(f"Reusing connection for agent: {agent_id}")
                        return pooled.client

            if len(self._pool) >= self._max_connections:
                await self._evict_lru_locked()

            if options is None:
                options = self._build_base_options()

            client = ClaudeSDKClient(options=options)
            await client.connect()
            self._pool[agent_id] = PooledClient(
                agent_id=agent_id,
                client=client,
                options=options,
                last_used=time.time(),
                in_use=True,
            )
            logger.debug(f"Created new connection for agent: {agent_id}")
            return client

    async def release(
        self,
        agent_id: str,
        had_error: bool = False,
        session_id: str | None = None,
    ) -> None:
        async with self._lock:
            if agent_id in self._pool:
                pooled = self._pool[agent_id]
                pooled.in_use = False
                pooled.last_used = time.time()
                if session_id:
                    pooled.session_id = session_id
                pooled.error_count = pooled.error_count + 1 if had_error else 0

    async def _evict_lru_locked(self) -> None:
        if not self._pool:
            return

        lru_id = None
        lru_time = float("inf")
        for agent_id, pooled in self._pool.items():
            if not pooled.in_use and pooled.last_used < lru_time:
                lru_time = pooled.last_used
                lru_id = agent_id

        if lru_id:
            pooled = self._pool.pop(lru_id)
            try:
                await pooled.client.disconnect()
                logger.debug(f"Evicted LRU connection for agent: {lru_id}")
            except Exception as exc:
                logger.warning(f"Error disconnecting evicted client {lru_id}: {exc}")

    async def cleanup_idle(self) -> int:
        now = time.time()
        cleaned = 0

        async with self._lock:
            to_remove = [
                agent_id
                for agent_id, pooled in self._pool.items()
                if not pooled.in_use and (now - pooled.last_used) > self._idle_timeout
            ]

            for agent_id in to_remove:
                pooled = self._pool.pop(agent_id)
                try:
                    await pooled.client.disconnect()
                    cleaned += 1
                    logger.debug(f"Cleaned up idle connection for agent: {agent_id}")
                except Exception as exc:
                    logger.warning(f"Error disconnecting idle client {agent_id}: {exc}")

        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} idle connections")
        return cleaned

    async def close_all(self) -> None:
        self._closed = True

        async with self._lock:
            for agent_id, pooled in list(self._pool.items()):
                try:
                    await pooled.client.disconnect()
                    logger.debug(f"Closed connection for agent: {agent_id}")
                except Exception as exc:
                    logger.warning(f"Error disconnecting client {agent_id}: {exc}")
            self._pool.clear()

        logger.info("All connections closed")
        _kill_orphan_sdk_processes()

    @property
    def size(self) -> int:
        return len(self._pool)

    @property
    def active_count(self) -> int:
        return sum(1 for pooled in self._pool.values() if pooled.in_use)

    def is_warmed_up(self, agent_id: str) -> bool:
        return agent_id in self._pool

    def get_session_id(self, agent_id: str) -> str | None:
        if agent_id in self._pool:
            return self._pool[agent_id].session_id
        return None

    async def cleanup_run(self, run_id: str) -> int:
        cleaned = 0
        prefix = f"{run_id}:"

        async with self._lock:
            to_remove = [agent_id for agent_id in self._pool if agent_id.startswith(prefix)]

            for agent_id in to_remove:
                pooled = self._pool.pop(agent_id)
                try:
                    await pooled.client.disconnect()
                    cleaned += 1
                    logger.debug(f"Cleaned up connection for run: {agent_id}")
                except Exception as exc:
                    logger.warning(f"Error disconnecting client {agent_id}: {exc}")

        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} connections for run {run_id}")
        return cleaned


def _kill_orphan_sdk_processes() -> None:
    marker = "claude_agent_sdk/_bundled/claude"
    self_pid = os.getpid()
    killed = []
    try:
        for entry in os.scandir("/proc"):
            if not entry.name.isdigit():
                continue
            pid = int(entry.name)
            if pid == self_pid:
                continue
            try:
                with open(f"/proc/{entry.name}/cmdline", "rb") as file:
                    cmdline = file.read()
                if marker.encode() in cmdline:
                    try:
                        os.kill(pid, signal.SIGKILL)
                        killed.append(pid)
                    except ProcessLookupError:
                        pass
            except (FileNotFoundError, PermissionError, ValueError):
                continue
        if killed:
            logger.info(f"SIGKILL sent to {len(killed)} orphan SDK process(es): {killed}")
    except Exception as exc:
        logger.warning(f"Failed to kill orphan SDK processes: {exc}")


_global_pool: AgentConnectionPool | None = None
_pool_lock = asyncio.Lock()


async def get_connection_pool() -> AgentConnectionPool:
    global _global_pool

    if _global_pool is not None:
        return _global_pool

    async with _pool_lock:
        if _global_pool is None:
            from app.infra.settings import get_settings

            _global_pool = AgentConnectionPool(get_settings())
            logger.info("Created global connection pool")

    return _global_pool


async def close_connection_pool() -> None:
    global _global_pool

    if _global_pool is not None:
        await _global_pool.close_all()
        _global_pool = None
        logger.info("Global connection pool closed")


def peek_connection_pool() -> AgentConnectionPool | None:
    return _global_pool


__all__ = [
    "AgentConnectionPool",
    "PooledClient",
    "close_connection_pool",
    "get_connection_pool",
    "peek_connection_pool",
]
