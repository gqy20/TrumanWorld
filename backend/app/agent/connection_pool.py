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

from app.agent.sdk_options import build_sdk_options
from app.agent.system_prompt import build_system_prompt
from app.infra.logging import get_logger
from app.infra.settings import Settings

logger = get_logger(__name__)

# 绕过嵌套会话检查（在 Claude Code 会话中运行时需要）
# 必须在导入 SDK 之前设置，但这里我们已经在运行时了
# 所以通过 env 传递给子进程


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
    """Agent 连接池，预热并缓存 ClaudeSDKClient 实例。

    使用方式：
        pool = AgentConnectionPool(settings)
        await pool.warmup(["alice", "bob"])  # 预热连接

        # 获取连接
        client = await pool.acquire("alice")
        try:
            await client.query("...")
            async for msg in client.receive_response():
                ...
        finally:
            await pool.release("alice")

        # 关闭所有连接
        await pool.close_all()
    """

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
        """构建基础 SDK 选项"""
        return build_sdk_options(
            self.settings,
            max_turns=3,  # 决策任务通常只需 1-3 轮
            max_budget_usd=self.settings.agent_budget_usd,
            model=self.settings.agent_model,
            cwd=str(self.settings.project_root),
            system_prompt=build_system_prompt(),
            permission_mode="bypassPermissions",
        )

    async def warmup(self, agent_ids: list[str]) -> int:
        """预热：提前建立连接

        Args:
            agent_ids: 需要预热的 agent ID 列表

        Returns:
            成功预热的连接数
        """
        if self._closed:
            logger.warning("Connection pool is closed, cannot warmup")
            return 0

        options = self._build_base_options()
        success_count = 0

        # 并行预热
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
            except Exception as e:
                logger.warning(f"Failed to warmup connection for {agent_id}: {e}")
                return False

        results = await asyncio.gather(*[warmup_one(aid) for aid in agent_ids])
        success_count = sum(1 for r in results if r)

        logger.info(f"Connection pool warmed up: {success_count}/{len(agent_ids)} agents")
        return success_count

    async def acquire(
        self,
        agent_id: str,
        options: ClaudeAgentOptions | None = None,
    ) -> ClaudeSDKClient:
        """获取客户端连接

        优先复用已有连接，否则新建。

        Args:
            agent_id: Agent ID
            options: SDK 选项（仅新建时使用）

        Returns:
            ClaudeSDKClient 实例
        """
        if self._closed:
            raise RuntimeError("Connection pool is closed")

        async with self._lock:
            # 尝试复用现有连接
            if agent_id in self._pool:
                pooled = self._pool[agent_id]
                if not pooled.in_use:
                    # 检查是否需要重连（错误过多）
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

            # 池满则清理最久未使用的
            if len(self._pool) >= self._max_connections:
                await self._evict_lru_locked()

            # 新建连接
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
        """释放客户端回池

        Args:
            agent_id: Agent ID
            had_error: 是否发生了错误（用于错误计数）
            session_id: SDK session ID，用于下次恢复对话
        """
        async with self._lock:
            if agent_id in self._pool:
                pooled = self._pool[agent_id]
                pooled.in_use = False
                pooled.last_used = time.time()
                if session_id:
                    pooled.session_id = session_id
                if had_error:
                    pooled.error_count += 1
                else:
                    # 成功调用重置错误计数
                    pooled.error_count = 0

    async def _evict_lru_locked(self) -> None:
        """清理最久未使用的连接（必须持有锁）"""
        if not self._pool:
            return

        # 找到最久未使用且不在使用中的连接
        lru_id = None
        lru_time = float("inf")

        for aid, pooled in self._pool.items():
            if not pooled.in_use and pooled.last_used < lru_time:
                lru_time = pooled.last_used
                lru_id = aid

        if lru_id:
            pooled = self._pool.pop(lru_id)
            try:
                await pooled.client.disconnect()
                logger.debug(f"Evicted LRU connection for agent: {lru_id}")
            except Exception as e:
                logger.warning(f"Error disconnecting evicted client {lru_id}: {e}")

    async def cleanup_idle(self) -> int:
        """清理空闲超时的连接

        Returns:
            清理的连接数
        """
        now = time.time()
        cleaned = 0

        async with self._lock:
            to_remove = [
                aid
                for aid, pooled in self._pool.items()
                if not pooled.in_use and (now - pooled.last_used) > self._idle_timeout
            ]

            for aid in to_remove:
                pooled = self._pool.pop(aid)
                try:
                    await pooled.client.disconnect()
                    cleaned += 1
                    logger.debug(f"Cleaned up idle connection for agent: {aid}")
                except Exception as e:
                    logger.warning(f"Error disconnecting idle client {aid}: {e}")

        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} idle connections")
        return cleaned

    async def close_all(self) -> None:
        """关闭所有连接"""
        self._closed = True

        async with self._lock:
            for aid, pooled in list(self._pool.items()):
                try:
                    await pooled.client.disconnect()
                    logger.debug(f"Closed connection for agent: {aid}")
                except Exception as e:
                    logger.warning(f"Error disconnecting client {aid}: {e}")
            self._pool.clear()

        logger.info("All connections closed")
        _kill_orphan_sdk_processes()

    @property
    def size(self) -> int:
        """当前池大小"""
        return len(self._pool)

    @property
    def active_count(self) -> int:
        """正在使用的连接数"""
        return sum(1 for p in self._pool.values() if p.in_use)

    def is_warmed_up(self, agent_id: str) -> bool:
        """检查指定 agent 是否已预热"""
        return agent_id in self._pool

    def get_session_id(self, agent_id: str) -> str | None:
        """获取指定 agent 的 session_id

        用于在下次调用时恢复对话。
        """
        if agent_id in self._pool:
            return self._pool[agent_id].session_id
        return None

    async def cleanup_run(self, run_id: str) -> int:
        """清理指定 run 的所有连接

        当 run 被删除或暂停时调用，释放相关连接资源。

        Args:
            run_id: 要清理的 run ID

        Returns:
            清理的连接数
        """
        cleaned = 0
        prefix = f"{run_id}:"

        async with self._lock:
            to_remove = [aid for aid in self._pool if aid.startswith(prefix)]

            for aid in to_remove:
                pooled = self._pool.pop(aid)
                try:
                    await pooled.client.disconnect()
                    cleaned += 1
                    logger.debug(f"Cleaned up connection for run: {aid}")
                except Exception as e:
                    logger.warning(f"Error disconnecting client {aid}: {e}")

        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} connections for run {run_id}")
        return cleaned


