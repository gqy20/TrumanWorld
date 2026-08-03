from typer.testing import CliRunner

from app.cli.client import ApiClient
from app.cli.main import app

runner = CliRunner()
RUN_ID = "12345678-1234-4234-8234-123456789abc"


def test_run_list_supports_json_output(monkeypatch):
    monkeypatch.setattr(
        ApiClient,
        "get",
        lambda _self, path, **_kwargs: (
            [{"id": "run-1", "name": "Town", "status": "paused", "current_tick": 3}]
            if path == "runs"
            else {}
        ),
    )

    result = runner.invoke(app, ["--output", "json", "run", "list"])

    assert result.exit_code == 0
    assert '"id": "run-1"' in result.stdout


def test_run_create_paused_sends_auto_start_false(monkeypatch):
    recorded = {}

    def fake_post(_self, path, *, json_body=None):
        recorded.update({"path": path, "body": json_body})
        return {"id": "run-2", "name": "Debug", "status": "created"}

    monkeypatch.setattr(ApiClient, "post", fake_post)

    result = runner.invoke(
        app,
        ["--output", "json", "run", "create", "--name", "Debug", "--paused"],
    )

    assert result.exit_code == 0
    assert recorded["path"] == "runs"
    assert recorded["body"]["auto_start"] is False


def test_scenario_list_exposes_registered_scenarios(monkeypatch):
    monkeypatch.setattr(
        ApiClient,
        "get",
        lambda _self, path, **_kwargs: (
            [{"id": "narrative_world", "name": "Narrative World", "version": "1"}]
            if path == "scenarios"
            else {}
        ),
    )

    result = runner.invoke(app, ["--output", "json", "scenario", "list"])

    assert result.exit_code == 0
    assert '"id": "narrative_world"' in result.stdout


def test_timeline_list_requests_latest_events_by_default(monkeypatch):
    requests = []

    def fake_get(_self, path, **kwargs):
        requests.append((path, kwargs.get("params")))
        if path == "runs":
            return [{"id": RUN_ID, "name": "Town"}]
        return {"events": []}

    monkeypatch.setattr(ApiClient, "get", fake_get)

    result = runner.invoke(app, ["--output", "json", "timeline", "list", "Town"])

    assert result.exit_code == 0
    assert requests[-1][1]["order_desc"] is True


def test_run_show_resolves_short_id(monkeypatch):
    requested: list[str] = []

    def fake_get(_self, path, **_kwargs):
        requested.append(path)
        if path == "runs":
            return [{"id": RUN_ID, "name": "Town"}]
        return {"id": RUN_ID, "status": "paused"}

    monkeypatch.setattr(ApiClient, "get", fake_get)

    result = runner.invoke(app, ["--output", "json", "run", "show", "12345678"])

    assert result.exit_code == 0
    assert requested == ["runs", f"runs/{RUN_ID}"]
    assert RUN_ID in result.stdout


def test_agent_show_resolves_run_and_agent_aliases(monkeypatch):
    requested: list[str] = []

    def fake_get(_self, path, **_kwargs):
        requested.append(path)
        if path == "runs":
            return [{"id": RUN_ID, "name": "Town"}]
        if path == f"runs/{RUN_ID}/agents":
            return {"agents": [{"id": f"{RUN_ID}-truman", "config_id": "truman", "name": "Truman"}]}
        return {"agent_id": f"{RUN_ID}-truman", "name": "Truman"}

    monkeypatch.setattr(ApiClient, "get", fake_get)

    result = runner.invoke(
        app,
        ["--output", "json", "agent", "show", "12345678", "truman"],
    )

    assert result.exit_code == 0
    assert requested[-1] == f"runs/{RUN_ID}/agents/{RUN_ID}-truman"


