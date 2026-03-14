"""Simple scheduler for automatic tick advancement."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from app.infra.logging import debug, error, info, warning
from app.infra.settings import get_settings


@dataclass
class ScheduledRun:
    run_id: str
    interval_seconds: float
    callback: Callable[[str], Awaitable[None]]
    task: asyncio.Task | None = None
    callback_task: asyncio.Task | None = None
    consecutive_errors: int = 0
    stop_requested: bool = False
    on_max_errors: Callable[[str], Awaitable[None]] | None = field(default=None, repr=False)


class SimulationScheduler:
    """Manages automatic tick advancement for runs."""

    def __init__(self) -> None:
        self._scheduled: dict[str, ScheduledRun] = {}
        self._lock = asyncio.Lock()

    async def start_run(
        self,
        run_id: str,
        interval_seconds: float,
        callback: Callable[[str], Awaitable[None]],
        on_max_errors: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        """Start automatic tick advancement for a run."""
        async with self._lock:
            if run_id in self._scheduled:
                existing = self._scheduled[run_id]
                info(
                    f"Run {run_id} already scheduled (interval={existing.interval_seconds}s), restarting"
                )
                await self._stop_run_locked(run_id)

            info(
                f"Starting scheduler for run {run_id} with interval={interval_seconds}s, active_runs={len(self._scheduled)}"
            )
            scheduled = ScheduledRun(
                run_id=run_id,
                interval_seconds=interval_seconds,
                callback=callback,
                on_max_errors=on_max_errors,
            )
            scheduled.task = asyncio.create_task(
                self._tick_loop(run_id, interval_seconds, callback, on_max_errors),
                name=f"tick-loop-{run_id}",
            )
            self._scheduled[run_id] = scheduled

    async def stop_run(self, run_id: str) -> None:
        """Stop automatic tick advancement for a run."""
        async with self._lock:
            await self._stop_run_locked(run_id)

    async def stop_all(self) -> None:
        """Stop all scheduled runs."""
        async with self._lock:
            run_ids = list(self._scheduled)
            for run_id in run_ids:
                await self._stop_run_locked(run_id)

    async def _stop_run_locked(self, run_id: str) -> None:
        """Internal method to stop a run (must hold lock)."""
        scheduled = self._scheduled.pop(run_id, None)
        if scheduled is not None:
            scheduled.stop_requested = True
        if scheduled and scheduled.callback_task and not scheduled.callback_task.done():
            scheduled.callback_task.cancel()
        if scheduled and scheduled.task:
            info(f"Stopping scheduler for run {run_id}, remaining_runs={len(self._scheduled)}")
            scheduled.task.cancel()
            # Await the task to properly handle cancellation
            # Use timeout to avoid blocking forever if LLM call is stuck
            try:
                await asyncio.wait_for(asyncio.shield(scheduled.task), timeout=2.0)
            except TimeoutError:
                warning(f"Task for run {run_id} did not cancel within 2s, continuing")
            except asyncio.CancelledError:
                pass
            except RuntimeError as e:
                if "cancel scope" not in str(e).lower():
                    error(f"Unexpected error stopping run {run_id}: {e}")

    def is_running(self, run_id: str) -> bool:
        """Check if a run is being automatically scheduled."""
        return run_id in self._scheduled

    def running_count(self) -> int:
        """Return the number of currently scheduled runs."""
        return len(self._scheduled)

    async def _tick_loop(
        self,
        run_id: str,
        interval_seconds: float,
        callback: Callable[[str], Awaitable[None]],
        on_max_errors: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        """Main loop for automatic tick advancement."""
        max_errors = get_settings().scheduler_max_consecutive_errors
        consecutive_errors = 0
        tick_count = 0
        while True:
            try:
                await asyncio.sleep(interval_seconds)
                scheduled = self._scheduled.get(run_id)
                if scheduled is None or scheduled.stop_requested:
                    info(f"Tick loop stopping before next tick for run {run_id}")
                    break
                tick_count += 1
                debug(f"Auto-advancing tick #{tick_count} for run {run_id}")

                # Run callback in a separate task to isolate errors and cancellation
                # Use shield to protect from external cancellation during database operations
                task = asyncio.create_task(callback(run_id))
                scheduled.callback_task = task
                try:
                    await task
                    consecutive_errors = 0  # 成功清零错误计数
                    debug(f"Tick #{tick_count} completed successfully for run {run_id}")
                except asyncio.CancelledError:
                    # Task was cancelled, clean up
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    info(f"Tick callback cancelled for run {run_id} (tick #{tick_count})")
                    raise
                except RuntimeError as e:
                    # Handle claude_agent_sdk anyio cancel scope errors
                    if "cancel scope" in str(e).lower():
                        debug(f"Tick callback cancel scope error for run {run_id}: {e}")
                    else:
                        error(f"RuntimeError in tick callback for run {run_id}: {e}")
                        consecutive_errors += 1
                except Exception as e:
                    error(f"Error in tick callback for run {run_id}: {e}")
                    consecutive_errors += 1
                    # Continue running despite callback errors
                finally:
                    if scheduled.callback_task is task:
                        scheduled.callback_task = None

                # 连续失败超过阈値时自动暂停
                if max_errors > 0 and consecutive_errors >= max_errors:
                    warning(
                        f"Run {run_id} has failed {consecutive_errors} consecutive ticks "
                        f"(max={max_errors}), auto-pausing"
                    )
                    # 移除调度登记，避免锁死锁
                    self._scheduled.pop(run_id, None)
                    if on_max_errors is not None:
                        try:
                            await on_max_errors(run_id)
                        except Exception as cb_err:
                            error(f"on_max_errors callback failed for run {run_id}: {cb_err}")
                    break

            except asyncio.CancelledError:
                info(f"Tick loop cancelled for run {run_id} after {tick_count} ticks")
                break
            except Exception as e:
                error(f"Unexpected error in tick loop for run {run_id}: {e}")
                # Continue running despite errors


# Global scheduler instance
_scheduler: SimulationScheduler | None = None


def get_scheduler() -> SimulationScheduler:
    """Get or create the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = SimulationScheduler()
    return _scheduler
