# Agent Backend Abstraction

## 1. Background

TrumanWorld currently couples agent cognition to `claude_agent_sdk` in several places:

- resident agent decision runtime
- director cognition
- Claude SDK connection pooling and process cleanup
- SDK-specific retry / cancellation handling
- SDK-specific configuration and environment wiring

This coupling makes the current system expensive to run and difficult to evolve. The immediate design goal is not to replace the world simulator. The goal is to decouple the cognition runtime so TrumanWorld can select among:

- `claude_sdk`
- `langgraph`
- `heuristic`

using the same world core.

## 2. Goals

- Keep the world core unchanged as much as possible.
- Define a framework-neutral cognition interface.
- Move Claude-specific logic behind an adapter boundary.
- Make room for a future LangGraph adapter without rewriting the simulation core.
- Allow per-run or global backend selection.

## 3. Non-Goals

- Rewriting the scheduler, persistence, or API surface.
- Replacing all agent cognition logic in one step.
- Moving world time, day-boundary, or event storage into LangGraph.
- Building a full LangGraph implementation in the first phase.

## 4. Current Coupling

### 4.1 Direct SDK Core

The main Claude SDK coupling lives in:

- `backend/app/agent/providers.py`
- `backend/app/agent/runtime.py`
- `backend/app/agent/connection_pool.py`
- `backend/app/agent/sdk_options.py`
- `backend/app/director/agent.py`

### 4.2 Peripheral Coupling

Additional references exist in:

- `backend/app/infra/settings.py`
- `backend/app/sim/service.py`
- `backend/app/sim/scheduler.py`
- `backend/app/main.py`

### 4.3 Architectural Problem

Today, Claude is not just an implementation detail. It shapes runtime structure:

- long-lived SDK client pool
- Claude-specific cancellation handling
- Claude-specific process cleanup
- Claude-specific options and MCP configuration

As a result, the business layer is not cleanly separated from the framework layer.

## 5. Target Architecture

The target split has four layers.

### 5.1 World Core

Owns:

- tick progression
- world state
- day-boundary rules
- persistence
- scheduler
- run lifecycle
- world/timeline APIs

This layer must not know whether cognition comes from Claude, LangGraph, or heuristics.

### 5.2 Cognition Interface

Defines the domain-level capabilities TrumanWorld needs.

Example interfaces:

```python
class AgentCognitionBackend(Protocol):
    async def decide_action(self, invocation: AgentInvocation) -> RuntimeDecision: ...
    async def plan_day(self, invocation: PlanningInvocation) -> PlanningResult: ...
    async def reflect_day(self, invocation: ReflectionInvocation) -> ReflectionResult: ...
```

```python
class DirectorCognitionBackend(Protocol):
    async def observe_world(self, invocation: DirectorObservationInvocation) -> DirectorObservation: ...
    async def propose_intervention(
        self,
        invocation: DirectorInterventionInvocation,
    ) -> DirectorDecision: ...
```

Rules for this layer:

- no Claude terms
- no LangGraph terms
- no SDK session or graph state leakage
- domain-native request and response types only

### 5.3 Framework Adapters

Each framework implements the interface:

- `ClaudeSdkAgentBackend`
- `LangGraphAgentBackend`
- `HeuristicAgentBackend`
- `ClaudeSdkDirectorBackend`
- `LangGraphDirectorBackend`

Each adapter is responsible for:

- translating TrumanWorld invocation -> framework input
- executing the framework runtime
- parsing framework output
- returning TrumanWorld-native result types

### 5.4 Framework-Specific Infrastructure

Framework-private plumbing stays here.

Claude examples:

- SDK connection pool
- SDK options builder
- orphan process cleanup
- MCP config

LangGraph examples:

- graph registry
- graph state schema
- checkpoint store
- graph tool wiring

This layer is allowed to be framework-specific and should not leak upward.

### 5.5 Pooling Policy

Connection pooling is not a universal optimization.

For TrumanWorld's current Claude SDK integration:

- reactor / action decision may use pooled long-lived clients
- planner must remain a one-shot query call
- reflector must remain a one-shot query call
- director decision must remain a one-shot query call

Reason:

- `ClaudeSDKClient` carries async task-group lifecycle and session state
- low-frequency free-text tasks do not benefit enough from pooling
- forcing these tasks through the pool increases cancellation and cleanup risk

In short:

- pool only the high-frequency reactor path
- keep planner / reflector / director stateless

## 6. Proposed Module Layout

### 6.1 New Neutral Layer

Create:

- `backend/app/cognition/interfaces.py`
- `backend/app/cognition/types.py`
- `backend/app/cognition/registry.py`

Responsibilities:

- define agent/director backend protocols
- define framework-neutral result types
- select backend implementations from configuration

### 6.2 Claude Adapter Layer

Move or wrap current Claude logic into:

- `backend/app/cognition/claude/agent_backend.py`
- `backend/app/cognition/claude/director_backend.py`
- `backend/app/cognition/claude/connection_pool.py`
- `backend/app/cognition/claude/sdk_options.py`

