from __future__ import annotations

import json
import shlex
import time
from contextlib import nullcontext
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID

import typer
from rich.console import Console

from app.cli.client import ApiClient, ApiClientError
from app.cli.config import CliConfig, CliConfigError, load_config
from app.cli.output import Renderer, compact
from app.evaluation.run_quality_api import RunQualityApiClient, collect_run_quality_report

app = typer.Typer(
    name="truman", help="Operate and inspect Truman World from the terminal.", no_args_is_help=True
)
config_app = typer.Typer(help="Inspect CLI configuration.")
system_app = typer.Typer(help="Inspect API, database, access, and runtime health.")
run_app = typer.Typer(help="Create and control simulation runs.")
world_app = typer.Typer(help="Inspect world snapshots and cost telemetry.")
agent_app = typer.Typer(help="Inspect residents, memories, governance, and economy.")
timeline_app = typer.Typer(help="Query or follow the event timeline.")
director_app = typer.Typer(help="Observe and intervene as the director.")
scenario_app = typer.Typer(help="Discover registered simulation scenarios.")

app.add_typer(config_app, name="config")
app.add_typer(system_app, name="system")
app.add_typer(run_app, name="run")
app.add_typer(world_app, name="world")
app.add_typer(agent_app, name="agent")
app.add_typer(timeline_app, name="timeline")
app.add_typer(director_app, name="director")
app.add_typer(scenario_app, name="scenario")


@dataclass(slots=True)
class Runtime:
    config: CliConfig
    client: ApiClient
    renderer: Renderer


@app.callback()
def root(
    ctx: typer.Context,
    profile: str = typer.Option("default", "--profile", help="Config profile name."),
    base_url: str | None = typer.Option(None, "--base-url", help="Backend API base URL."),
    timeout: float | None = typer.Option(
        None, "--timeout", min=0.1, help="Request timeout in seconds."
    ),
    output: str | None = typer.Option(None, "--output", "-o", help="table, json, or ndjson."),
) -> None:
    try:
        config = load_config(profile=profile, base_url=base_url, timeout=timeout, output=output)
    except CliConfigError as exc:
        raise typer.BadParameter(str(exc)) from exc
    ctx.call_on_close(lambda: ctx.obj.client.close() if ctx.obj else None)
    ctx.obj = Runtime(
        config=config,
        client=ApiClient(
            config.base_url,
            admin_password=config.admin_password,
            timeout=config.timeout,
        ),
        renderer=Renderer(config.output),
    )


def rt(ctx: typer.Context) -> Runtime:
    return ctx.find_root().obj


def _one_match(kind: str, reference: str, matches: list[dict[str, Any]]) -> str:
    if len(matches) == 1:
        return str(matches[0]["id"])
    if not matches:
        raise ApiClientError(f"{kind} not found for reference: {reference}", exit_code=6)
    choices = ", ".join(str(item.get("id")) for item in matches[:5])
    raise ApiClientError(f"Ambiguous {kind} reference '{reference}': {choices}")


def _resolve_run_id(runtime: Runtime, reference: str) -> str:
    """Resolve a UUID, unique short ID prefix, or exact run name."""
    try:
        return str(UUID(reference))
    except ValueError:
        pass
    runs = runtime.client.get("runs")
    normalized = reference.casefold()
    matches = [
        item
        for item in runs
        if str(item.get("id") or "").startswith(reference)
        or str(item.get("name") or "").casefold() == normalized
    ]
    return _one_match("run", reference, matches)


def _resolve_agent_id(runtime: Runtime, run_id: str, reference: str) -> str:
    if reference.startswith(f"{run_id}-"):
        return reference
    agents = runtime.client.get(f"runs/{run_id}/agents").get("agents") or []
    normalized = reference.casefold()
    matches = [
        item
        for item in agents
        if str(item.get("id") or "") == reference
        or str(item.get("config_id") or "").casefold() == normalized
        or str(item.get("name") or "").casefold() == normalized
        or str(item.get("id") or "").endswith(f"-{reference}")
    ]
    return _one_match("agent", reference, matches)


def _resolve_location_id(runtime: Runtime, run_id: str, reference: str | None) -> str | None:
    if reference is None or reference.startswith(f"{run_id}-"):
        return reference
    locations = runtime.client.get(f"runs/{run_id}/world").get("locations") or []
    normalized = reference.casefold()
    matches = [
        item
        for item in locations
        if str(item.get("id") or "") == reference
        or str(item.get("name") or "").casefold() == normalized
        or str(item.get("location_type") or "").casefold() == normalized
        or str(item.get("id") or "").endswith(f"-{reference}")
    ]
    return _one_match("location", reference, matches)


