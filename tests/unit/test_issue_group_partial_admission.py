from core.issue_group_executor import _remaining_reason


def test_mixed_child_routes_are_recorded_as_partial_admission() -> None:
    reason = _remaining_reason(
        [
            {"admission_route": "KOSIS_PIPELINE_ELIGIBLE"},
            {"admission_route": "STRUCTURAL_HOLD"},
        ]
    )

    assert reason == "PARTIAL_CHILD_ADMISSION"