The intent is to make Claude one backend implementation, not the central architecture.

### 6.3 LangGraph Adapter Layer

Future location:

- `backend/app/cognition/langgraph/agent_backend.py`
- `backend/app/cognition/langgraph/director_backend.py`
- `backend/app/cognition/langgraph/graphs.py`
- `backend/app/cognition/langgraph/state.py`

### 6.4 Runtime Entry Points

Existing runtime orchestration can keep its role, but it should depend only on the neutral layer.

Examples:

- `AgentRuntime` should request an `AgentCognitionBackend`
- director services should request a `DirectorCognitionBackend`

## 7. Configuration Direction

Current configuration is effectively:

- `heuristic`
- `claude`

Target configuration should be explicit:

```python
agent_backend: Literal["heuristic", "claude_sdk", "langgraph"] = "heuristic"
director_backend: Literal["heuristic", "claude_sdk", "langgraph"] = "heuristic"
```

This avoids overloading the word `provider` and clarifies that the choice is now a runtime backend selection.

## 8. Migration Strategy

### Phase 1: Extract Neutral Types

- define framework-neutral agent/director interfaces
- define result types for action, planning, reflection, director observation
- keep existing behavior unchanged

### Phase 2: Wrap Claude as Adapter

- move Claude-specific logic behind the new interface
- keep existing provider behavior but route through the new adapter
- isolate connection pool as Claude-private infra

### Phase 3: Switch Runtime Construction

- replace direct Claude-aware construction with backend registry lookup
- make `AgentRuntime` and director services consume neutral backends

### Phase 4: Add LangGraph Backend

- implement `LangGraphAgentBackend` for the smallest viable scope:
  - action decision first
- optionally defer director and planning integration to a second pass

### Phase 5: Expand Coverage

- evaluate whether planner/reflector should also move to LangGraph
- add backend-specific tracing hooks
- add integration tests to compare backend parity

Planner / reflector / director should preserve one-shot execution semantics
unless the underlying SDK/runtime guarantees safe cross-task long-lived reuse.

## 9. Minimal LangGraph Entry Point

The first LangGraph implementation should not take over world orchestration.

Recommended scope:

- keep current `SimulationService`
- keep current tick loop
- keep current persistence
- replace only the agent decision backend

This limits risk and allows side-by-side evaluation of:

- `heuristic`
- `claude_sdk`
- `langgraph`

under the same world engine and test suite.

## 10. Main Risks

### 10.1 Over-Abstracting Too Early

If the neutral interface tries to model every future framework feature, it will become vague and hard to use.

Mitigation:

- define only the domain operations TrumanWorld already needs

### 10.2 Claude Assumptions Leaking Into Neutral Types

Examples:

- session ids
- SDK message objects
- SDK options
- Claude cancellation behavior

Mitigation:

- keep neutral types plain and domain-focused

### 10.3 LangGraph Scope Creep

It is tempting to let LangGraph absorb planner, reflector, memory flow, and world orchestration all at once.

Mitigation:

- start with action decision only

## 11. Recommendation

Near-term recommendation:

1. create the neutral cognition interface
2. move Claude-specific logic behind a Claude adapter
3. switch runtime construction to a backend registry
4. add a minimal LangGraph action backend in parallel

This gives TrumanWorld a clean path to support multiple cognition runtimes without rewriting the world simulator.

## 12. Concrete Interface Sketch

The first implementation should keep the interface small and aligned to current behavior.

### 12.1 Neutral Types

Suggested location:

- `backend/app/cognition/types.py`

Suggested first-pass types:

```python
@dataclass(slots=True)
class CognitionMetadata:
    backend: str
    model: str | None = None
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    raw_trace_id: str | None = None
```

```python
class ActionDecision(BaseModel):
    action_type: str
    target_location_id: str | None = None
    target_agent_id: str | None = None
    message: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: CognitionMetadata | None = None
```

```python
class PlanningDecision(BaseModel):
    morning: str | None = None
    daytime: str | None = None
    evening: str | None = None
    intention: str | None = None
    metadata: CognitionMetadata | None = None
```

```python
class ReflectionDecision(BaseModel):
    reflection: str | None = None
    mood: str | None = None
    key_person: str | None = None
    tomorrow_intention: str | None = None
    metadata: CognitionMetadata | None = None
```

```python
class DirectorObservation(BaseModel):
    truman_suspicion_score: float
    suspicion_level: str
    continuity_risk: str
    focus_agent_ids: list[str] = []
    notes: list[str] = []
    metadata: CognitionMetadata | None = None
```

```python
class DirectorDecision(BaseModel):
    scene_goal: str | None = None
    target_agent_id: str | None = None
    target_cast_ids: list[str] = []
    message_hint: str | None = None
    location_hint: str | None = None
    reason: str | None = None
    priority: str = "advisory"
    urgency: str = "advisory"
    metadata: CognitionMetadata | None = None
```

