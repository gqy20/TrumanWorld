"""测试 ClaudeSDKClient 的稳定性和复用能力。

运行方式：
    cd backend && python tests/test_sdk_client_stability.py

注意：此测试不能在 Claude Code 会话中运行，因为 SDK 会尝试启动嵌套的 Claude Code 实例。
如果必须在 Claude Code 中运行，需要先 unset CLAUDECODE 环境变量。
"""

import asyncio
import os
import time
from dataclasses import dataclass
from typing import Any

# 绕过嵌套会话检查 - 必须在导入 SDK 之前设置
os.environ.pop("CLAUDECODE", None)

import pytest

# 检查 SDK 是否可用
pytest.importorskip("claude_agent_sdk")

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    query,
)


@dataclass
class TestResult:
    """测试结果"""

    method: str
    query_no: int
    success: bool
    latency_seconds: float
    error: str | None = None
    response_preview: str | None = None


async def run_query_test(num_queries: int = 3) -> list[TestResult]:
    """测试 query() 方式 - 每次新建连接"""
    results = []

    options = ClaudeAgentOptions(
        max_turns=1,
        max_budget_usd=0.1,
        permission_mode="bypassPermissions",
    )

    for i in range(num_queries):
        start = time.time()
        try:
            response_text = []
            async for message in query(
                prompt=f"请只回复一个数字：{i + 1}",
                options=options,
            ):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if hasattr(block, "text"):
                            response_text.append(block.text)
                elif isinstance(message, ResultMessage):
                    pass  # 完成

            elapsed = time.time() - start
            results.append(
                TestResult(
                    method="query",
                    query_no=i + 1,
                    success=True,
                    latency_seconds=elapsed,
                    response_preview="".join(response_text)[:50],
                )
            )
        except Exception as e:
            elapsed = time.time() - start
            results.append(
                TestResult(
                    method="query",
                    query_no=i + 1,
                    success=False,
                    latency_seconds=elapsed,
                    error=str(e),
                )
            )

    return results


async def run_client_test(num_queries: int = 3) -> list[TestResult]:
    """测试 ClaudeSDKClient 方式 - 复用连接"""
    results = []

    options = ClaudeAgentOptions(
        max_turns=1,
        max_budget_usd=0.1,
        permission_mode="bypassPermissions",
    )

    # 连接阶段
    connect_start = time.time()
    client = ClaudeSDKClient(options=options)

    try:
        await client.connect()
        connect_time = time.time() - connect_start
        print(f"[CLIENT] 连接耗时: {connect_time:.2f}s")

        # 多次查询复用同一连接
        for i in range(num_queries):
            start = time.time()
            try:
                # 发送查询
                await client.query(f"请只回复一个数字：{i + 1}")

                # 接收响应
                response_text = []
                async for message in client.receive_response():
                    if isinstance(message, AssistantMessage):
                        for block in message.content:
                            if hasattr(block, "text"):
                                response_text.append(block.text)
                    elif isinstance(message, ResultMessage):
                        break  # 收到结果即结束

                elapsed = time.time() - start
                results.append(
                    TestResult(
                        method="client",
                        query_no=i + 1,
                        success=True,
                        latency_seconds=elapsed,
                        response_preview="".join(response_text)[:50],
                    )
                )

            except Exception as e:
                elapsed = time.time() - start
                results.append(
                    TestResult(
                        method="client",
                        query_no=i + 1,
                        success=False,
                        latency_seconds=elapsed,
                        error=str(e),
                    )
                )

    except Exception as e:
        results.append(
            TestResult(
                method="client",
                query_no=0,
                success=False,
                latency_seconds=time.time() - connect_start,
                error=f"连接失败: {e}",
            )
        )
    finally:
        await client.disconnect()

    return results


