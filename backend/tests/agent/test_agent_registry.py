from pathlib import Path

from app.agent.config_loader import AgentConfigLoader
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