def _resolve_directive_id(runtime: Runtime, run_id: str, reference: str) -> str:
    payload = runtime.client.get(f"runs/{run_id}/director/directives", params={"limit": 200})
    directives = payload.get("directives") or []
    matches = [
        directive
        for directive in directives
        if str(directive.get("id") or "") == reference
        or str(directive.get("id") or "").startswith(reference)
    ]
    return _one_match("director directive", reference, matches)


class DirectorEventType(StrEnum):
    activity = "activity"
    shutdown = "shutdown"
    broadcast = "broadcast"
    weather_change = "weather_change"
    power_outage = "power_outage"


@config_app.command("show")
def config_show(ctx: typer.Context) -> None:
    runtime = rt(ctx)
    runtime.renderer.key_values(
        {
            "profile": runtime.config.profile,
            "base_url": runtime.config.base_url,
            "timeout": runtime.config.timeout,
            "output": runtime.config.output,
            "config_path": runtime.config.config_path,
            "admin_password": "configured" if runtime.config.admin_password else "not configured",
        },
        title="CLI configuration",
    )


@app.command("health")
def health(ctx: typer.Context) -> None:
    rt(ctx).renderer.data(rt(ctx).client.get("health"))


@app.command("ready")
def ready(ctx: typer.Context) -> None:
    rt(ctx).renderer.data(rt(ctx).client.get("ready"))


@app.command("doctor")
def doctor(ctx: typer.Context) -> None:
    runtime = rt(ctx)
    checks: list[dict[str, Any]] = []
    for name, path in (("api", "health"), ("database", "ready"), ("access", "system/access")):
        try:
            payload = runtime.client.get(path)
            checks.append({"check": name, "status": "ok", "detail": payload})
        except ApiClientError as exc:
            checks.append({"check": name, "status": "failed", "detail": str(exc)})
    try:
        runs = runtime.client.get("runs")
        running = [item for item in runs if item.get("status") == "running"]
        checks.append(
            {
                "check": "runs",
                "status": "ok",
                "detail": f"{len(runs)} total, {len(running)} running",
            }
        )
    except ApiClientError as exc:
        checks.append({"check": "runs", "status": "failed", "detail": str(exc)})
    runtime.renderer.rows(
        checks,
        (("check", "Check"), ("status", "Status"), ("detail", "Detail")),
        title="Truman World doctor",
    )
    if any(item["status"] == "failed" for item in checks):
        raise typer.Exit(1)


PLAY_HELP = """Commands:
  look                  show the world and latest story
  people                list residents and movement
  inspect <resident>    open a resident dossier
  step [count]          advance an exact number of ticks
  broadcast <message>   inject a town-wide broadcast
  directives            show director commands and execution status
  start | pause         control real-time simulation
  cost                  show token and cost telemetry
  help                  show this guide
  quit                  leave the console (does not change run state)
"""


@app.command("play")
def play(
    ctx: typer.Context,
    run_id: str,
    commands: list[str] | None = typer.Option(
        None,
        "--execute",
        "-e",
        help="Execute a play command and exit; repeat for a scripted session.",
    ),
) -> None:
    """Enter a world-focused director console."""
    runtime = rt(ctx)
    run_id = _resolve_run_id(runtime, run_id)
    _play_header(runtime, run_id)
    if commands:
        for command in commands:
            if not _execute_play_command(ctx, run_id, command, refresh_header=False):
                break
        return

    runtime.renderer.console.print(PLAY_HELP)
    while True:
        try:
            command = runtime.renderer.console.input("[bold cyan]town ›[/] ")
        except (EOFError, KeyboardInterrupt):
            runtime.renderer.console.print()
            return
        if not _execute_play_command(ctx, run_id, command):
            return


def _play_header(runtime: Runtime, run_id: str) -> None:
    run = runtime.client.get(f"runs/{run_id}")
    pulse = runtime.client.get(f"runs/{run_id}/world/pulse")
    clock = pulse.get("world_clock") or {}
    runtime.renderer.key_values(
        {
            "world": run.get("name"),
            "status": run.get("status"),
            "tick": run.get("current_tick"),
            "time": clock.get("display") or clock.get("iso") or "—",
            "tokens": _total_tokens(pulse),
            "cost_usd": _total_cost(pulse) if _total_cost(pulse) is not None else "unavailable",
            "run_ref": run_id[:8],
        },
        title="Truman World",
    )


