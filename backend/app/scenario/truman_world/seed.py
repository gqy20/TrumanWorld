from __future__ import annotations

from uuid import uuid4

from typing import TYPE_CHECKING

from app.sim.context import DEFAULT_WORLD_START_TIME
from app.scenario.truman_world.types import build_scenario_agent_profile
from app.store.models import Agent, Location, Relationship

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.store.models import SimulationRun


# =============================================================================
# 初始关系定义：定义角色之间的初始关系
# =============================================================================

INITIAL_RELATIONSHIPS = {
    # Truman 的关系
    ("truman", "spouse"): {
        "familiarity": 0.95,
        "trust": 0.9,
        "affinity": 0.85,
        "relation_type": "family",
    },
    ("truman", "friend"): {
        "familiarity": 0.75,
        "trust": 0.7,
        "affinity": 0.65,
        "relation_type": "close_friend",
    },
    ("truman", "alice"): {
        "familiarity": 0.5,
        "trust": 0.4,
        "affinity": 0.4,
        "relation_type": "acquaintance",
    },
    ("truman", "neighbor"): {
        "familiarity": 0.2,
        "trust": 0.1,
        "affinity": 0.15,
        "relation_type": "stranger",
    },
    # Meryl 的关系
    ("spouse", "truman"): {
        "familiarity": 0.95,
        "trust": 0.9,
        "affinity": 0.85,
        "relation_type": "family",
    },
    ("spouse", "friend"): {
        "familiarity": 0.4,
        "trust": 0.35,
        "affinity": 0.3,
        "relation_type": "acquaintance",
    },
    ("spouse", "alice"): {
        "familiarity": 0.35,
        "trust": 0.3,
        "affinity": 0.3,
        "relation_type": "acquaintance",
    },
    ("spouse", "neighbor"): {
        "familiarity": 0.1,
        "trust": 0.1,
        "affinity": 0.1,
        "relation_type": "stranger",
    },
    # Marlon 的关系
    ("friend", "truman"): {
        "familiarity": 0.75,
        "trust": 0.7,
        "affinity": 0.65,
        "relation_type": "close_friend",
    },
    ("friend", "spouse"): {
        "familiarity": 0.4,
        "trust": 0.35,
        "affinity": 0.3,
        "relation_type": "acquaintance",
    },
    ("friend", "alice"): {
        "familiarity": 0.65,
        "trust": 0.55,
        "affinity": 0.6,
        "relation_type": "housemate",
    },
    ("friend", "neighbor"): {
        "familiarity": 0.6,
        "trust": 0.5,
        "affinity": 0.55,
        "relation_type": "housemate",
    },
    # Alice 的关系
    ("alice", "truman"): {
        "familiarity": 0.5,
        "trust": 0.4,
        "affinity": 0.4,
        "relation_type": "acquaintance",
    },
    ("alice", "friend"): {
        "familiarity": 0.65,
        "trust": 0.55,
        "affinity": 0.6,
        "relation_type": "housemate",
    },
    ("alice", "neighbor"): {
        "familiarity": 0.7,
        "trust": 0.6,
        "affinity": 0.65,
        "relation_type": "housemate",
    },
    ("alice", "spouse"): {
        "familiarity": 0.2,
        "trust": 0.15,
        "affinity": 0.2,
        "relation_type": "stranger",
    },
    # Lauren 的关系
    ("neighbor", "alice"): {
        "familiarity": 0.7,
        "trust": 0.6,
        "affinity": 0.65,
        "relation_type": "housemate",
    },
    ("neighbor", "truman"): {
        "familiarity": 0.2,
        "trust": 0.1,
        "affinity": 0.15,
        "relation_type": "stranger",
    },
    ("neighbor", "friend"): {
        "familiarity": 0.6,
        "trust": 0.5,
        "affinity": 0.55,
        "relation_type": "housemate",
    },
    ("neighbor", "spouse"): {
        "familiarity": 0.1,
        "trust": 0.1,
        "affinity": 0.1,
        "relation_type": "stranger",
    },
    # Bob 的关系
    ("bob", "truman"): {
        "familiarity": 0.2,
        "trust": 0.1,
        "affinity": 0.15,
        "relation_type": "stranger",
    },
    ("bob", "spouse"): {
        "familiarity": 0.1,
        "trust": 0.1,
        "affinity": 0.1,
        "relation_type": "stranger",
    },
    ("bob", "friend"): {
        "familiarity": 0.3,
        "trust": 0.25,
        "affinity": 0.25,
        "relation_type": "acquaintance",
    },
    ("bob", "alice"): {
        "familiarity": 0.3,
        "trust": 0.25,
        "affinity": 0.25,
        "relation_type": "acquaintance",
    },
    ("bob", "neighbor"): {
        "familiarity": 0.4,
        "trust": 0.35,
        "affinity": 0.35,
        "relation_type": "acquantee",
    },
}


