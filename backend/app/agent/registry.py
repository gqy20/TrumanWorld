from pathlib import Path

from app.agent.config_loader import AgentConfig, AgentConfigLoader
from app.agent.prompt_loader import PromptLoader


class AgentRegistry:
    """Loads agent configurations from the agents directory."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._config_loader = AgentConfigLoader()
        self._prompt_loader = PromptLoader()

    def list_agent_dirs(self) -> list[Path]:
        if not self.root.exists():
            return []

        return sorted(
            path
            for path in self.root.iterdir()
            if path.is_dir() and not path.name.startswith("_") and (path / "agent.yml").exists()
        )

    def list_configs(self) -> list[AgentConfig]:
        return [self._config_loader.load(path / "agent.yml") for path in self.list_agent_dirs()]

    def get_config(self, agent_id: str) -> AgentConfig | None:
        for config in self.list_configs():
            if config.id == agent_id:
                return config
        return None

    def get_prompt(self, agent_id: str, context: dict[str, object] | None = None) -> str | None:
        config = self.get_config(agent_id)
        if config is None:
            return None

        prompt = self._prompt_loader.load(config.prompt_path)
        return self._prompt_loader.render(prompt, context=context)
