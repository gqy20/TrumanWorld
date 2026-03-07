from app.agent.runtime import AgentRuntime, RuntimeInvocation


class Reflector:
    """Produces reflection memories at day boundaries."""

    def __init__(self, runtime: AgentRuntime) -> None:
        self.runtime = runtime

    def prepare(
        self,
        agent_id: str,
        world: dict | None = None,
        memory: dict | None = None,
        daily_summary: dict | None = None,
    ) -> RuntimeInvocation:
        return self.runtime.prepare_reflector(
            agent_id,
            world=world,
            memory=memory,
            daily_summary=daily_summary,
        )