def _play_look(runtime: Runtime, run_id: str, *, include_header: bool = True) -> None:
    if include_header:
        _play_header(runtime, run_id)
    payload = runtime.client.get(
        f"runs/{run_id}/timeline",
        params={"limit": 5, "order_desc": True},
    )
    events = payload.get("events") or []
    if not events:
        runtime.renderer.console.print("[dim]No story events yet.[/dim]")
        return
    runtime.renderer.console.print("[bold]Latest story[/bold]")
    for event in reversed(events):
        runtime.renderer.event(event)


def _execute_play_command(
    ctx: typer.Context,
    run_id: str,
    command: str,
    *,
    refresh_header: bool = True,
) -> bool:
    runtime = rt(ctx)
    try:
        parts = shlex.split(command)
    except ValueError as exc:
        runtime.renderer.console.print(f"[red]Invalid command:[/red] {exc}")
        return True
    if not parts or parts[0] in {"look", "l"}:
        _play_look(runtime, run_id, include_header=refresh_header)
    elif parts[0] in {"people", "p"}:
        agent_list(ctx, run_id)
    elif parts[0] in {"inspect", "i"}:
        if len(parts) != 2:
            runtime.renderer.console.print("[yellow]Usage: inspect <resident>[/yellow]")
        else:
            agent_show(ctx, run_id, parts[1], event_limit=5, memory_limit=5)
    elif parts[0] in {"step", "n"}:
        try:
            count = int(parts[1]) if len(parts) > 1 else 1
        except ValueError:
            runtime.renderer.console.print("[yellow]Usage: step [positive-count][/yellow]")
            return True
        if count < 1:
            runtime.renderer.console.print("[yellow]Step count must be positive.[/yellow]")
        else:
            _run_steps(ctx, run_id, count)
            _play_look(runtime, run_id)
    elif parts[0] == "broadcast":
        message = " ".join(parts[1:]).strip()
        if not message:
            runtime.renderer.console.print("[yellow]Usage: broadcast <message>[/yellow]")
        else:
            director_inject(
                ctx,
                run_id,
                event_type=DirectorEventType.broadcast,
                message=message,
                location_id=None,
                importance=0.5,
                payload=None,
            )
    elif parts[0] in {"directives", "d"}:
        director_directives(ctx, run_id, status=None, agent_id=None, limit=20)
    elif parts[0] == "start":
        _run_action(ctx, run_id, "start")
    elif parts[0] == "pause":
        _run_action(ctx, run_id, "pause")
    elif parts[0] == "cost":
        world_cost(ctx, run_id)
    elif parts[0] in {"help", "?"}:
        runtime.renderer.console.print(PLAY_HELP)
    elif parts[0] in {"quit", "q", "exit"}:
        return False
    else:
        runtime.renderer.console.print(
            f"[yellow]Unknown play command '{parts[0]}'. Type 'help'.[/yellow]"
        )
    return True


@system_app.command("status")
def system_status(ctx: typer.Context) -> None:
    runtime = rt(ctx)
    payload = runtime.client.get("system/overview")
    if runtime.config.output != "table":
        runtime.renderer.data(payload)
        return
    try:
        database_connectivity = runtime.client.get("ready").get("status", "unknown")
    except ApiClientError:
        database_connectivity = "failed"
    components = payload.get("components") or {}
    rows = []
    for name in ("backend", "frontend", "postgres", "total"):
        component = components.get(name) or {}
        status = component.get("status") or "unknown"
        if name == "postgres" and status == "unavailable" and database_connectivity == "ready":
            status = "remote / no local process"
        rows.append(
            {
                "component": name,
                "status": status,
                "rss_mb": round(float(component.get("rss_bytes") or 0) / 1024 / 1024, 1),
                "cpu_percent": component.get("cpu_percent") or 0,
                "process_count": component.get("process_count") or 0,
            }
        )
    runtime.renderer.key_values(
        {"database_connectivity": database_connectivity},
        title="Connectivity",
    )
    runtime.renderer.rows(
        rows,
        (
            ("component", "Component"),
            ("status", "Status"),
            ("rss_mb", "RSS (MB)"),
            ("cpu_percent", "CPU %"),
            ("process_count", "Processes"),
        ),
        title="Local processes",
    )


