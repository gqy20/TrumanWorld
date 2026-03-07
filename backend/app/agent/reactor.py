from app.agent.runtime import AgentRuntime, RuntimeInvocation


class Reactor:
    """Generates context-sensitive action intents."""

    def __init__(self, runtime: AgentRuntime) -> None:
        self.runtime = runtime

    def prepare(
        self,
        agent_id: str,
        world: dict | None = None,
        memory: dict | None = None,
        event: dict | None = None,
    ) -> RuntimeInvocation:
        return self.runtime.prepare_reactor(agent_id, world=world, memory=memory, event=event)
