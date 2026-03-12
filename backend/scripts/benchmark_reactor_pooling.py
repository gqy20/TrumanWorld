from __future__ import annotations

import argparse
import json
import re
import statistics
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass
class TickSample:
    tick_no: int
    duration_seconds: float


def _request_json(method: str, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8")
            if not body:
                return {}
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        msg = f"{method} {url} failed with HTTP {exc.code}: {body}"
        raise RuntimeError(msg) from exc


def _request_text(url: str) -> str:
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8")


def _extract_metric_value(metrics_text: str, metric_name: str) -> float | None:
    pattern = re.compile(rf"^{re.escape(metric_name)}(?:\{{[^}}]*\}})?\s+([0-9eE+.\-]+)$", re.M)
    matches = pattern.findall(metrics_text)
    if not matches:
        return None
    return float(matches[-1])


def _extract_histogram_count(metrics_text: str, metric_name: str, mode: str) -> float | None:
    pattern = re.compile(
        rf'^{re.escape(metric_name)}_count\{{mode="{re.escape(mode)}"\}}\s+([0-9eE+.\-]+)$',
        re.M,
    )
    matches = pattern.findall(metrics_text)
    if not matches:
        return None
    return float(matches[-1])


def _extract_histogram_sum(metrics_text: str, metric_name: str, mode: str) -> float | None:
    pattern = re.compile(
        rf'^{re.escape(metric_name)}_sum\{{mode="{re.escape(mode)}"\}}\s+([0-9eE+.\-]+)$',
        re.M,
    )
    matches = pattern.findall(metrics_text)
    if not matches:
        return None
    return float(matches[-1])


def _build_base_url(raw_base_url: str) -> str:
    return raw_base_url.rstrip("/")


def _api_url(base_url: str, path: str) -> str:
    return f"{base_url}{path}"


def run_benchmark(
    *,
    base_url: str,
    run_name: str,
    ticks: int,
    seed_demo: bool,
) -> int:
    metrics_before = _request_text(_api_url(base_url, "/metrics"))
    pool_enabled = _extract_metric_value(metrics_before, "trumanworld_claude_reactor_pool_enabled")
    pool_size_before = _extract_metric_value(metrics_before, "trumanworld_claude_reactor_pool_size")
    pool_active_before = _extract_metric_value(
        metrics_before, "trumanworld_claude_reactor_pool_active"
    )
    tick_count_before = _extract_histogram_count(
        metrics_before, "trumanworld_tick_duration_seconds", "inline"
    )
    tick_sum_before = _extract_histogram_sum(
        metrics_before, "trumanworld_tick_duration_seconds", "inline"
    )

    run = _request_json(
        "POST",
        _api_url(base_url, "/runs"),
        {"name": run_name, "seed_demo": seed_demo},
    )
    run_id = run["id"]

    samples: list[TickSample] = []
    try:
        _request_json("POST", _api_url(base_url, f"/runs/{run_id}/pause"))

        for _ in range(ticks):
            started_at = time.perf_counter()
            tick = _request_json("POST", _api_url(base_url, f"/runs/{run_id}/tick"))
            elapsed = time.perf_counter() - started_at
            samples.append(TickSample(tick_no=int(tick["tick_no"]), duration_seconds=elapsed))

        metrics_after = _request_text(_api_url(base_url, "/metrics"))
    finally:
        try:
            _request_json("DELETE", _api_url(base_url, f"/runs/{run_id}"))
        except Exception:
            pass

    pool_size_after = _extract_metric_value(metrics_after, "trumanworld_claude_reactor_pool_size")
    pool_active_after = _extract_metric_value(metrics_after, "trumanworld_claude_reactor_pool_active")
    tick_count_after = _extract_histogram_count(
        metrics_after, "trumanworld_tick_duration_seconds", "inline"
    )
    tick_sum_after = _extract_histogram_sum(
        metrics_after, "trumanworld_tick_duration_seconds", "inline"
    )

    durations = [sample.duration_seconds for sample in samples]
    avg_duration = statistics.mean(durations) if durations else 0.0
    median_duration = statistics.median(durations) if durations else 0.0
    p95_duration = (
        statistics.quantiles(durations, n=20, method="inclusive")[18] if len(durations) >= 2 else avg_duration
    )

    histogram_count_delta = (
        (tick_count_after or 0.0) - (tick_count_before or 0.0)
        if tick_count_before is not None and tick_count_after is not None
        else None
    )
    histogram_sum_delta = (
        (tick_sum_after or 0.0) - (tick_sum_before or 0.0)
        if tick_sum_before is not None and tick_sum_after is not None
        else None
    )

    print("Reactor Pool Benchmark")
    print(f"base_url: {base_url}")
    print(f"run_id: {run_id}")
    print(f"ticks: {ticks}")
    print(f"seed_demo: {seed_demo}")
    print(f"reactor_pool_enabled_metric: {int(pool_enabled or 0)}")
    print(f"pool_size_before: {pool_size_before or 0:.0f}")
    print(f"pool_size_after: {pool_size_after or 0:.0f}")
    print(f"pool_active_before: {pool_active_before or 0:.0f}")
    print(f"pool_active_after: {pool_active_after or 0:.0f}")
    print(f"avg_tick_seconds_client: {avg_duration:.4f}")
    print(f"median_tick_seconds_client: {median_duration:.4f}")
    print(f"p95_tick_seconds_client: {p95_duration:.4f}")
    if histogram_count_delta is not None:
        print(f"tick_histogram_count_delta: {histogram_count_delta:.0f}")
    if histogram_sum_delta is not None:
        print(f"tick_histogram_sum_delta: {histogram_sum_delta:.4f}")

    print("per_tick:")
    for sample in samples:
        print(f"  tick={sample.tick_no} duration_seconds={sample.duration_seconds:.4f}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark inline run ticks with reactor pooling on/off."
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:18080/api",
        help="Backend API base URL, default: http://127.0.0.1:18080/api",
    )
    parser.add_argument(
        "--run-name",
        default="reactor-pool-benchmark",
        help="Name prefix for the temporary benchmark run.",
    )
    parser.add_argument(
        "--ticks",
        type=int,
        default=10,
        help="Number of manual ticks to execute, default: 10",
    )
    parser.add_argument(
        "--seed-demo",
        action="store_true",
        help="Create the benchmark run with seeded demo data.",
    )
    args = parser.parse_args()

    return run_benchmark(
        base_url=_build_base_url(args.base_url),
        run_name=args.run_name,
        ticks=args.ticks,
        seed_demo=args.seed_demo,
    )


if __name__ == "__main__":
    raise SystemExit(main())