def test_world_spatial_returns_only_embodiment_diagnostics(monkeypatch):
    def fake_get(_self, path, **_kwargs):
        if path == "runs":
            return [{"id": RUN_ID, "name": "Town"}]
        return {
            "tick": 4,
            "world_time": "2026-03-02T08:00:00Z",
            "map_id": "campus-world-v2",
            "agents": [
                {
                    "id": f"{RUN_ID}-truman",
                    "name": "Truman",
                    "position_meters": [1, 0, 2],
                    "zone_id": "quad.center",
                    "current_location_id": f"{RUN_ID}-quad",
                    "movement": {
                        "id": "move-1",
                        "state": "paused",
                        "paused_progress": 0.4,
                        "paused_for_conversation_id": "conversation-1",
                    },
                    "activity": {
                        "id": "activity-1",
                        "status": "paused",
                        "pause_reason": "encounter_conversation",
                    },
                    "profile": {"private": "omitted"},
                }
            ],
            "object_states": [{"resource_id": "bench:1", "occupant_agent_ids": []}],
        }

    monkeypatch.setattr(ApiClient, "get", fake_get)

    result = runner.invoke(app, ["--output", "json", "world", "spatial", "Town"])

    assert result.exit_code == 0
    assert '"map_id": "campus-world-v2"' in result.stdout
    assert '"position_meters"' in result.stdout
    assert '"paused_progress": 0.4' in result.stdout
    assert '"pause_reason": "encounter_conversation"' in result.stdout
    assert '"private"' not in result.stdout


def test_world_encounters_includes_pause_and_resume_lifecycle(monkeypatch):
    requested = {}

    def fake_get(_self, path, **kwargs):
        if path == "runs":
            return [{"id": RUN_ID, "name": "Town"}]
        requested.update({"path": path, **kwargs})
        return {"events": []}

    monkeypatch.setattr(ApiClient, "get", fake_get)

    result = runner.invoke(app, ["--output", "json", "world", "encounters", "Town"])

    assert result.exit_code == 0
    assert requested["path"] == f"runs/{RUN_ID}/timeline"
    assert requested["params"]["event_type"] == (
        "encounter_candidate_created,encounter_resolved,"
        "activity_paused,activity_resumed,movement_paused,movement_resumed"
    )


def test_agent_activity_start_resolves_aliases_and_advances_via_manual_action(monkeypatch):
    recorded = {}

    def fake_get(_self, path, **_kwargs):
        if path == "runs":
            return [{"id": RUN_ID, "name": "Town"}]
        if path == f"runs/{RUN_ID}/agents":
            return {"agents": [{"id": f"{RUN_ID}-truman", "config_id": "truman", "name": "Truman"}]}
        if path == f"runs/{RUN_ID}/world":
            return {"locations": [{"id": f"{RUN_ID}-cafe", "name": "Studio Cafe"}]}
        raise AssertionError(path)

    def fake_post(_self, path, *, json_body=None):
        recorded.update({"path": path, "body": json_body})
        return {"run_id": RUN_ID, "tick_no": 3, "accepted": []}

    monkeypatch.setattr(ApiClient, "get", fake_get)
    monkeypatch.setattr(ApiClient, "post", fake_post)

    result = runner.invoke(
        app,
        [
            "--output",
            "json",
            "agent",
            "activity-start",
            "Town",
            "truman",
            "drink_coffee",
            "--location",
            "cafe",
        ],
    )

    assert result.exit_code == 0
    assert recorded == {
        "path": f"runs/{RUN_ID}/actions",
        "body": {
            "agent_id": f"{RUN_ID}-truman",
            "action_type": "start_activity",
            "target_location_id": f"{RUN_ID}-cafe",
            "payload": {"activity_type": "drink_coffee"},
        },
    }


