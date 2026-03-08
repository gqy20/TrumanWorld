from __future__ import annotations

from uuid import uuid4

from typing import TYPE_CHECKING

from app.agent.registry import AgentRegistry
from app.infra.settings import get_settings
from app.sim.context import DEFAULT_WORLD_START_TIME
from app.scenario.truman_world.types import build_scenario_agent_profile
from app.store.models import Agent, Location, Relationship

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.store.models import SimulationRun


# =============================================================================
# 地点定义：场景静态配置
# =============================================================================

LOCATION_CONFIGS = [
    {
        "id_suffix": "plaza",
        "name": "小镇广场",
        "location_type": "plaza",
        "capacity": 10,
        "x": 1,
        "y": 2,
        "attributes": {"kind": "social"},
    },
    {
        "id_suffix": "apartment",
        "name": "海滨公寓",
        "location_type": "home",
        "capacity": 3,
        "x": 0,
        "y": 0,
        "attributes": {"kind": "private"},
    },
    {
        "id_suffix": "office",
        "name": "港务办公室",
        "location_type": "office",
        "capacity": 6,
        "x": 3,
        "y": 0,
        "attributes": {"kind": "work"},
    },
    {
        "id_suffix": "cafe",
        "name": "街角咖啡馆",
        "location_type": "cafe",
        "capacity": 6,
        "x": 2,
        "y": 1,
        "attributes": {"kind": "work"},
    },
    {
        "id_suffix": "hospital",
        "name": "海湾医院",
        "location_type": "hospital",
        "capacity": 8,
        "x": 4,
        "y": 2,
        "attributes": {"kind": "work"},
    },
    {
        "id_suffix": "bachelor-apt",
        "name": "镇中公寓",
        "location_type": "home",
        "capacity": 6,
        "x": 0,
        "y": 2,
        "attributes": {"kind": "private"},
    },
    {
        "id_suffix": "mall",
        "name": "港湾商场",
        "location_type": "shop",
        "capacity": 12,
        "x": 3,
        "y": 2,
        "attributes": {"kind": "commercial"},
    },
]

# 地点 ID 映射：agent.yml 中的 home/workplace 值 -> location id suffix
LOCATION_ID_MAP = {
    "apartment": "apartment",
    "demo_home": "apartment",      # alias used in agent.yml
    "bachelor_apt": "bachelor-apt",
    "office": "office",
    "harbor_office": "office",     # alias used in agent.yml
    "cafe": "cafe",
    "corner_cafe": "cafe",          # alias used in agent.yml
    "hospital": "hospital",
    "plaza": "plaza",
    "mall": "mall",
}

# 职业中文映射（key 须与 agent.yml 中的 occupation 字段完全一致）
OCCUPATION_NAMES: dict[str, str] = {
    "insurance clerk": "保险文员",
    "hospital staff": "医院职员",
    "office coworker": "办公室同事",   # friend: occupation = office coworker
    "barista": "咖啡师",
    "shop regular": "常客",            # neighbor: occupation = shop regular
    "resident": "居民",
}

# 工作描述映射
WORK_DESCRIPTIONS: dict[str, str] = {
    "truman": "审核保险理赔、整理客户档案、处理保单变更",
    "spouse": "医院工作人员，协助病房巡查和病历整理",
    "friend": "与 Truman 同一办公室，负责保单录入和客户咨询",
    "alice": "咖啡师，制作咖啡、服务顾客",
    "neighbor": "自由职业者，常在咖啡馆活动",
    "bob": "无固定工作，日常活动比较自由",
}


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
        return OCCUPATION_NAMES.get(occupation, occupation)

    def _get_work_description(self, agent_id: str) -> str:
        """Get work description for an agent."""
        return WORK_DESCRIPTIONS.get(agent_id, "")

    async def seed_demo_run(self, run: SimulationRun) -> None:
        """Seed a demo run from agent configuration files."""
        run_id = run.id

        # 1. 创建地点
        locations: dict[str, Location] = {}
        for loc_config in LOCATION_CONFIGS:
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
            home_location_id = self._resolve_location_id(run_id, config.home, LOCATION_ID_MAP)

            # 解析 workplace_location_id
            workplace_location_id = None
            if config.workplace:
                workplace_location_id = self._resolve_location_id(
                    run_id, config.workplace, LOCATION_ID_MAP
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
                    run_id, initial.initial_location, LOCATION_ID_MAP
                )
                if resolved:
                    current_location_id = resolved

            # 构建 profile
            workplace_name = None
            if config.workplace and config.workplace in LOCATION_ID_MAP:
                workplace_name = locations[LOCATION_ID_MAP[config.workplace]].name

            profile = build_scenario_agent_profile(
                bio=bio,
                agent_config_id=config.id,
                world_role=config.world_role,
                workplace=workplace_name,
                workplace_location_id=workplace_location_id,
                work_description=self._get_work_description(config.id),
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
