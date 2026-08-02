from app.sim.relationship_policy import compute_relationship_delta


def test_relationship_gain_diminishes_across_conversation_turns() -> None:
    first = compute_relationship_delta(
        event_type="speech",
        world_time=None,
        location_id=None,
        location_type=None,
        conversation_turn_no=1,
    )
    sixth = compute_relationship_delta(
        event_type="speech",
        world_time=None,
        location_id=None,
        location_type=None,
        conversation_turn_no=6,
    )

    assert first is not None
    assert sixth is not None
    assert sixth.familiarity_delta == first.familiarity_delta * 0.2
    assert "diminishing_turn:6" in sixth.modifiers
