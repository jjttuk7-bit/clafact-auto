from core.issue_group_executor import normalize_context_result


def _child(disposition: str, *, eligible: bool = False) -> dict[str, object]:
    return {
        "admission_route": (
            "KOSIS_PIPELINE_ELIGIBLE" if eligible else "STRUCTURAL_HOLD"
        ),
        "twelve_slot_complete": eligible,
        "disposition": disposition,
        "disposition_reason": f"REASON_{disposition}",
        "next_route": (
            "OFFICIAL_SEARCH"
            if disposition == "OFFICIAL_VERIFICATION_TARGET"
            else "PRE_VERIFICATION_EXCLUDE"
            if disposition in {"FORECAST_OR_POLICY", "NO_VERIFIABLE_NUMERIC_ASSERTION"}
            else "CONTEXT_REVIEW"
        ),
    }


def test_all_safely_excluded_children_reclassify_parent() -> None:
    result = normalize_context_result(
        {
            "claim_id": "C-1",
            "children": [
                _child("FORECAST_OR_POLICY"),
                _child("NO_VERIFIABLE_NUMERIC_ASSERTION"),
            ],
        }
    )

    assert result["status"] == "RECLASSIFIED"
    assert result["reason_code"] == "PRE_VERIFICATION_RECLASSIFIED"
    assert result["reclassification_result"] == "ALL_RECLASSIFIED"
    assert result["next_route"] == "PRE_VERIFICATION_EXCLUDE"


def test_official_and_excluded_children_make_parent_ready_with_reclassification() -> None:
    result = normalize_context_result(
        {
            "claim_id": "C-1",
            "children": [
                _child("OFFICIAL_VERIFICATION_TARGET", eligible=True),
                _child("NO_VERIFIABLE_NUMERIC_ASSERTION"),
            ],
        }
    )

    assert result["status"] == "PASS"
    assert result["reason_code"] == "CHILDREN_READY_WITH_RECLASSIFICATION"
    assert result["reclassification_result"] == "PARTIAL_RECLASSIFICATION"
    assert result["next_route"] == "OFFICIAL_SEARCH"


def test_context_insufficient_child_keeps_parent_in_review() -> None:
    result = normalize_context_result(
        {
            "claim_id": "C-1",
            "children": [
                _child("OFFICIAL_VERIFICATION_TARGET", eligible=True),
                _child("SOURCE_CONTEXT_INSUFFICIENT"),
            ],
        }
    )

    assert result["status"] == "HUMAN_REVIEW"
    assert result["reason_code"] == "PARTIAL_CHILD_ADMISSION"
    assert result["next_route"] == "CONTEXT_REVIEW"
