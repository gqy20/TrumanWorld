from typer.testing import CliRunner

from app.cli.client import ApiClient
from app.cli.main import app

runner = CliRunner()


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


def test_run_wait_pauses_when_cost_limit_is_reached(monkeypatch):
    posts = []

    def fake_get(_self, path, **_kwargs):
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
