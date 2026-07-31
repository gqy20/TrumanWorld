from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from app.api.auth import DEMO_ADMIN_HEADER
from app.evaluation.run_quality import build_run_quality_report


class RunQualityApiClient:
    """Small standard-library client for collecting run quality inputs."""

    def __init__(
        self,
        base_url: str,
        *,
        admin_password: str | None = None,
        timeline_page_size: int = 500,
        timeout: float = 120.0,
        open_url: Callable[..., Any] = urlopen,
    ) -> None:
        if timeline_page_size < 1:
            raise ValueError("timeline_page_size must be positive")
        self.base_url = base_url.rstrip("/")
        self.admin_password = admin_password
        self.timeline_page_size = timeline_page_size
        self.timeout = timeout
        self._open_url = open_url

    def _request_json(
        self,
        path: str,
        *,
        method: str = "GET",
        query: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        if query:
            url = f"{url}?{urlencode(query)}"
        headers = {"Accept": "application/json"}
        if self.admin_password:
            headers[DEMO_ADMIN_HEADER] = self.admin_password
        request = Request(
            url,
            data=b"" if method != "GET" else None,
            headers=headers,
            method=method,
        )
        try:
            with self._open_url(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode())
        except HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise RuntimeError(f"API request failed ({exc.code}) for {url}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"API request failed for {url}: {exc.reason}") from exc
        if not isinstance(payload, dict):
            raise RuntimeError(f"API returned a non-object response for {url}")
        return payload

    def get_run(self, run_id: str) -> dict[str, Any]:
        return self._request_json(f"runs/{quote(run_id, safe='')}")

    def get_director_observation(self, run_id: str) -> dict[str, Any]:
        return self._request_json(f"runs/{quote(run_id, safe='')}/director/observation")

    def advance_tick(self, run_id: str) -> dict[str, Any]:
        return self._request_json(f"runs/{quote(run_id, safe='')}/tick", method="POST")

    def list_timeline_events(self, run_id: str) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        offset = 0
        while True:
            payload = self._request_json(
                f"runs/{quote(run_id, safe='')}/timeline",
                query={
                    "limit": self.timeline_page_size,
                    "offset": offset,
                    "order_desc": "false",
                },
            )
            page = payload.get("events") or []
            if not isinstance(page, list):
                raise RuntimeError("Timeline response field 'events' must be a list")
            events.extend(item for item in page if isinstance(item, dict))
            total = int(payload.get("total") or 0)
            if not page or len(events) >= total:
                break
            offset += len(page)
        return events

    def get_memory_snapshot(self, run_id: str, *, memory_limit: int = 100) -> dict[str, Any]:
        payload = self._request_json(
            f"runs/{quote(run_id, safe='')}/agents/memory-counts",
            query={"memory_limit": memory_limit},
        )
        observed_counts = payload.get("observed_counts") or {}
        capped_agent_ids = payload.get("capped_agent_ids") or []
        return {
            "tick_no": int(payload.get("tick_no") or 0),
            "observed_counts": (
                {str(agent_id): int(count) for agent_id, count in observed_counts.items()}
                if isinstance(observed_counts, Mapping)
                else {}
            ),
            "capped_agent_ids": (
                sorted(str(agent_id) for agent_id in capped_agent_ids)
                if isinstance(capped_agent_ids, list)
                else []
            ),
        }


def collect_run_quality_report(
    client: Any,
    run_id: str,
    *,
    ticks: int = 0,
    clock: Callable[[], float] = time.perf_counter,
) -> dict[str, Any]:
    """Collect API snapshots, optionally advance the run, and build a quality report."""
    if ticks < 0:
        raise ValueError("ticks must be non-negative")

    run = client.get_run(run_id)
    if ticks and run.get("status") == "running":
        raise ValueError("pause the run before advancing evaluation ticks")
    observation = client.get_director_observation(run_id)
    memory_snapshots = [client.get_memory_snapshot(run_id)]
    tick_samples: list[dict[str, Any]] = [
        {
            "tick_no": int(run.get("current_tick") or 0),
            "subject_alert_score": observation.get("subject_alert_score"),
        }
    ]

    for _ in range(ticks):
        started_at = clock()
        tick_result = client.advance_tick(run_id)
        duration_seconds = clock() - started_at
        observation = client.get_director_observation(run_id)
        tick_samples.append(
            {
                "tick_no": int(tick_result.get("tick_no") or 0),
                "duration_seconds": duration_seconds,
                "accepted_count": int(tick_result.get("accepted_count") or 0),
                "rejected_count": int(tick_result.get("rejected_count") or 0),
                "subject_alert_score": observation.get("subject_alert_score"),
            }
        )

    if ticks:
        run = client.get_run(run_id)
        memory_snapshots.append(client.get_memory_snapshot(run_id))
    timeline_events = client.list_timeline_events(run_id)
    return build_run_quality_report(
        run=run,
        timeline_events=timeline_events,
        director_observation=observation,
        tick_samples=tick_samples,
        memory_snapshots=memory_snapshots,
    )
