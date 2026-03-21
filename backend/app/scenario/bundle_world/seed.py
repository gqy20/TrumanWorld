from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from app.agent.registry import AgentRegistry
from app.infra.settings import get_settings
from app.scenario.bundle_registry import resolve_agents_root_for_scenario
from app.scenario.bundle_world.types import build_agent_profile
from app.scenario.runtime.world_config import load_world_config
from app.scenario.runtime_config import build_runtime_role_semantics
from app.sim.context import DEFAULT_WORLD_START_TIME
from app.store.models import Agent, Location, Relationship

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.store.models import SimulationRun

_WORLD_CONFIG_CACHE: dict[str, dict] = {}


def _get_world_config(scenario_id: str) -> dict:
    if scenario_id not in _WORLD_CONFIG_CACHE:
        _WORLD_CONFIG_CACHE[scenario_id] = load_world_config(scenario_id)
    return _WORLD_CONFIG_CACHE[scenario_id]


def _get_location_configs(scenario_id: str) -> list[dict]:
    return _get_world_config(scenario_id).get("locations", [])


def _get_location_id_map(scenario_id: str) -> dict:
    return _get_world_config(scenario_id).get("location_id_map", {})


def _get_occupation_names(scenario_id: str) -> dict[str, str]:
    return _get_world_config(scenario_id).get("occupation_names", {})


class BundleWorldSeedBuilder:
    def __init__(
        self,
        session: AsyncSession,
        registry: AgentRegistry | None = None,
        *,
        scenario_id: str = "narrative_world",
    ) -> None:
        self.session = session
        self.scenario_id = scenario_id
        settings = get_settings()
        self.registry = registry or AgentRegistry(
            resolve_agents_root_for_scenario(scenario_id, project_root=settings.project_root)
        )

    def _build_location_id(self, run_id: str, suffix: str) -> str:
        return f"{run_id}-{suffix}"

    def _resolve_location_id(
        self,
        run_id: str,
        location_key: str | None,
        location_id_map: dict[str, str],
    ) -> str | None:
        if location_key is None:
            return None
        suffix = location_id_map.get(location_key, location_key)
        return self._build_location_id(run_id, suffix)

    def _get_occupation_name(self, occupation: str) -> str:
        return _get_occupation_names(self.scenario_id).get(occupation, occupation)

    async def seed_demo_run(self, run: SimulationRun) -> None:
        run_id = run.id
        semantics = build_runtime_role_semantics(self.scenario_id)

        locations: dict[str, Location] = {}
        for loc_config in _get_location_configs(self.scenario_id):
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

        agent_configs = self.registry.list_configs()
        agents: dict[str, Agent] = {}

        for config in agent_configs:
            initial = self.registry.get_initial(config.id)
            bio = self.registry.get_bio(config.id) or ""
            location_id_map = _get_location_id_map(self.scenario_id)
            home_location_id = self._resolve_location_id(run_id, config.home, location_id_map)

            workplace_location_id = None
            if config.workplace:
                workplace_location_id = self._resolve_location_id(
                    run_id, config.workplace, location_id_map
                )

            current_location_id = home_location_id
            initial_location = initial.spawn.location or initial.initial_location
            initial_goal = initial.spawn.goal or initial.initial_goal

            if initial_location == "workplace" and workplace_location_id:
                current_location_id = workplace_location_id
            elif initial_location == "home" and home_location_id:
                current_location_id = home_location_id
            elif initial_location:
                resolved = self._resolve_location_id(run_id, initial_location, location_id_map)
                if resolved:
                    current_location_id = resolved

            workplace_name = None
            if config.workplace and config.workplace in location_id_map:
                workplace_name = locations[location_id_map[config.workplace]].name

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

            status_extras = initial.status.model_extra or {}
            alert_value = status_extras.get(semantics.alert_metric)
            if alert_value is None:
                alert_value = initial.status.alert_score

            status = {"energy": initial.status.energy}
            if float(alert_value or 0.0) > 0 or config.world_role == semantics.subject_role:
                status[semantics.alert_metric] = float(alert_value or 0.0)

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
                current_goal=initial_goal,
                personality=config.personality,
                profile=profile,
                status=status,
                current_plan=current_plan,
            )
            agents[config.id] = agent

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

        if "world_start_time" not in (run.metadata_json or {}):
            metadata = dict(run.metadata_json or {})
            metadata["world_start_time"] = DEFAULT_WORLD_START_TIME.isoformat()
            run.metadata_json = metadata

        self.session.add_all(list(locations.values()))
        await self.session.flush()
        self.session.add_all(list(agents.values()))
        await self.session.flush()
        if relationships:
            self.session.add_all(relationships)
        await self.session.commit()
