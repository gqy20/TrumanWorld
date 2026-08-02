from pathlib import Path

import pytest
from pydantic import ValidationError

from app.agent.config_loader import AgentConfigLoader, InitialConfigLoader
from app.agent.prompt_loader import PromptLoader
from app.agent.registry import AgentRegistry

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_agent_config_loader_reads_template_config():
    loader = AgentConfigLoader()

    config = loader.load(REPO_ROOT / "agents" / "_template" / "agent.yml")

    assert config.id == "demo_agent"
    assert config.name == "Demo Agent"
    assert config.world_role == "cast"
    assert config.capabilities.dialogue is True
    assert config.model.max_turns == 8


def test_prompt_loader_reads_and_renders_prompt():
    loader = PromptLoader()
    prompt = loader.load(REPO_ROOT / "agents" / "_template" / "prompt.md")
    rendered = loader.render(prompt, context={"location": "cafe", "goal": "work"})

    assert "角色定义" in prompt
    assert "# 运行上下文" in rendered
    assert '"location": "cafe"' in rendered
    assert '"goal": "work"' in rendered


def test_prompt_loader_decision_prompt_discourages_work_as_default():
    loader = PromptLoader()

    rendered = loader.render_decision_prompt(
        "你是测试角色",
        context={"current_location_name": "海滨公寓", "current_goal": "work"},
        allowed_actions=["move", "talk", "work", "rest"],
    )

    assert "优先保持当前情境一致" in rendered
    assert "不要把普通停留、等待、整理或在家活动表述成 `work`" in rendered
    assert "只能使用运行上下文中真实存在的地点 ID" in rendered


def test_agent_registry_lists_configs_and_renders_prompt(tmp_path: Path):
    agent_dir = tmp_path / "alice"
    agent_dir.mkdir(parents=True)
    (agent_dir / "agent.yml").write_text(
        "\n".join(
            [
                "id: alice",
                "name: Alice",
                "occupation: barista",
                "home: apartment_a",
                "personality:",
                "  openness: 0.7",
                "capabilities:",
                "  dialogue: true",
                "  reflection: true",
                "model:",
                "  max_turns: 8",
                "  max_budget_usd: 1.0",
            ]
        ),
        encoding="utf-8",
    )
    (agent_dir / "prompt.md").write_text("# Alice\nHello", encoding="utf-8")

    registry = AgentRegistry(tmp_path)

    configs = registry.list_configs()
    prompt = registry.get_prompt("alice", context={"tick": 3})

    assert len(configs) == 1
    assert configs[0].id == "alice"
    assert configs[0].world_role == "cast"
    assert prompt is not None
    assert '"tick": 3' in prompt


def test_initial_config_loader_reads_spawn_config(tmp_path: Path):
    initial_path = tmp_path / "initial.yml"
    initial_path.write_text(
        "\n".join(
            [
                "status:",
                "  energy: 0.9",
                "  alert_score: 0.2",
                "plan:",
                "  default: patrol",
                "spawn:",
                "  location: workplace",
                "  goal: greet",
            ]
        ),
        encoding="utf-8",
    )

    config = InitialConfigLoader().load(initial_path)

    assert config.status.energy == 0.9
    assert config.status.alert_score == 0.2
    assert config.spawn.location == "workplace"
    assert config.spawn.goal == "greet"


@pytest.mark.parametrize(
    "removed_field",
    ["initial_goal: work", "initial_location: home", "status:\n  suspicion_score: 0.2"],
)
def test_initial_config_loader_rejects_removed_fields(tmp_path: Path, removed_field: str) -> None:
    initial_path = tmp_path / "initial.yml"
    initial_path.write_text(removed_field, encoding="utf-8")

    with pytest.raises(ValidationError):
        InitialConfigLoader().load(initial_path)