@system_app.command("access")
def system_access(ctx: typer.Context) -> None:
    rt(ctx).renderer.data(rt(ctx).client.get("system/access"))


@system_app.command("scenarios")
def scenarios(ctx: typer.Context) -> None:
    scenario_list(ctx)


@scenario_app.command("list")
def scenario_list(ctx: typer.Context) -> None:
    runtime = rt(ctx)
    rows = runtime.client.get("scenarios")
    runtime.renderer.rows(
        rows, (("id", "ID"), ("name", "Name"), ("version", "Version")), title="Scenarios"
    )


RUN_COLUMNS = (
    ("short_id", "ID"),
    ("name", "Name"),
    ("status", "Status"),
    ("scenario_type", "Scenario"),
    ("current_tick", "Tick"),
    ("elapsed_seconds", "Elapsed (s)"),
    ("agent_count", "Agents"),
)


@run_app.command("list")
def run_list(ctx: typer.Context) -> None:
    runtime = rt(ctx)
    runs = runtime.client.get("runs")
    rows = [{**run, "short_id": str(run.get("id") or "")[:8]} for run in runs]
    runtime.renderer.rows(rows, RUN_COLUMNS, title="Simulation runs")


@run_app.command("restore-all")
def run_restore_all(ctx: typer.Context) -> None:
    rt(ctx).renderer.data(rt(ctx).client.post("runs/restore-all"))


@run_app.command("create")
def run_create(
    ctx: typer.Context,
    name: str = typer.Option(..., "--name", "-n", help="Run name."),
    scenario: str | None = typer.Option(None, "--scenario", "-s"),
    tick_minutes: int = typer.Option(5, "--tick-minutes", min=1, max=60),
    paused: bool = typer.Option(
        False, "--paused", help="Seed the world without starting the scheduler."
    ),
    seed_demo: bool = typer.Option(True, "--seed-demo/--no-seed-demo"),
) -> None:
    runtime = rt(ctx)
    payload = runtime.client.post(
        "runs",
        json_body={
            "name": name,
            "scenario_type": scenario,
            "tick_minutes": tick_minutes,
            "seed_demo": seed_demo,
            "auto_start": not paused,
        },
    )
    runtime.renderer.key_values(payload, title="Run created")


@run_app.command("show")
def run_show(ctx: typer.Context, run_id: str) -> None:
    runtime = rt(ctx)
    run_id = _resolve_run_id(runtime, run_id)
    runtime.renderer.data(runtime.client.get(f"runs/{run_id}"))


def _run_action(ctx: typer.Context, run_id: str, action: str) -> dict[str, Any]:
    runtime = rt(ctx)
    run_id = _resolve_run_id(runtime, run_id)
    payload = runtime.client.post(f"runs/{run_id}/{action}")
    runtime.renderer.key_values(payload, title=f"Run {action}")
    return payload


@run_app.command("start")
def run_start(ctx: typer.Context, run_id: str) -> None:
    _run_action(ctx, run_id, "start")


@run_app.command("pause")
def run_pause(ctx: typer.Context, run_id: str) -> None:
    _run_action(ctx, run_id, "pause")


@run_app.command("resume")
def run_resume(ctx: typer.Context, run_id: str) -> None:
    _run_action(ctx, run_id, "resume")


@run_app.command("step")
def run_step(
    ctx: typer.Context,
    run_id: str,
    count: int = typer.Option(1, "--count", "-n", min=1),
) -> None:
    """Advance an inactive world by an exact number of ticks."""
    _run_steps(ctx, run_id, count)


def _run_steps(ctx: typer.Context, run_id: str, count: int) -> None:
    runtime = rt(ctx)
    run_id = _resolve_run_id(runtime, run_id)
    run = runtime.client.get(f"runs/{run_id}")
    if run.get("status") == "running":
        raise ApiClientError(
            "Deterministic step requires an inactive world. Pause it first with "
            f"'truman run pause {run_id[:8]}'.",
            exit_code=7,
        )
    status_context = (
        runtime.renderer.console.status(
            f"Tick 1/{count}: running director and actor graphs…", spinner="dots"
        )
        if runtime.config.output == "table"
        else nullcontext()
    )
    results: list[dict[str, Any]] = []
    with status_context as progress:
        for index in range(count):
            if progress is not None:
                progress.update(f"Tick {index + 1}/{count}: running director and actor graphs…")
            results.append(runtime.client.post(f"runs/{run_id}/tick"))
    runtime.renderer.rows(
        results,
        (("tick_no", "Tick"), ("accepted_count", "Accepted"), ("rejected_count", "Rejected")),
        title="Deterministic steps",
    )


