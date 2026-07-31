from __future__ import annotations

import json
from collections.abc import Iterator

import pytest

from app.evaluation.run_quality_api import RunQualityApiClient, collect_run_quality_report


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode()


def test_api_client_paginates_timeline_and_sends_admin_header() -> None:
    requests = []

    def open_url(request, *, timeout: float):
        requests.append((request, timeout))
        if "offset=0" in request.full_url:
            return FakeResponse(
                {
                    "total": 3,
                    "events": [
                        {"id": "1", "tick_no": 1, "event_type": "move"},
                        {"id": "2", "tick_no": 2, "event_type": "talk"},
                    ],
                }
            )
        return FakeResponse(
            {
                "total": 3,
                "events": [{"id": "3", "tick_no": 3, "event_type": "rest"}],
            }
        )

    client = RunQualityApiClient(
        "http://localhost:18080/api/",
        admin_password="secret",
        timeline_page_size=2,
        timeout=15.0,
        open_url=open_url,
    )

    events = client.list_timeline_events("run id")

    assert [event["id"] for event in events] == ["1", "2", "3"]
    assert len(requests) == 2
    assert all(timeout == 15.0 for _, timeout in requests)
    assert all(request.get_header("X-demo-admin-password") == "secret" for request, _ in requests)
    assert "/runs/run%20id/timeline?" in requests[0][0].full_url
    assert "limit=2" in requests[0][0].full_url
    assert "order_desc=false" in requests[0][0].full_url


def test_api_client_gets_memory_snapshot_in_one_request() -> None:
    requests = []

    def open_url(request, *, timeout: float):
        requests.append((request, timeout))
        return FakeResponse(
            {
                "run_id": "run-1",
                "tick_no": 4,
                "memory_limit": 100,
                "observed_counts": {"alice": 3, "bob": 0},
                "capped_agent_ids": [],
            }
        )

    client = RunQualityApiClient("http://localhost:18080/api", open_url=open_url)

    snapshot = client.get_memory_snapshot("run-1")

    assert snapshot == {
        "tick_no": 4,
        "observed_counts": {"alice": 3, "bob": 0},
        "capped_agent_ids": [],
    }
    assert len(requests) == 1
    assert requests[0][0].full_url.endswith("/runs/run-1/agents/memory-counts?memory_limit=100")


def test_collect_run_quality_report_samples_ticks_and_memory_growth() -> None:
    class StubClient:
        current_tick = 4
        observation_scores: Iterator[float] = iter([0.1, 0.2, 0.35])
        memory_counts: Iterator[int] = iter([2, 5])

        def get_run(self, _run_id: str) -> dict:
            return {"id": "run-1", "current_tick": self.current_tick, "status": "paused"}

        def get_director_observation(self, _run_id: str) -> dict:
            return {
                "subject_alert_tracking_enabled": True,
                "subject_alert_score": next(self.observation_scores),
            }

        def get_memory_snapshot(self, _run_id: str) -> dict:
            return {
                "tick_no": self.current_tick,
                "observed_counts": {"alice": next(self.memory_counts)},
                "capped_agent_ids": [],
            }

        def advance_tick(self, _run_id: str) -> dict:
            self.current_tick += 1
            return {
                "tick_no": self.current_tick,
                "accepted_count": 2,
                "rejected_count": 1,
            }

        def list_timeline_events(self, _run_id: str) -> list[dict]:
            return [
                {"tick_no": 5, "event_type": "move", "payload": {"actor_name": "Alice"}},
                {
                    "tick_no": 6,
                    "event_type": "move_rejected",
                    "payload": {"actor_name": "Alice"},
                },
            ]

    times = iter([10.0, 10.5, 20.0, 21.5])

    report = collect_run_quality_report(
        StubClient(),
        "run-1",
        ticks=2,
        clock=lambda: next(times),
    )

    assert report["run"]["current_tick"] == 6
    assert report["subject_alert"]["sample_count"] == 3
    assert report["subject_alert"]["start_score"] == 0.1
    assert report["subject_alert"]["end_score"] == 0.35
    assert report["memory"]["observed_delta"] == 3
    assert report["performance"] == {
        "sample_count": 2,
        "mean_tick_seconds": 1.0,
        "p95_tick_seconds": 1.5,
    }


def test_collect_run_quality_report_rejects_negative_tick_count() -> None:
    with pytest.raises(ValueError, match="ticks must be non-negative"):
        collect_run_quality_report(object(), "run-1", ticks=-1)


def test_collect_run_quality_report_rejects_tick_advance_for_running_run() -> None:
    class StubClient:
        advance_called = False

        def get_run(self, _run_id: str) -> dict:
            return {"id": "run-1", "current_tick": 4, "status": "running"}

        def advance_tick(self, _run_id: str) -> dict:
            self.advance_called = True
            return {}

    client = StubClient()

    with pytest.raises(ValueError, match="pause the run before advancing evaluation ticks"):
        collect_run_quality_report(client, "run-1", ticks=1)

    assert client.advance_called is False
