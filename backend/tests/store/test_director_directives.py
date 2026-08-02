from __future__ import annotations

import pytest

from app.sim.action_resolver import ActionResult
from app.store.models import Agent, DirectorDirective, DirectorMemory, SimulationRun
from app.store.repositories import DirectorDirectiveRepository


async def _seed_directive(db_session) -> None:
    db_session.add_all(
        [
            SimulationRun(id="run-1", name="director", status="created"),
            Agent(
                id="actor",
                run_id="run-1",
                name="Actor",
                profile={},
                personality={},
                status={},
                current_plan={},
            ),
            Agent(
                id="subject",
                run_id="run-1",
                name="Subject",
                profile={},
                personality={},
                status={},
                current_plan={},
            ),
            DirectorMemory(
                id="memory-1",
                run_id="run-1",
                tick_no=1,
                scene_goal="soft_check_in",
                target_agent_ids='["actor"]',
            ),
            DirectorDirective(
                id="directive-1",
                run_id="run-1",
                target_agent_id="actor",
                subject_agent_id="subject",
                objective="soft_check_in",
                mode="advisory",
                priority="normal",
                status="active",
                issued_tick=1,
                expires_at_tick=8,
                constraints_json={},
                completion_criteria_json={
                    "action_type": "talk",
                    "target_agent_id": "subject",
                },
                source_memory_id="memory-1",
            ),
        ]
    )
    await db_session.commit()


def _accepted_result(target_agent_id: str) -> ActionResult:
    return ActionResult(
        accepted=True,
        action_type="talk",
        reason="accepted",
        event_payload={
            "director_directive_id": "directive-1",
            "director_disposition": "accepted",
            "target_agent_id": target_agent_id,
        },
    )


@pytest.mark.asyncio
async def test_directive_escalates_then_marks_target_drift(db_session) -> None:
    await _seed_directive(db_session)
    repo = DirectorDirectiveRepository(db_session)

    await repo.apply_results("run-1", 2, [_accepted_result("other")])
    await repo.apply_results("run-1", 3, [_accepted_result("other")])
    directive = await repo.get_for_run("run-1", "directive-1")
    assert directive is not None
    assert directive.mode == "priority"
    assert directive.attempt_count == 2
    assert directive.failure_reason == "progress_stalled_escalated"

    await repo.apply_results("run-1", 4, [_accepted_result("other")])
    await db_session.commit()
    assert directive.status == "failed"
    assert directive.failure_reason == "target_drift"
    assert (await repo.list_needing_replan("run-1"))[0].id == "directive-1"
    memory = await db_session.get(DirectorMemory, "memory-1")
    assert memory is not None
    assert memory.was_executed is True


@pytest.mark.asyncio
async def test_directive_execution_waits_for_delayed_effect_evaluation(db_session) -> None:
    await _seed_directive(db_session)
    repo = DirectorDirectiveRepository(db_session)

    await repo.apply_results("run-1", 2, [_accepted_result("subject")])
    await db_session.commit()

    directive = await repo.get_for_run("run-1", "directive-1")
    memory = await db_session.get(DirectorMemory, "memory-1")
    assert directive is not None
    assert directive.status == "executed"
    assert directive.last_progress_tick == 2
    assert directive.effect_status == "pending"
    assert memory is not None
    assert memory.was_executed is True
    assert memory.effectiveness_score is None

    subject = await db_session.get(Agent, "subject")
    assert subject is not None
    subject.status = {"truman_suspicion_score": 0.0}
    await repo.evaluate_effects("run-1", 3, [subject])
    await db_session.commit()

    assert directive.status == "succeeded"
    assert directive.effect_status == "evaluated"
    assert directive.effectiveness_score == 0.6
    assert directive.evaluated_tick == 3
    assert memory.effectiveness_score == 0.6


@pytest.mark.asyncio
async def test_expired_directive_is_not_reported_as_executed(db_session) -> None:
    await _seed_directive(db_session)
    repo = DirectorDirectiveRepository(db_session)

    await repo.expire_stale("run-1", 9)
    await db_session.commit()

    directive = await repo.get_for_run("run-1", "directive-1")
    memory = await db_session.get(DirectorMemory, "memory-1")
    assert directive is not None
    assert directive.status == "expired"
    assert directive.effect_status == "evaluated"
    assert directive.effectiveness_score == 0.0
    assert memory is not None
    assert memory.was_executed is False
    assert memory.effectiveness_score == 0.0