def test_director_inject_validates_type_and_resolves_location_alias(monkeypatch):
    recorded = {}

    def fake_get(_self, path, **_kwargs):
        if path == "runs":
            return [{"id": RUN_ID, "name": "Town"}]
        if path == f"runs/{RUN_ID}/world":
            return {"locations": [{"id": f"{RUN_ID}-plaza", "name": "小镇广场"}]}
        raise AssertionError(path)

    def fake_post(_self, path, *, json_body=None):
        recorded.update({"path": path, "body": json_body})
        return {"status": "queued"}

    monkeypatch.setattr(ApiClient, "get", fake_get)
    monkeypatch.setattr(ApiClient, "post", fake_post)

    result = runner.invoke(
        app,
        [
            "director",
            "inject",
            "12345678",
            "--type",
            "broadcast",
            "--location",
            "plaza",
        ],
    )

    assert result.exit_code == 0
    assert recorded == {
        "path": f"runs/{RUN_ID}/director/events",
        "body": {
            "event_type": "broadcast",
            "payload": {},
            "location_id": f"{RUN_ID}-plaza",
            "importance": 0.5,
        },
    }


def test_director_inject_help_lists_supported_event_types():
    result = runner.invoke(app, ["director", "inject", "--help"])

    assert result.exit_code == 0
    assert "broadcast" in result.stdout
    assert "power_outage" in result.stdout


def test_director_directives_filters_and_renders_rows(monkeypatch):
    requested = []

    def fake_get(_self, path, **kwargs):
        requested.append((path, kwargs.get("params")))
        if path == "runs":
            return [{"id": RUN_ID, "name": "Town"}]
        return {
            "directives": [
                {
                    "id": "directive-1",
                    "issued_tick": 5,
                    "target_agent_name": "Meryl",
                    "objective": "soft_check_in",
                    "mode": "priority",
                    "status": "active",
                    "disposition": "accepted",
                    "failure_reason": None,
                }
            ]
        }

    monkeypatch.setattr(ApiClient, "get", fake_get)

    result = runner.invoke(
        app,
        ["--output", "json", "director", "directives", "Town", "--status", "active"],
    )

    assert result.exit_code == 0
    assert requested[-1] == (
        f"runs/{RUN_ID}/director/directives",
        {"status": "active", "limit": 100},
    )
    assert '"objective": "soft_check_in"' in result.stdout


def test_director_directive_resolves_short_id(monkeypatch):
    requested = []

    def fake_get(_self, path, **kwargs):
        requested.append(path)
        if path == "runs":
            return [{"id": RUN_ID, "name": "Town"}]
        if path == f"runs/{RUN_ID}/director/directives":
            return {"directives": [{"id": "directive-full-id"}]}
        return {"id": "directive-full-id", "status": "active"}

    monkeypatch.setattr(ApiClient, "get", fake_get)

    result = runner.invoke(
        app,
        ["--output", "json", "director", "directive", "Town", "directive-full"],
    )

    assert result.exit_code == 0
    assert requested[-1] == f"runs/{RUN_ID}/director/directives/directive-full-id"


def test_run_step_advances_an_inactive_world_exactly(monkeypatch):
    posts: list[str] = []
    next_tick = iter((4, 5))

    monkeypatch.setattr(
        ApiClient,
        "get",
        lambda _self, path, **_kwargs: {"id": RUN_ID, "status": "paused", "current_tick": 3},
    )
    monkeypatch.setattr(
        ApiClient,
        "post",
        lambda _self, path, **_kwargs: (
            posts.append(path)
            or {
                "tick_no": next(next_tick),
                "accepted_count": 2,
                "rejected_count": 0,
            }
        ),
    )

    result = runner.invoke(
        app,
        ["--output", "json", "run", "step", RUN_ID, "--count", "2"],
    )

    assert result.exit_code == 0
    assert posts == [f"runs/{RUN_ID}/tick", f"runs/{RUN_ID}/tick"]
    assert '"tick_no": 5' in result.stdout


