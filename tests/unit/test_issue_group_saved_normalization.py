from core.issue_group_executor import normalize_context_result


def test_saved_mixed_children_are_normalized_without_external_rerun() -> None:
    result = normalize_context_result(
        {
            "claim_id": "C-001",
            "status": "HUMAN_REVIEW",
            "reason_code": "KOSIS_PIPELINE_ELIGIBLE",
            "children": [
                {
                    "admission_route": "KOSIS_PIPELINE_ELIGIBLE",
                    "twelve_slot_complete": True,
                },
                {
                    "admission_route": "STRUCTURAL_HOLD",
                    "twelve_slot_complete": False,
                },
            ],
        }
    )

    assert result["reason_code"] == "PARTIAL_CHILD_ADMISSION"
