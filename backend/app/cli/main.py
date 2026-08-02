from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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

app.add_typer(config_app, name="config")
app.add_typer(system_app, name="system")
app.add_typer(run_app, name="run")
app.add_typer(world_app, name="world")
app.add_typer(agent_app, name="agent")
app.add_typer(timeline_app, name="timeline")
app.add_typer(director_app, name="director")


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


@system_app.command("status")
def system_status(ctx: typer.Context) -> None:
    rt(ctx).renderer.data(rt(ctx).client.get("system/overview"))


@system_app.command("access")
def system_access(ctx: typer.Context) -> None:
    rt(ctx).renderer.data(rt(ctx).client.get("system/access"))


@system_app.command("scenarios")
def scenarios(ctx: typer.Context) -> None:
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
    rt(ctx).renderer.data(rt(ctx).client.get(f"runs/{run_id}"))


def _run_action(ctx: typer.Context, run_id: str, action: str) -> dict[str, Any]:
    runtime = rt(ctx)
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


@run_app.command("tick")
def run_tick(
    ctx: typer.Context,
    run_id: str,
    count: int = typer.Option(1, "--count", "-n", min=1),
) -> None:
    runtime = rt(ctx)
    results = [runtime.client.post(f"runs/{run_id}/tick") for _ in range(count)]
    runtime.renderer.rows(
        results,
        (("tick_no", "Tick"), ("accepted_count", "Accepted"), ("rejected_count", "Rejected")),
        title="Manual ticks",
    )


@run_app.command("delete")
def run_delete(
    ctx: typer.Context,
    run_id: str,
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip destructive confirmation."),
) -> None:
    if not yes and not typer.confirm(f"Delete run {run_id} and all related data?"):
        raise typer.Abort()
    rt(ctx).renderer.data(rt(ctx).client.delete(f"runs/{run_id}"))


def _total_cost(pulse: dict[str, Any]) -> float:
    return float((pulse.get("daily_stats") or {}).get("total_cost_usd") or 0.0)


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
    started = time.monotonic()
    while True:
        run = runtime.client.get(f"runs/{run_id}")
        pulse = runtime.client.get(f"runs/{run_id}/world/pulse")
        cost = _total_cost(pulse)
        tokens = _total_tokens(pulse)
        if max_cost is not None and cost >= max_cost:
            if run.get("status") == "running":
                runtime.client.post(f"runs/{run_id}/pause")
            runtime.renderer.data(
                {"reason": "cost_limit", "run": run, "total_cost_usd": cost, "tokens": tokens}
            )
            return
        if max_tokens is not None and tokens >= max_tokens:
            if run.get("status") == "running":
                runtime.client.post(f"runs/{run_id}/pause")
            runtime.renderer.data(
                {"reason": "token_limit", "run": run, "total_cost_usd": cost, "tokens": tokens}
            )
            return
        if until_tick is not None and int(run.get("current_tick") or 0) >= until_tick:
            runtime.renderer.data(
                {"reason": "tick_reached", "run": run, "total_cost_usd": cost, "tokens": tokens}
            )
            return
        if until_status is not None and run.get("status") == until_status:
            runtime.renderer.data(
                {"reason": "status_reached", "run": run, "total_cost_usd": cost, "tokens": tokens}
            )
            return
        if time.monotonic() - started >= max_seconds:
            raise ApiClientError("Wait deadline exceeded", exit_code=9)
        time.sleep(poll_interval)


@world_app.command("show")
def world_show(ctx: typer.Context, run_id: str) -> None:
    runtime = rt(ctx)
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
    rt(ctx).renderer.data(rt(ctx).client.get(f"runs/{run_id}/world/pulse"))


@world_app.command("cost")
def world_cost(ctx: typer.Context, run_id: str) -> None:
    runtime = rt(ctx)
    pulse = runtime.client.get(f"runs/{run_id}/world/pulse")
    stats = pulse.get("daily_stats") or {}
    runtime.renderer.key_values(
        compact(
            stats,
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
    payload = runtime.client.get(f"runs/{run_id}/agents")
    runtime.renderer.rows(
        payload.get("agents") or [],
        (
            ("id", "ID"),
            ("name", "Name"),
            ("occupation", "Occupation"),
            ("current_location_id", "Location"),
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
    rt(ctx).renderer.data(
        rt(ctx).client.get(
            f"runs/{run_id}/agents/{agent_id}",
            params={"event_limit": event_limit, "memory_limit": memory_limit},
        )
    )


@agent_app.command("economy")
def agent_economy(ctx: typer.Context, run_id: str, agent_id: str) -> None:
    rt(ctx).renderer.data(rt(ctx).client.get(f"runs/{run_id}/agents/{agent_id}/economic-summary"))


@agent_app.command("governance")
def agent_governance(ctx: typer.Context, run_id: str, agent_id: str, limit: int = 20) -> None:
    rt(ctx).renderer.data(
        rt(ctx).client.get(
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
    newest_first: bool = typer.Option(False, "--newest-first"),
) -> None:
    runtime = rt(ctx)
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
    rt(ctx).renderer.data(rt(ctx).client.get(f"runs/{run_id}/director/observation"))


@director_app.command("memories")
def director_memories(ctx: typer.Context, run_id: str, limit: int = 100) -> None:
    rt(ctx).renderer.data(
        rt(ctx).client.get(f"runs/{run_id}/director/memories", params={"limit": limit})
    )


@director_app.command("cases")
def director_cases(
    ctx: typer.Context, run_id: str, status: str | None = None, limit: int = 100
) -> None:
    params = {
        key: value for key, value in {"status": status, "limit": limit}.items() if value is not None
    }
    rt(ctx).renderer.data(rt(ctx).client.get(f"runs/{run_id}/director/cases", params=params))


@director_app.command("restrictions")
def director_restrictions(
    ctx: typer.Context, run_id: str, status: str | None = None, limit: int = 100
) -> None:
    params = {
        key: value for key, value in {"status": status, "limit": limit}.items() if value is not None
    }
    rt(ctx).renderer.data(rt(ctx).client.get(f"runs/{run_id}/director/restrictions", params=params))


@director_app.command("inject")
def director_inject(
    ctx: typer.Context,
    run_id: str,
    event_type: str = typer.Option(..., "--type"),
    message: str | None = typer.Option(None, "--message"),
    location_id: str | None = typer.Option(None, "--location"),
    importance: float = typer.Option(0.5, min=0, max=1),
    payload: str | None = typer.Option(None, "--payload", help="Additional JSON object."),
) -> None:
    try:
        event_payload = json.loads(payload) if payload else {}
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"Invalid --payload JSON: {exc}") from exc
    if not isinstance(event_payload, dict):
        raise typer.BadParameter("--payload must be a JSON object")
    if message:
        event_payload["message"] = message
    rt(ctx).renderer.data(
        rt(ctx).client.post(
            f"runs/{run_id}/director/events",
            json_body={
                "event_type": event_type,
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
