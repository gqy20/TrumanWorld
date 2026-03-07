from pathlib import Path


class AgentRegistry:
    """Loads agent configurations from the agents directory."""

    def __init__(self, root: Path) -> None:
        self.root = root