def test_play_script_renders_latest_story(monkeypatch):
    def fake_get(_self, path, **_kwargs):
        if path == f"runs/{RUN_ID}":
            return {"id": RUN_ID, "name": "Town", "status": "paused", "current_tick": 1}
        if path.endswith("world/pulse"):
            return {
                "world_clock": {"display": "06:05"},
                "daily_stats": {"total_input_tokens": 10, "total_output_tokens": 2},
            }
        if path.endswith("timeline"):
            return {
                "events": [
                    {
                        "tick_no": 1,
                        "event_type": "speech",
                        "world_time": "06:05",
                        "payload": {
                            "actor_name": "Meryl",
                            "target_name": "Truman",
                            "message": "早上好",
                        },
                    }
                ]
            }
        raise AssertionError(path)

    monkeypatch.setattr(ApiClient, "get", fake_get)

    result = runner.invoke(app, ["play", RUN_ID, "--execute", "look"])

    assert result.exit_code == 0
    assert "Latest story" in result.stdout
    assert "Meryl → Truman" in result.stdout
    assert "“早上好”" in result.stdout


def test_world_cost_marks_unreported_provider_cost_as_unavailable(monkeypatch):
    monkeypatch.setattr(
        ApiClient,
        "get",
        lambda _self, path, **_kwargs: {
            "daily_stats": {
                "llm_provider": "anthropic",
                "llm_model": "MiniMax-M3",
                "total_cost_usd": 0,
                "total_input_tokens": 100,
                "total_output_tokens": 20,
            }
        },
    )

    result = runner.invoke(app, ["world", "cost", RUN_ID])

    assert result.exit_code == 0
    assert "unavailable" in result.stdout


def test_system_status_distinguishes_remote_database_from_local_process(monkeypatch):
    def fake_get(_self, path, **_kwargs):
        if path == "ready":
            return {"status": "ready"}
        return {
            "components": {
                "backend": {"status": "available", "rss_bytes": 1048576},
                "frontend": {"status": "available", "rss_bytes": 2097152},
                "postgres": {"status": "unavailable", "rss_bytes": 0},
                "total": {"status": "available", "rss_bytes": 3145728},
            }
        }

    monkeypatch.setattr(ApiClient, "get", fake_get)

    result = runner.invoke(app, ["system", "status"])

    assert result.exit_code == 0
    assert "database_connectivity" in result.stdout
    assert "remote / no local process" in result.stdout


def test_run_wait_pauses_when_cost_limit_is_reached(monkeypatch):
    posts = []

    def fake_get(_self, path, **_kwargs):
        if path == "runs":
            return [{"id": "run-1", "status": "running", "current_tick": 4}]
        if path.endswith("world/pulse"):
            return {"daily_stats": {"total_cost_usd": 0.25}}
        return {"id": "run-1", "status": "running", "current_tick": 4}

    monkeypatch.setattr(ApiClient, "get", fake_get)
    monkeypatch.setattr(ApiClient, "post", lambda _self, path, **_kwargs: posts.append(path) or {})

    result = runner.invoke(
        app,
        ["--output", "json", "run", "wait", "run-1", "--max-cost", "0.20"],
    )

    assert result.exit_code == 0
    assert posts == ["runs/run-1/pause"]
    assert '"reason": "cost_limit"' in result.stdout


def test_run_wait_can_guard_providers_that_only_report_tokens(monkeypatch):
    posts = []

    def fake_get(_self, path, **_kwargs):
        if path == "runs":
            return [{"id": "run-1", "status": "running", "current_tick": 4}]
        if path.endswith("world/pulse"):
            return {
                "daily_stats": {
                    "total_cost_usd": 0,
                    "total_input_tokens": 900,
                    "total_output_tokens": 150,
                    "total_reasoning_tokens": 0,
                }
            }
        return {"id": "run-1", "status": "running", "current_tick": 4}

    monkeypatch.setattr(ApiClient, "get", fake_get)
    monkeypatch.setattr(ApiClient, "post", lambda _self, path, **_kwargs: posts.append(path) or {})

    result = runner.invoke(
        app,
        ["--output", "json", "run", "wait", "run-1", "--max-tokens", "1000"],
    )

    assert result.exit_code == 0
    assert posts == ["runs/run-1/pause"]
    assert '"reason": "token_limit"' in result.stdout
