from core.direct_value_multi_claim_results import build_reinput_child_id


def test_reinput_child_id_preserves_original_identity_but_prevents_collisions() -> None:
    first = build_reinput_child_id("P1", "duplicate", 1)
    second_parent = build_reinput_child_id("P2", "duplicate", 1)
    second_occurrence = build_reinput_child_id("P1", "duplicate", 2)

    assert len({first, second_parent, second_occurrence}) == 3
    assert first == build_reinput_child_id("P1", "duplicate", 1)
