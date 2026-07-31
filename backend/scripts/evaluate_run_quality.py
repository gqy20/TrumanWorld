#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from app.evaluation.run_quality_api import RunQualityApiClient, collect_run_quality_report


def non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return parsed


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect a deterministic quality report for an existing TrumanWorld run."
    )
    parser.add_argument("--run-id", required=True, help="Run UUID to evaluate")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:18080/api",
        help="Backend API base URL",
    )
    parser.add_argument(
        "--ticks",
        type=non_negative_int,
        default=0,
        help="Ticks to advance before producing the report; zero is read-only",
    )
    parser.add_argument(
        "--timeline-page-size",
        type=positive_int,
        default=500,
        help="Timeline events requested per API page",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="HTTP timeout per API request in seconds",
    )
    parser.add_argument("--output", type=Path, help="Optional path for the JSON report")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    client = RunQualityApiClient(
        args.base_url,
        admin_password=os.getenv("TRUMANWORLD_DEMO_ADMIN_PASSWORD"),
        timeline_page_size=args.timeline_page_size,
        timeout=args.timeout,
    )
    try:
        report = collect_run_quality_report(client, args.run_id, ticks=args.ticks)
    except (RuntimeError, ValueError) as exc:
        print(f"evaluation failed: {exc}", file=sys.stderr)
        return 1

    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(f"{rendered}\n", encoding="utf-8")
        print(f"report written to {args.output}", file=sys.stderr)
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
