from datetime import date

from core.issue_group_executor import revalidate_saved_context_result


def test_saved_complete_difference_is_revalidated_without_network() -> None:
    source = (
        "\uc774\uc5d0 \ub530\ub77c \ub300\uc911 \uc218\ucd9c\uc561\uc774 \ub300\ubbf8 \uc218\ucd9c\uc561\ubcf4\ub2e4 "
        "52\uc5b53500\ub9cc\ub2ec\ub7ec \ub354 \ub9ce\uc558\ub2e4."
    )
    result = revalidate_saved_context_result(
        {
            "claim_id": "C-001",
            "status": "HUMAN_REVIEW",
            "reason_code": "CONTEXT_REQUIRED",
            "official_lookup_attempted": False,
            "children": [
                {
                    "claim_id": "C-001",
                    "admission_route": "CONTEXT_REQUIRED",
                    "twelve_slot_complete": True,
                    "claim": {
                        "claim_id": "C-001",
                        "source_sentence": source,
                        "indicator": "\uc218\ucd9c\uc561",
                        "value": 52.35,
                        "unit": "\uc5b5 \ub2ec\ub7ec",
                        "time": "\uc9c0\ub09c\ud574",
                        "frequency": "\ub144",
                        "region": None,
                        "population": None,
                        "dimension": None,
                        "comparison": {
                            "type": "DIFFERENCE",
                            "current_item": "\ub300\uc911 \uc218\ucd9c\uc561",
                            "reference_item": "\ub300\ubbf8 \uc218\ucd9c\uc561",
                            "current_value": "1330.26",
                            "reference_value": "1277.91",
                            "operand_unit": "\uc5b5 \ub2ec\ub7ec",
                        },
                        "calculation": "DIFFERENCE",
                        "condition": {"direction": "INCREASE"},
                        "source_hint": None,
                        "parse_status": "HOLD",
                        "parse_reason": "AMBIGUOUS_COMPARISON",
                    },
                    "recovery_audit": {},
                }
            ],
        },
        date(2025, 1, 6),
    )

    child = result["children"][0]
    assert result["status"] == "HUMAN_REVIEW"
    assert child["admission_route"] == "CONTEXT_REQUIRED"
    assert child["claim"]["time"] == "2024\ub144"
    assert child["recovery_audit"]["offline_revalidated"] is True
    assert result["official_lookup_attempted"] is False