class TrumanWorldSeedBuilder:
    """Builds the default Truman-world demo seed."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def seed_demo_run(self, run: SimulationRun) -> None:
        run_id = run.id

        plaza = Location(
            id=f"{run_id}-plaza",
            run_id=run_id,
            name="小镇广场",
            location_type="plaza",
            capacity=10,
            x=1,
            y=2,
            attributes={"kind": "social"},
        )
        apartment = Location(
            id=f"{run_id}-apartment",
            run_id=run_id,
            name="海滨公寓",
            location_type="home",
            capacity=3,
            x=0,
            y=0,
            attributes={"kind": "private"},
        )
        office = Location(
            id=f"{run_id}-office",
            run_id=run_id,
            name="港务办公室",
            location_type="office",
            capacity=6,
            x=3,
            y=0,
            attributes={"kind": "work"},
        )
        cafe = Location(
            id=f"{run_id}-cafe",
            run_id=run_id,
            name="街角咖啡馆",
            location_type="cafe",
            capacity=6,
            x=2,
            y=1,
            attributes={"kind": "work"},
        )
        hospital = Location(
            id=f"{run_id}-hospital",
            run_id=run_id,
            name="海湾医院",
            location_type="hospital",
            capacity=8,
            x=4,
            y=2,
            attributes={"kind": "work"},
        )
        bachelor_apt = Location(
            id=f"{run_id}-bachelor-apt",
            run_id=run_id,
            name="镇中公寓",
            location_type="home",
            capacity=6,
            x=0,
            y=2,
            attributes={"kind": "private"},
        )
        mall = Location(
            id=f"{run_id}-mall",
            run_id=run_id,
            name="港湾商场",
            location_type="shop",
            capacity=12,
            x=3,
            y=2,
            attributes={"kind": "commercial"},
        )

        truman = Agent(
            id=f"{run_id}-truman",
            run_id=run_id,
            name="Truman",
            occupation="保险文员",
            home_location_id=f"{run_id}-apartment",
            current_location_id=f"{run_id}-apartment",
            current_goal="work",
            personality={"openness": 0.55, "conscientiousness": 0.62},
            profile=build_scenario_agent_profile(
                bio="过着平凡的生活，相信小镇完全正常。",
                agent_config_id="truman",
                world_role="truman",
                workplace="港务办公室",
                workplace_location_id=f"{run_id}-office",
                work_description="审核保险理赔、整理客户档案、处理保单变更",
            ),
            status={"energy": 0.85, "suspicion_score": 0.0},
            current_plan={"morning": "commute", "daytime": "work", "evening": "socialize"},
        )
        spouse = Agent(
            id=f"{run_id}-spouse",
            run_id=run_id,
            name="Meryl",
            occupation="医院职员",
            home_location_id=f"{run_id}-apartment",
            current_location_id=f"{run_id}-apartment",
            current_goal="work",
            personality={"agreeableness": 0.72, "conscientiousness": 0.7},
            profile=build_scenario_agent_profile(
                bio="维持 Truman 的家庭生活稳定且可预测。",
                agent_config_id="spouse",
                world_role="cast",
                workplace="医院",
                workplace_location_id=f"{run_id}-hospital",
                work_description="医院工作人员，协助病房巡查和病历整理",
            ),
            status={"energy": 0.78},
            current_plan={"morning": "prepare_day", "daytime": "work", "evening": "home"},
        )
        friend = Agent(
            id=f"{run_id}-friend",
            run_id=run_id,
            name="Marlon",
            occupation="办公室同事",
            home_location_id=f"{run_id}-bachelor-apt",
            current_location_id=f"{run_id}-bachelor-apt",
            current_goal="commute",
            personality={"agreeableness": 0.68, "openness": 0.48},
            profile=build_scenario_agent_profile(
                bio="一个熟悉的朋友，经常和 Truman 分享日常生活。",
                agent_config_id="friend",
                world_role="cast",
                workplace="港务办公室",
                workplace_location_id=f"{run_id}-office",
                work_description="与 Truman 同一办公室，负责保单录入和客户咨询",
            ),
            status={"energy": 0.74},
            current_plan={"morning": "work", "daytime": "work", "evening": "socialize"},
        )
        neighbor = Agent(
            id=f"{run_id}-neighbor",
            run_id=run_id,
            name="Lauren",
            occupation="常客",
            home_location_id=f"{run_id}-bachelor-apt",
            current_location_id=f"{run_id}-bachelor-apt",
            current_goal="wander",
            personality={"agreeableness": 0.58, "openness": 0.66},
            profile=build_scenario_agent_profile(
                bio="广场和咖啡馆的常客，熟悉的面孔。",
                agent_config_id="neighbor",
                world_role="cast",
                work_description="自由职业者，常在咖啡馆活动",
            ),
            status={"energy": 0.72},
            current_plan={"morning": "socialize", "daytime": "wander", "evening": "socialize"},
        )
        alice = Agent(
            id=f"{run_id}-alice",
            run_id=run_id,
            name="Alice",
            occupation="咖啡师",
            home_location_id=f"{run_id}-cafe",
            current_location_id=f"{run_id}-cafe",
            current_goal="work",
            personality={"openness": 0.7, "conscientiousness": 0.8},
            profile=build_scenario_agent_profile(
                bio="在街角咖啡馆工作，熟悉常客。",
                agent_config_id="alice",
                world_role="cast",
                workplace="街角咖啡馆",
                workplace_location_id=f"{run_id}-cafe",
                work_description="咖啡师，制作咖啡、服务顾客",
            ),
            status={"energy": 0.8},
            current_plan={"morning": "work", "daytime": "work", "evening": "rest"},
        )
        bob = Agent(
            id=f"{run_id}-bob",
            run_id=run_id,
            name="Bob",
            occupation="居民",
            home_location_id=f"{run_id}-bachelor-apt",
            current_location_id=f"{run_id}-bachelor-apt",
            current_goal="wander",
            personality={"agreeableness": 0.6, "openness": 0.5},
            profile=build_scenario_agent_profile(
                bio="小镇普通居民，经常在镇中心和咖啡馆附近活动。",
                agent_config_id="bob",
                world_role="cast",
                work_description="无固定工作，日常活动比较自由",
            ),
            status={"energy": 0.75},
            current_plan={"morning": "wander", "daytime": "wander", "evening": "socialize"},
        )

        # 创建初始关系
        agent_id_map = {
            "truman": truman.id,
            "spouse": spouse.id,
            "friend": friend.id,
            "neighbor": neighbor.id,
            "alice": alice.id,
            "bob": bob.id,
        }
        relationships = []
        for (from_agent, to_agent), attrs in INITIAL_RELATIONSHIPS.items():
            relationships.append(
                Relationship(
                    id=str(uuid4()),
                    run_id=run_id,
                    agent_id=agent_id_map[from_agent],
                    other_agent_id=agent_id_map[to_agent],
                    familiarity=attrs["familiarity"],
                    trust=attrs["trust"],
                    affinity=attrs["affinity"],
                    relation_type=attrs["relation_type"],
                )
            )

        if "world_start_time" not in (run.metadata_json or {}):
            metadata = dict(run.metadata_json or {})
            metadata["world_start_time"] = DEFAULT_WORLD_START_TIME.isoformat()
            run.metadata_json = metadata

        self.session.add_all([plaza, apartment, office, cafe, hospital, bachelor_apt, mall])
        await self.session.flush()
        self.session.add_all([truman, spouse, friend, neighbor, alice, bob])
        await self.session.flush()
        self.session.add_all(relationships)
        await self.session.commit()