### 12.2 Neutral Interfaces

Suggested location:

- `backend/app/cognition/interfaces.py`

```python
class AgentCognitionBackend(Protocol):
    async def decide_action(
        self,
        invocation: RuntimeInvocation,
        runtime_ctx: RuntimeContext | None = None,
    ) -> ActionDecision: ...

    async def plan_day(
        self,
        agent_id: str,
        agent_name: str,
        world_context: dict[str, Any],
        recent_memories: list[dict[str, Any]] | None = None,
        runtime_ctx: RuntimeContext | None = None,
    ) -> PlanningDecision | None: ...

    async def reflect_day(
        self,
        agent_id: str,
        agent_name: str,
        world_context: dict[str, Any],
        daily_events: list[dict[str, Any]] | None = None,
        runtime_ctx: RuntimeContext | None = None,
    ) -> ReflectionDecision | None: ...
```

```python
class DirectorCognitionBackend(Protocol):
    async def observe_world(
        self,
        run_id: str,
        current_tick: int,
        payload: dict[str, Any],
    ) -> DirectorObservation: ...

    async def propose_intervention(
        self,
        run_id: str,
        current_tick: int,
        payload: dict[str, Any],
    ) -> DirectorDecision | None: ...
```

## 13. Registry Sketch

Suggested location:

- `backend/app/cognition/registry.py`

```python
def build_agent_backend(
    settings: Settings,
    *,
    connection_pool: AgentConnectionPool | None = None,
) -> AgentCognitionBackend:
    if settings.agent_backend == "claude_sdk":
        return ClaudeSdkAgentBackend(settings, connection_pool=connection_pool)
    if settings.agent_backend == "langgraph":
        return LangGraphAgentBackend(settings)
    return HeuristicAgentBackend()
```

```python
def build_director_backend(settings: Settings) -> DirectorCognitionBackend:
    if settings.director_backend == "claude_sdk":
        return ClaudeSdkDirectorBackend(settings)
    if settings.director_backend == "langgraph":
        return LangGraphDirectorBackend(settings)
    return HeuristicDirectorBackend()
```

## 14. File Migration Map

The first refactor should avoid moving too many behaviors at once.

### 14.1 Keep in Place Initially

- `backend/app/sim/service.py`
- `backend/app/sim/day_boundary.py`
- `backend/app/sim/persistence.py`
- `backend/app/sim/scheduler.py`
- `backend/app/api/*`

These files should change dependency direction only, not behavior.

### 14.2 Convert Into Neutral Layer Consumers

#### `backend/app/agent/runtime.py`

Current role:

- prompt preparation
- provider construction
- planner / reflector free-text calls
- intent conversion

Target role:

- keep prompt preparation
- depend on `AgentCognitionBackend`
- stop constructing Claude-specific provider directly

Immediate change:

- replace `_build_default_provider()` with registry lookup
- make `decision_provider` concept become `agent_backend`

#### `backend/app/director/agent.py`

Current role:

- prompt assembly
- Claude SDK invocation
- director observation / decision generation

Target role:

- become `ClaudeSdkDirectorBackend`
- export only domain-native result types upward

### 14.3 Move Behind Claude Adapter Boundary

#### `backend/app/agent/providers.py`

Split into:

- neutral decision/result types move to `cognition/types.py`
- heuristic implementation becomes `cognition/heuristic/agent_backend.py`
- Claude implementation becomes `cognition/claude/agent_backend.py`

#### `backend/app/agent/connection_pool.py`

Move to:

- `backend/app/cognition/claude/connection_pool.py`

Reason:

- this is Claude-private infrastructure, not a system-wide abstraction

#### `backend/app/agent/sdk_options.py`

Move to:

- `backend/app/cognition/claude/sdk_options.py`

Reason:

- SDK options are framework-private, not domain-level

## 15. Minimal Implementation Order

Recommended order for the first real refactor:

1. add `cognition/types.py`
2. add `cognition/interfaces.py`
3. add `cognition/registry.py`
4. wrap current heuristic path as `HeuristicAgentBackend`
5. wrap current Claude decision path as `ClaudeSdkAgentBackend`
6. switch `AgentRuntime` to consume `AgentCognitionBackend`
7. wrap current director Claude path as `ClaudeSdkDirectorBackend`
8. add new settings fields:
   - `agent_backend`
   - `director_backend`
9. keep old config alias temporarily for compatibility
10. only after parity is stable, start `LangGraphAgentBackend`

## 16. Compatibility Strategy

To reduce migration risk:

- remove legacy `agent_provider`
- standardize all runtime selection on `agent_backend`
- standardize director selection on `director_backend`
- emit a warning when old config is used

This keeps rollout incremental and avoids breaking existing deployments.

## 17. First LangGraph Scope

The first LangGraph backend should implement only:

- `decide_action()`

It should explicitly not own:

- scheduler
- tick persistence
- world time
- director flow
- planner/reflector

Those can remain in the current runtime until action-decision parity is verified.