@run_app.command("delete")
def run_delete(
    ctx: typer.Context,
    run_id: str,
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip destructive confirmation."),
) -> None:
    runtime = rt(ctx)
    run_id = _resolve_run_id(runtime, run_id)
    if not yes and not typer.confirm(f"Delete run {run_id} and all related data?"):
        raise typer.Abort()
    runtime.renderer.data(runtime.client.delete(f"runs/{run_id}"))


def _total_cost(pulse: dict[str, Any]) -> float | None:
    stats = pulse.get("daily_stats") or {}
    value = float(stats.get("total_cost_usd") or 0.0)
    return None if value == 0 and _total_tokens(pulse) > 0 else value


def _total_tokens(pulse: dict[str, Any]) -> int:
    stats = pulse.get("daily_stats") or {}
    return sum(
        int(stats.get(key) or 0)
        for key in ("total_input_tokens", "total_output_tokens", "total_reasoning_tokens")
    )


@run_app.command("wait")
def run_wait(
    ctx: typer.Context,
    run_id: str,
    until_tick: int | None = typer.Option(None, "--until-tick", min=0),
    until_status: str | None = typer.Option(None, "--until-status"),
    max_cost: float | None = typer.Option(None, "--max-cost", min=0),
    max_tokens: int | None = typer.Option(None, "--max-tokens", min=0),
    poll_interval: float = typer.Option(2.0, "--poll-interval", min=0.2),
    max_seconds: float = typer.Option(3600.0, "--max-seconds", min=0.1),
) -> None:
    if until_tick is None and until_status is None and max_cost is None and max_tokens is None:
        raise typer.BadParameter("Set --until-tick, --until-status, --max-cost, or --max-tokens")
    runtime = rt(ctx)
    run_id = _resolve_run_id(runtime, run_id)
    result = _wait_for_run(
        runtime,
        run_id,
        until_tick=until_tick,
        until_status=until_status,
        max_cost=max_cost,
        max_tokens=max_tokens,
        poll_interval=poll_interval,
        max_seconds=max_seconds,
    )
    runtime.renderer.data(result)


def _wait_for_run(
    runtime: Runtime,
    run_id: str,
    *,
    until_tick: int | None,
    until_status: str | None,
    max_cost: float | None,
    max_tokens: int | None,
    poll_interval: float,
    max_seconds: float,
) -> dict[str, Any]:
    started = time.monotonic()
    status_context = (
        runtime.renderer.console.status("Waiting for world state…", spinner="dots")
        if runtime.config.output == "table"
        else nullcontext()
    )
    with status_context as progress:
        while True:
            run = runtime.client.get(f"runs/{run_id}")
            pulse = runtime.client.get(f"runs/{run_id}/world/pulse")
            cost = _total_cost(pulse)
            tokens = _total_tokens(pulse)
            elapsed = round(time.monotonic() - started)
            if progress is not None:
                progress.update(
                    f"Waiting · tick {run.get('current_tick', '?')} · {tokens:,} tokens · {elapsed}s"
                )
            if max_cost is not None and cost is None and max_tokens is None:
                if run.get("status") == "running":
                    runtime.client.post(f"runs/{run_id}/pause")
                raise ApiClientError(
                    "Provider does not report USD cost; run paused. "
                    "Use --max-tokens as the hard limit."
                )
            reason = None
            if max_cost is not None and cost is not None and cost >= max_cost:
                reason = "cost_limit"
            elif max_tokens is not None and tokens >= max_tokens:
                reason = "token_limit"
            elif until_tick is not None and int(run.get("current_tick") or 0) >= until_tick:
                reason = "tick_reached"
            elif until_status is not None and run.get("status") == until_status:
                reason = "status_reached"
            if reason is not None:
                if reason in {"cost_limit", "token_limit"} and run.get("status") == "running":
                    runtime.client.post(f"runs/{run_id}/pause")
                return {
                    "reason": reason,
                    "run": run,
                    "total_cost_usd": cost,
                    "tokens": tokens,
                }
            if time.monotonic() - started >= max_seconds:
                raise ApiClientError("Wait deadline exceeded", exit_code=9)
            time.sleep(poll_interval)


