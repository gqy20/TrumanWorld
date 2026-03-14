from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from app.agent.registry import AgentRegistry
from app.infra.settings import get_settings
from app.scenario.truman_world.rules import load_world_config
from app.scenario.truman_world.types import build_agent_profile
from app.sim.context import DEFAULT_WORLD_START_TIME
from app.store.models import Agent, Location, Relationship

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.store.models import SimulationRun


# 延迟加载世界配置（避免模块导入时初始化问题）
_WORLD_CONFIG_CACHE: dict | None = None


def _get_world_config() -> dict:
    """Lazy load world configuration."""
    global _WORLD_CONFIG_CACHE
    if _WORLD_CONFIG_CACHE is None:
        _WORLD_CONFIG_CACHE = load_world_config()
    return _WORLD_CONFIG_CACHE


# 地点定义：从 YAML 配置加载（延迟加载）
def _get_location_configs() -> list[dict]:
    return _get_world_config().get("locations", [])


# 地点 ID 映射：从 YAML 配置加载（延迟加载）
def _get_location_id_map() -> dict:
    return _get_world_config().get("location_id_map", {})


# 职业中文映射：从 YAML 配置加载（延迟加载）
def _get_occupation_names() -> dict[str, str]:
    return _get_world_config().get("occupation_names", {})


class TrumanWorldSeedBuilder:
    """Builds the default Truman-world demo seed from agent configuration files."""

    def __init__(
        self,
        session: AsyncSession,
        registry: AgentRegistry | None = None,
    ) -> None:
        self.session = session
        settings = get_settings()
        self.registry = registry or AgentRegistry(settings.project_root / "agents")

    def _build_location_id(self, run_id: str, suffix: str) -> str:
        """Build full location ID from run_id and suffix."""
        return f"{run_id}-{suffix}"

    def _resolve_location_id(
        self,
        run_id: str,
        location_key: str | None,
        location_id_map: dict[str, str],
    ) -> str | None:
        """Resolve location key to full location ID."""
        if location_key is None:
            return None
        suffix = location_id_map.get(location_key, location_key)
        return self._build_location_id(run_id, suffix)

    def _get_occupation_name(self, occupation: str) -> str:
        """Get localized occupation name."""
        return _get_occupation_names().get(occupation, occupation)

    async def seed_demo_run(self, run: SimulationRun) -> None:
        """Seed a demo run from agent configuration files."""
        run_id = run.id

        # 1. 创建地点
        locations: dict[str, Location] = {}
        for loc_config in _get_location_configs():
            loc_id = self._build_location_id(run_id, loc_config["id_suffix"])
            locations[loc_config["id_suffix"]] = Location(
                id=loc_id,
                run_id=run_id,
                name=loc_config["name"],
                location_type=loc_config["location_type"],
                capacity=loc_config["capacity"],
                x=loc_config["x"],
                y=loc_config["y"],
                attributes=loc_config["attributes"],
            )

        # 2. 从 agents/ 目录加载配置并创建 Agent
        agent_configs = self.registry.list_configs()
        agents: dict[str, Agent] = {}

        for config in agent_configs:
            # 加载初始状态配置
            initial = self.registry.get_initial(config.id)

            # 加载 bio
            bio = self.registry.get_bio(config.id) or ""

            # 解析 home_location_id
            location_id_map = _get_location_id_map()
            home_location_id = self._resolve_location_id(run_id, config.home, location_id_map)

            # 解析 workplace_location_id
            workplace_location_id = None
            if config.workplace:
                workplace_location_id = self._resolve_location_id(
                    run_id, config.workplace, location_id_map
                )

            # 确定初始位置
            current_location_id = home_location_id
            if initial.initial_location == "workplace" and workplace_location_id:
                current_location_id = workplace_location_id
            elif initial.initial_location == "home" and home_location_id:
                current_location_id = home_location_id
            elif initial.initial_location:
                # 可能是具体的 location key
                resolved = self._resolve_location_id(
                    run_id, initial.initial_location, location_id_map
                )
                if resolved:
                    current_location_id = resolved

            # 构建 profile
            workplace_name = None
            if config.workplace and config.workplace in location_id_map:
                workplace_name = locations[location_id_map[config.workplace]].name

            # 提取轮班类型（用于 heuristics 替代 agent_id 字符串匹配）
            schedule_type = None
            if config.work_schedule and config.work_schedule.type:
                schedule_type = config.work_schedule.type

            profile = build_agent_profile(
                bio=bio,
                agent_config_id=config.id,
                world_role=config.world_role,
                workplace=workplace_name,
                workplace_location_id=workplace_location_id,
                work_description=config.work_description or "",
                extras={"schedule_type": schedule_type} if schedule_type else None,
            )

            # 构建状态
            status = {
                "energy": initial.status.energy,
            }
            if initial.status.suspicion_score > 0 or config.world_role == "truman":
                status["suspicion_score"] = initial.status.suspicion_score

            # 构建计划
            current_plan = {
                "morning": initial.plan.morning,
                "daytime": initial.plan.daytime,
                "evening": initial.plan.evening,
            }

            agent = Agent(
                id=f"{run_id}-{config.id}",
                run_id=run_id,
                name=config.name,
                occupation=self._get_occupation_name(config.occupation),
                home_location_id=home_location_id,
                current_location_id=current_location_id,
                current_goal=initial.initial_goal,
                personality=config.personality,
                profile=profile,
                status=status,
                current_plan=current_plan,
            )
            agents[config.id] = agent

        # 3. 从 agents/ 目录加载关系配置并创建 Relationship
        relationships = []
        all_relations = self.registry.load_all_relations()

        for (from_agent_id, to_agent_id), rel_config in all_relations.items():
            if from_agent_id not in agents or to_agent_id not in agents:
                continue

            relationships.append(
                Relationship(
                    id=str(uuid4()),
                    run_id=run_id,
                    agent_id=agents[from_agent_id].id,
                    other_agent_id=agents[to_agent_id].id,
                    familiarity=rel_config.familiarity,
                    trust=rel_config.trust,
                    affinity=rel_config.affinity,
                    relation_type=rel_config.relation_type,
                )
            )

        # 4. 设置世界开始时间
        if "world_start_time" not in (run.metadata_json or {}):
            metadata = dict(run.metadata_json or {})
            metadata["world_start_time"] = DEFAULT_WORLD_START_TIME.isoformat()
            run.metadata_json = metadata

        # 5. 持久化
        self.session.add_all(list(locations.values()))
        await self.session.flush()
        self.session.add_all(list(agents.values()))
        await self.session.flush()
        if relationships:
            self.session.add_all(relationships)
        await self.session.commit()