async def run_concurrent_client_test(
    num_clients: int = 3,
    queries_per_client: int = 2,
) -> dict[str, Any]:
    """测试多个客户端并发"""
    results = {
        "clients": [],
        "total_time": 0,
        "errors": [],
    }

    async def run_single_client(client_id: int) -> list[TestResult]:
        """单个客户端的测试"""
        client_results = []

        options = ClaudeAgentOptions(
            max_turns=1,
            max_budget_usd=0.1,
            permission_mode="bypassPermissions",
        )

        client = ClaudeSDKClient(options=options)
        try:
            connect_start = time.time()
            await client.connect()
            connect_time = time.time() - connect_start
            print(f"[CLIENT-{client_id}] 连接耗时: {connect_time:.2f}s")

            for i in range(queries_per_client):
                start = time.time()
                try:
                    await client.query(f"Client {client_id}, Query {i + 1}: 回复一个数字")
                    response_text = []
                    async for message in client.receive_response():
                        if isinstance(message, AssistantMessage):
                            for block in message.content:
                                if hasattr(block, "text"):
                                    response_text.append(block.text)
                        elif isinstance(message, ResultMessage):
                            break

                    elapsed = time.time() - start
                    client_results.append(
                        TestResult(
                            method=f"client-{client_id}",
                            query_no=i + 1,
                            success=True,
                            latency_seconds=elapsed,
                            response_preview="".join(response_text)[:30],
                        )
                    )
                except Exception as e:
                    elapsed = time.time() - start
                    client_results.append(
                        TestResult(
                            method=f"client-{client_id}",
                            query_no=i + 1,
                            success=False,
                            latency_seconds=elapsed,
                            error=str(e),
                        )
                    )

        except Exception as e:
            client_results.append(
                TestResult(
                    method=f"client-{client_id}",
                    query_no=0,
                    success=False,
                    latency_seconds=0,
                    error=f"连接失败: {e}",
                )
            )
        finally:
            await client.disconnect()

        return client_results

    # 并发启动所有客户端
    start = time.time()
    tasks = [run_single_client(i) for i in range(num_clients)]
    all_results = await asyncio.gather(*tasks, return_exceptions=True)
    results["total_time"] = time.time() - start

    for i, r in enumerate(all_results):
        if isinstance(r, Exception):
            results["errors"].append(f"Client {i} failed: {r}")
        else:
            results["clients"].extend(r)

    return results


async def test_long_running_client() -> dict[str, Any]:
    """测试长时间运行的客户端稳定性"""
    results = {
        "queries": [],
        "disconnects": 0,
        "errors": [],
    }

    options = ClaudeAgentOptions(
        max_turns=1,
        max_budget_usd=0.5,
        permission_mode="bypassPermissions",
    )

    client = ClaudeSDKClient(options=options)

    try:
        await client.connect()
        print("[LONG-RUN] 客户端已连接")

        # 进行 10 次查询，每次间隔 1 秒
        for i in range(10):
            start = time.time()
            try:
                await client.query(f"查询 {i + 1}/10: 回复 OK")
                response_text = []
                async for message in client.receive_response():
                    if isinstance(message, AssistantMessage):
                        for block in message.content:
                            if hasattr(block, "text"):
                                response_text.append(block.text)
                    elif isinstance(message, ResultMessage):
                        break

                elapsed = time.time() - start
                results["queries"].append(
                    {
                        "no": i + 1,
                        "success": True,
                        "latency": elapsed,
                        "response": "".join(response_text)[:30],
                    }
                )
                print(f"[LONG-RUN] 查询 {i + 1} 完成: {elapsed:.2f}s")

                # 间隔 1 秒
                await asyncio.sleep(1)

            except Exception as e:
                elapsed = time.time() - start
                results["queries"].append(
                    {
                        "no": i + 1,
                        "success": False,
                        "latency": elapsed,
                        "error": str(e),
                    }
                )
                results["errors"].append(str(e))
                print(f"[LONG-RUN] 查询 {i + 1} 失败: {e}")

                # 尝试重连
                try:
                    await client.disconnect()
                    await client.connect()
                    results["disconnects"] += 1
                    print("[LONG-RUN] 已重连")
                except Exception as reconnect_error:
                    results["errors"].append(f"重连失败: {reconnect_error}")
                    break

    except Exception as e:
        results["errors"].append(f"初始连接失败: {e}")
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass

    return results