@world_app.command("show")
def world_show(ctx: typer.Context, run_id: str) -> None:
    runtime = rt(ctx)
    run_id = _resolve_run_id(runtime, run_id)
    payload = runtime.client.get(f"runs/{run_id}/world")
    if runtime.config.output != "table":
        runtime.renderer.data(payload)
        return
    runtime.renderer.key_values(
        {
            "run": (payload.get("run") or {}).get("name"),
            "status": (payload.get("run") or {}).get("status"),
            "tick": (payload.get("run") or {}).get("current_tick"),
            "world_time": (payload.get("world_clock") or {}).get("display"),
            "agents": len(payload.get("agents") or []),
            "locations": len(payload.get("locations") or []),
            "recent_events": len(payload.get("recent_events") or []),
        },
        title="World snapshot",
    )


@world_app.command("pulse")
def world_pulse(ctx: typer.Context, run_id: str) -> None:
    runtime = rt(ctx)
    run_id = _resolve_run_id(runtime, run_id)
    runtime.renderer.data(runtime.client.get(f"runs/{run_id}/world/pulse"))


@world_app.command("cost")
def world_cost(ctx: typer.Context, run_id: str) -> None:
    runtime = rt(ctx)
    run_id = _resolve_run_id(runtime, run_id)
    pulse = runtime.client.get(f"runs/{run_id}/world/pulse")
    stats = pulse.get("daily_stats") or {}
    cost = _total_cost(pulse)
    display_stats = {**stats, "total_cost_usd": cost if cost is not None else "unavailable"}
    runtime.renderer.key_values(
        compact(
            display_stats,
            (
                "llm_provider",
                "llm_model",
                "total_cost_usd",
                "total_input_tokens",
                "total_output_tokens",
                "total_reasoning_tokens",
                "total_cache_read_tokens",
                "total_cache_creation_tokens",
            ),
        ),
        title="LLM usage",
    )


@agent_app.command("list")
def agent_list(ctx: typer.Context, run_id: str) -> None:
    runtime = rt(ctx)
    run_id = _resolve_run_id(runtime, run_id)
    payload = runtime.client.get(f"runs/{run_id}/agents")
    rows = [
        {
            **agent,
            "agent_ref": agent.get("config_id")
            or str(agent.get("id") or "").removeprefix(f"{run_id}-"),
            "location_ref": (
                str(agent.get("current_location_id")).removeprefix(f"{run_id}-")
                if agent.get("current_location_id")
                else "→ "
                + str(
                    (agent.get("movement") or {}).get("to_location_id") or "in transit"
                ).removeprefix(f"{run_id}-")
            ),
        }
        for agent in payload.get("agents") or []
    ]
    runtime.renderer.rows(
        rows,
        (
            ("agent_ref", "Ref"),
            ("name", "Name"),
            ("occupation", "Occupation"),
            ("location_ref", "Location"),
            ("current_goal", "Goal"),
        ),
        title="Residents",
    )


@agent_app.command("show")
def agent_show(
    ctx: typer.Context,
    run_id: str,
    agent_id: str,
    event_limit: int = typer.Option(10, min=1, max=100),
    memory_limit: int = typer.Option(10, min=1, max=100),
) -> None:
    runtime = rt(ctx)
    run_id = _resolve_run_id(runtime, run_id)
    agent_id = _resolve_agent_id(runtime, run_id, agent_id)
    payload = runtime.client.get(
        f"runs/{run_id}/agents/{agent_id}",
        params={"event_limit": event_limit, "memory_limit": memory_limit},
    )
    if runtime.config.output != "table":
        runtime.renderer.data(payload)
        return
    runtime.renderer.key_values(
        compact(
            payload,
            ("agent_id", "name", "occupation", "current_goal", "status", "personality"),
        ),
        title="Resident",
    )
    events = payload.get("recent_events") or []
    if events:
        runtime.renderer.rows(
            events,
            (
                ("tick_no", "Tick"),
                ("event_type", "Event"),
                ("actor_name", "Actor"),
                ("target_name", "Target"),
                ("location_name", "Location"),
            ),
            title="Recent events",
        )
    memories = payload.get("memories") or []
    if memories:
        runtime.renderer.rows(
            memories,
            (
                ("memory_type", "Type"),
                ("importance", "Importance"),
                ("summary", "Summary"),
            ),
            title="Memories",
        )
    relationships = payload.get("relationships") or []
    if relationships:
        runtime.renderer.rows(
            relationships,
            (
                ("other_agent_name", "Resident"),
                ("relation_type", "Relation"),
                ("trust", "Trust"),
                ("affinity", "Affinity"),
            ),
            title="Relationships",
        )


