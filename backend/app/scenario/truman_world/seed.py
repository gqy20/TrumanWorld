from __future__ import annotations

from typing import TYPE_CHECKING

from app.sim.context import DEFAULT_WORLD_START_TIME
from app.store.models import Agent, Location

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.store.models import SimulationRun


class TrumanWorldSeedBuilder:
    """Builds the default Truman-world demo seed."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def seed_demo_run(self, run: SimulationRun) -> None:
        run_id = run.id

        plaza = Location(
            id=f"{run_id}-plaza",
            run_id=run_id,
            name="Town Plaza",
            location_type="plaza",
            capacity=10,
            x=0,
            y=0,
            attributes={"kind": "social"},
        )
        apartment = Location(
            id=f"{run_id}-apartment",
            run_id=run_id,
            name="Seaside Apartment",
            location_type="home",
            capacity=3,
            x=-1,
            y=0,
            attributes={"kind": "private"},
        )
        office = Location(
            id=f"{run_id}-office",
            run_id=run_id,
            name="Harbor Office",
            location_type="office",
            capacity=6,
            x=2,
            y=0,
            attributes={"kind": "work"},
        )
        cafe = Location(
            id=f"{run_id}-cafe",
            run_id=run_id,
            name="Corner Cafe",
            location_type="cafe",
            capacity=6,
            x=1,
            y=0,
            attributes={"kind": "work"},
        )

        truman = Agent(
            id=f"{run_id}-truman",
            run_id=run_id,
            name="Truman",
            occupation="insurance clerk",
            home_location_id=f"{run_id}-apartment",
            current_location_id=f"{run_id}-apartment",
            current_goal="work",
            personality={"openness": 0.55, "conscientiousness": 0.62},
            profile={
                "bio": "Lives an ordinary life and believes the town is completely normal.",
                "agent_config_id": "truman",
                "world_role": "truman",
                "workplace": "Harbor Office",
                "workplace_location_id": f"{run_id}-office",
                "work_description": "审核保险理赔、整理客户档案、处理保单变更",
            },
            status={"energy": 0.85, "suspicion_score": 0.0},
            current_plan={"morning": "commute", "daytime": "work", "evening": "socialize"},
        )
        spouse = Agent(
            id=f"{run_id}-spouse",
            run_id=run_id,
            name="Meryl",
            occupation="hospital staff",
            home_location_id=f"{run_id}-apartment",
            current_location_id=f"{run_id}-apartment",
            current_goal="work",
            personality={"agreeableness": 0.72, "conscientiousness": 0.7},
            profile={
                "bio": "Keeps Truman's domestic life stable and predictable.",
                "agent_config_id": "spouse",
                "world_role": "cast",
                "workplace": "Hospital",
                "work_description": "医院工作人员，协助病房巡查和病历整理",
            },
            status={"energy": 0.78},
            current_plan={"morning": "prepare_day", "daytime": "work", "evening": "home"},
        )
        friend = Agent(
            id=f"{run_id}-friend",
            run_id=run_id,
            name="Marlon",
            occupation="office coworker",
            home_location_id=f"{run_id}-plaza",
            current_location_id=f"{run_id}-office",
            current_goal="work",
            personality={"agreeableness": 0.68, "openness": 0.48},
            profile={
                "bio": "A familiar friend who often shares Truman's daily routine.",
                "agent_config_id": "friend",
                "world_role": "cast",
                "workplace": "Harbor Office",
                "workplace_location_id": f"{run_id}-office",
                "work_description": "与 Truman 同一办公室，负责保单录入和客户咨询",
            },
            status={"energy": 0.74},
            current_plan={"morning": "work", "daytime": "work", "evening": "socialize"},
        )
        neighbor = Agent(
            id=f"{run_id}-neighbor",
            run_id=run_id,
            name="Lauren",
            occupation="shop regular",
            home_location_id=f"{run_id}-plaza",
            current_location_id=f"{run_id}-cafe",
            current_goal="talk",
            personality={"agreeableness": 0.58, "openness": 0.66},
            profile={
                "bio": "A recurring familiar face around the plaza and cafe.",
                "agent_config_id": "neighbor",
                "world_role": "cast",
                "workplace": None,
                "work_description": "自由职业者，常在咖啡馆活动",
            },
            status={"energy": 0.72},
            current_plan={"morning": "socialize", "daytime": "wander", "evening": "socialize"},
        )

        if "world_start_time" not in (run.metadata_json or {}):
            metadata = dict(run.metadata_json or {})
            metadata["world_start_time"] = DEFAULT_WORLD_START_TIME.isoformat()
            run.metadata_json = metadata

        self.session.add_all([plaza, apartment, office, cafe])
        await self.session.flush()
        self.session.add_all([truman, spouse, friend, neighbor])
        await self.session.commit()
