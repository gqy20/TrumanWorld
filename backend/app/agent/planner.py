from app.agent.runtime import AgentRuntime, RuntimeInvocation


class Planner:
    """Builds coarse daily plans."""

    def __init__(self, runtime: AgentRuntime) -> None:
        self.runtime = runtime

    def prepare(self, agent_id: str, world: dict | None = None, memory: dict | None = None) -> RuntimeInvocation:
        return self.runtime.prepare_planner(agent_id, world=world, memory=memory)