@agent_app.command("economy")
def agent_economy(ctx: typer.Context, run_id: str, agent_id: str) -> None:
    runtime = rt(ctx)
    run_id = _resolve_run_id(runtime, run_id)
    agent_id = _resolve_agent_id(runtime, run_id, agent_id)
    runtime.renderer.data(runtime.client.get(f"runs/{run_id}/agents/{agent_id}/economic-summary"))


@agent_app.command("governance")
def agent_governance(ctx: typer.Context, run_id: str, agent_id: str, limit: int = 20) -> None:
    runtime = rt(ctx)
    run_id = _resolve_run_id(runtime, run_id)
    agent_id = _resolve_agent_id(runtime, run_id, agent_id)
    runtime.renderer.data(
        runtime.client.get(
            f"runs/{run_id}/agents/{agent_id}/governance-records", params={"limit": limit}
        )
    )


@timeline_app.command("list")
def timeline_list(
    ctx: typer.Context,
    run_id: str,
    tick_from: int | None = typer.Option(None, "--tick-from"),
    tick_to: int | None = typer.Option(None, "--tick-to"),
    event_type: str | None = typer.Option(None, "--event-type"),
    agent: str | None = typer.Option(None, "--agent"),
    limit: int = typer.Option(100, min=1, max=1000),
    newest_first: bool = typer.Option(
        True, "--newest-first/--oldest-first", help="Show latest events first by default."
    ),
) -> None:
    runtime = rt(ctx)
    run_id = _resolve_run_id(runtime, run_id)
    agent = _resolve_agent_id(runtime, run_id, agent) if agent else None
    params = {
        key: value
        for key, value in {
            "tick_from": tick_from,
            "tick_to": tick_to,
            "event_type": event_type,
            "agent_id": agent,
            "limit": limit,
            "order_desc": newest_first,
        }.items()
        if value is not None
    }
    payload = runtime.client.get(f"runs/{run_id}/timeline", params=params)
    events = payload.get("events") or []
    if runtime.config.output == "table":
        for event in events:
            runtime.renderer.event(event)
    else:
        runtime.renderer.data(events)


@timeline_app.command("follow")
def timeline_follow(
    ctx: typer.Context,
    run_id: str,
    since_tick: int = typer.Option(0, "--since-tick", min=0),
) -> None:
    runtime = rt(ctx)
    run_id = _resolve_run_id(runtime, run_id)
    try:
        for envelope in runtime.client.stream_events(
            f"runs/{run_id}/events/stream", params={"since_tick": since_tick}
        ):
            data = envelope.get("data")
            runtime.renderer.event(data) if isinstance(data, dict) else runtime.renderer.data(
                envelope
            )
    except KeyboardInterrupt:
        return


@director_app.command("observe")
def director_observe(ctx: typer.Context, run_id: str) -> None:
    runtime = rt(ctx)
    run_id = _resolve_run_id(runtime, run_id)
    runtime.renderer.data(runtime.client.get(f"runs/{run_id}/director/observation"))


@director_app.command("memories")
def director_memories(ctx: typer.Context, run_id: str, limit: int = 100) -> None:
    runtime = rt(ctx)
    run_id = _resolve_run_id(runtime, run_id)
    runtime.renderer.data(
        runtime.client.get(f"runs/{run_id}/director/memories", params={"limit": limit})
    )


@director_app.command("directives")
def director_directives(
    ctx: typer.Context,
    run_id: str,
    status: str | None = typer.Option(None, "--status"),
    agent_id: str | None = typer.Option(None, "--agent"),
    limit: int = typer.Option(100, "--limit", min=1, max=200),
) -> None:
    runtime = rt(ctx)
    run_id = _resolve_run_id(runtime, run_id)
    if agent_id is not None:
        agent_id = _resolve_agent_id(runtime, run_id, agent_id)
    params = {
        key: value
        for key, value in {"status": status, "agent_id": agent_id, "limit": limit}.items()
        if value is not None
    }
    payload = runtime.client.get(f"runs/{run_id}/director/directives", params=params)
    rows = payload.get("directives") or []
    if runtime.config.output == "table":
        rows = [
            {
                **directive,
                "short_id": str(directive.get("id") or "")[:8],
                "effect": (
                    f"{float(directive['effectiveness_score']):.2f}"
                    if directive.get("effectiveness_score") is not None
                    else directive.get("effect_status") or "pending"
                ),
            }
            for directive in rows
        ]
    runtime.renderer.rows(
        rows,
        (
            ("short_id", "ID"),
            ("issued_tick", "Tick"),
            ("target_agent_name", "Actor"),
            ("objective", "Objective"),
            ("status", "Status"),
            ("effect", "Effect"),
            ("failure_reason", "Reason"),
        ),
        title="Director directives",
    )