# ============ Pytest 测试用例 ============


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("TRUMANWORLD_ANTHROPIC_API_KEY")
    or os.getenv("TRUMANWORLD_ANTHROPIC_API_KEY") == "test-key",
    reason="需要有效的 Anthropic API Key 才能运行",
)
async def test_query_latency():
    """测试 query() 的延迟"""
    print("\n=== 测试 query() 延迟 ===")
    results = await run_query_test(num_queries=3)

    for r in results:
        status = "✓" if r.success else "✗"
        print(
            f"  [{status}] Query {r.query_no}: {r.latency_seconds:.2f}s - {r.response_preview or r.error}"
        )

    # 断言：至少有一个成功
    assert any(r.success for r in results), "所有 query 都失败了"


@pytest.mark.asyncio
async def test_client_latency():
    """测试 ClaudeSDKClient 的延迟"""
    print("\n=== 测试 ClaudeSDKClient 延迟 ===")
    results = await run_client_test(num_queries=3)

    for r in results:
        status = "✓" if r.success else "✗"
        print(
            f"  [{status}] Query {r.query_no}: {r.latency_seconds:.2f}s - {r.response_preview or r.error}"
        )

    # 断言：至少有一个成功
    assert any(r.success for r in results), "所有 client query 都失败了"


@pytest.mark.asyncio
async def test_compare_latency():
    """对比两种方式的延迟"""
    print("\n=== 延迟对比测试 ===")

    # query 方式
    query_results = await run_query_test(num_queries=3)
    query_avg = sum(r.latency_seconds for r in query_results if r.success) / max(
        1, sum(1 for r in query_results if r.success)
    )

    # client 方式
    client_results = await run_client_test(num_queries=3)
    client_avg = sum(r.latency_seconds for r in client_results if r.success) / max(
        1, sum(1 for r in client_results if r.success)
    )

    print(f"\n  query() 平均延迟: {query_avg:.2f}s")
    print(f"  client 复用平均延迟: {client_avg:.2f}s")

    if query_avg > 0 and client_avg > 0:
        speedup = query_avg / client_avg
        print(f"  加速比: {speedup:.1f}x")


@pytest.mark.asyncio
async def test_concurrent_clients():
    """测试并发客户端"""
    print("\n=== 并发客户端测试 ===")
    results = await run_concurrent_client_test(num_clients=3, queries_per_client=2)

    print(f"\n  总耗时: {results['total_time']:.2f}s")

    for r in results["clients"]:
        status = "✓" if r.success else "✗"
        print(f"  [{status}] {r.method} Q{r.query_no}: {r.latency_seconds:.2f}s")

    if results["errors"]:
        print(f"\n  错误: {results['errors']}")

    success_count = sum(1 for r in results["clients"] if r.success)
    print(f"\n  成功率: {success_count}/{len(results['clients'])}")


@pytest.mark.asyncio
async def test_long_running_stability():
    """测试长时间运行稳定性"""
    print("\n=== 长时间运行稳定性测试 ===")
    results = await test_long_running_client()

    print(f"\n  查询次数: {len(results['queries'])}")
    print(f"  重连次数: {results['disconnects']}")

    success_count = sum(1 for q in results["queries"] if q["success"])
    print(f"  成功率: {success_count}/{len(results['queries'])}")

    if results["errors"]:
        print("\n  错误列表:")
        for e in results["errors"]:
            print(f"    - {e}")


if __name__ == "__main__":
    # 直接运行测试
    async def main():
        print("=" * 60)
        print("Claude SDK Client 稳定性测试")
        print("=" * 60)

        await test_query_latency()
        await test_client_latency()
        await test_compare_latency()
        await test_concurrent_clients()
        await test_long_running_stability()

        print("\n" + "=" * 60)
        print("测试完成")
        print("=" * 60)

    asyncio.run(main())