def _kill_orphan_sdk_processes() -> None:
    """强杀所有残留的 Claude SDK 子进程。

    根因分析：
    1. SDK close() 先发 SIGTERM，但 anyio TaskGroup 取消会将 process.wait() 中断，
       被 suppress(Exception) 吞掉，没有等到进程真正退出就返回。
    2. claude CLI 是 Node.js 进程，收到 SIGTERM 后需要 3~8 秒做优雅退出
       （保存 session、关闭 LSP、flush BigQuery metrics 等）。
    3. 父进程不等就退出，claude 子进程成为孤儿进程继续运行。

    此函数在连接池关闭后作为最后一道保险，直接发 SIGKILL 强杀。
    注意：进程此时已在处理第一个 SIGTERM，再发 SIGTERM 无效，必须用 SIGKILL。
    进程查找用 /proc/pid/cmdline 而非 pgrep -f，因为 pgrep 对超长命令行（>128 字节）匹配失败。
    """
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
                cmdline_path = f"/proc/{entry.name}/cmdline"
                with open(cmdline_path, "rb") as f:
                    cmdline = f.read()
                if marker.encode() in cmdline:
                    try:
                        os.kill(pid, signal.SIGKILL)  # SIGKILL: 进程已在处理 SIGTERM，必须强杀
                        killed.append(pid)
                    except ProcessLookupError:
                        pass
            except (FileNotFoundError, PermissionError, ValueError):
                continue
        if killed:
            logger.info(f"SIGKILL sent to {len(killed)} orphan SDK process(es): {killed}")
    except Exception as e:
        logger.warning(f"Failed to kill orphan SDK processes: {e}")


# ============ 全局连接池单例 ============

_global_pool: AgentConnectionPool | None = None
_pool_lock = asyncio.Lock()


async def get_connection_pool() -> AgentConnectionPool:
    """获取全局连接池单例"""
    global _global_pool

    if _global_pool is not None:
        return _global_pool

    async with _pool_lock:
        if _global_pool is None:
            from app.infra.settings import get_settings

            settings = get_settings()
            _global_pool = AgentConnectionPool(settings)
            logger.info("Created global connection pool")

    return _global_pool


async def close_connection_pool() -> None:
    """关闭全局连接池"""
    global _global_pool

    if _global_pool is not None:
        await _global_pool.close_all()
        _global_pool = None
        logger.info("Global connection pool closed")