@director_app.command("directive")
def director_directive(ctx: typer.Context, run_id: str, directive_id: str) -> None:
    runtime = rt(ctx)
    run_id = _resolve_run_id(runtime, run_id)
    directive_id = _resolve_directive_id(runtime, run_id, directive_id)
    runtime.renderer.data(runtime.client.get(f"runs/{run_id}/director/directives/{directive_id}"))


@director_app.command("cases")
def director_cases(
    ctx: typer.Context, run_id: str, status: str | None = None, limit: int = 100
) -> None:
    runtime = rt(ctx)
    run_id = _resolve_run_id(runtime, run_id)
    params = {
        key: value for key, value in {"status": status, "limit": limit}.items() if value is not None
    }
    runtime.renderer.data(runtime.client.get(f"runs/{run_id}/director/cases", params=params))


@director_app.command("restrictions")
def director_restrictions(
    ctx: typer.Context, run_id: str, status: str | None = None, limit: int = 100
) -> None:
    runtime = rt(ctx)
    run_id = _resolve_run_id(runtime, run_id)
    params = {
        key: value for key, value in {"status": status, "limit": limit}.items() if value is not None
    }
    runtime.renderer.data(runtime.client.get(f"runs/{run_id}/director/restrictions", params=params))


@director_app.command("inject")
def director_inject(
    ctx: typer.Context,
    run_id: str,
    event_type: DirectorEventType = typer.Option(
        ...,
        "--type",
        help="activity, shutdown, broadcast, weather_change, or power_outage.",
    ),
    message: str | None = typer.Option(None, "--message"),
    location_id: str | None = typer.Option(None, "--location"),
    importance: float = typer.Option(0.5, min=0, max=1),
    payload: str | None = typer.Option(None, "--payload", help="Additional JSON object."),
) -> None:
    runtime = rt(ctx)
    run_id = _resolve_run_id(runtime, run_id)
    location_id = _resolve_location_id(runtime, run_id, location_id)
    try:
        event_payload = json.loads(payload) if payload else {}
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"Invalid --payload JSON: {exc}") from exc
    if not isinstance(event_payload, dict):
        raise typer.BadParameter("--payload must be a JSON object")
    if message:
        event_payload["message"] = message
    runtime.renderer.data(
        runtime.client.post(
            f"runs/{run_id}/director/events",
            json_body={
                "event_type": event_type.value,
                "payload": event_payload,
                "location_id": location_id,
                "importance": importance,
            },
        )
    )


@app.command("evaluate")
def evaluate(
    ctx: typer.Context,
    run_id: str,
    ticks: int = typer.Option(0, "--ticks", min=0),
    output_file: Path | None = typer.Option(None, "--output-file"),
) -> None:
    runtime = rt(ctx)
    run_id = _resolve_run_id(runtime, run_id)
    client = RunQualityApiClient(
        runtime.config.base_url,
        admin_password=runtime.config.admin_password,
        timeout=runtime.config.timeout,
    )
    try:
        report = collect_run_quality_report(client, run_id, ticks=ticks)
    except (RuntimeError, ValueError) as exc:
        raise ApiClientError(f"Evaluation failed: {exc}") from exc
    if output_file:
        output_file.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    runtime.renderer.data(report)


def main() -> None:
    try:
        app()
    except ApiClientError as exc:
        Console(stderr=True).print(f"[red]error:[/red] {exc}")
        raise SystemExit(exc.exit_code) from exc
    except typer.Exit as exc:
        raise SystemExit(exc.exit_code) from exc
    except typer.Abort as exc:
        raise SystemExit(130) from exc
    except KeyboardInterrupt as exc:
        raise SystemExit(130) from exc


if __name__ == "__main__":
    main()
