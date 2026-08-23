from datetime import date

from core.issue_group_executor import revalidate_saved_context_result
from core.validated_claim_recovery import recover_validated_claim
from schemas.claim import ClaimSchema


def test_auto_ok_record_comparison_is_not_allowed_to_bypass_safety() -> None:
    claim = ClaimSchema(
        claim_id="C",
        source_sentence="The export value was 1419 and set a record high.",
        indicator="export value",
        value=1419,
        unit="USD 100m",
        time="2024",
        frequency="annual",
        calculation="DIRECT_VALUE",
        comparison={"type": "RECORD_HIGH"},
        parse_status="AUTO_OK",
    )

    recovered = recover_validated_claim(claim, date(2025, 1, 2))

    assert recovered.parse_status == "HOLD"
    assert recovered.parse_reason == "RECORD_COMPARISON_REQUIRES_SEPARATE_CLAIM"


def test_article_year_does_not_ground_context_injected_target_value() -> None:
    claim = ClaimSchema(
        claim_id="C",
        source_sentence="2024\ub144 \uc218\ucd9c \uc2e4\uc801\uc740 \uc5ed\ub300 \ucd5c\ub300\uc600\ub2e4.",
        indicator="\uc218\ucd9c \uc2e4\uc801",
        value=6838,
        unit="\uc5b5 \ub2ec\ub7ec",
        time="2024\ub144",
        frequency="\ub144",
        calculation="DIRECT_VALUE",
        parse_status="HOLD",
        parse_reason="AMBIGUOUS_COMPARISON",
    )

    recovered = recover_validated_claim(claim, date(2025, 1, 1))

    assert recovered.parse_status == "HOLD"
    assert recovered.parse_reason == "TARGET_VALUE_NOT_IN_SOURCE_SENTENCE"


def test_saved_hold_downgrades_a_previous_official_route() -> None:
    result = revalidate_saved_context_result(
        {
            "claim_id": "C",
            "official_lookup_attempted": False,
            "children": [{
                "claim_id": "C",
                "admission_route": "KOSIS_PIPELINE_ELIGIBLE",
                "twelve_slot_complete": True,
                "claim": {
                    "claim_id": "C",
                    "source_sentence": "The value was 1419 and set a record high.",
                    "indicator": "export value",
                    "value": 1419,
                    "unit": "USD 100m",
                    "time": "2024",
                    "frequency": "annual",
                    "region": None,
                    "population": None,
                    "dimension": None,
                    "comparison": {"type": "RECORD_HIGH"},
                    "calculation": "DIRECT_VALUE",
                    "condition": None,
                    "source_hint": None,
                    "parse_status": "AUTO_OK",
                    "parse_reason": None,
                },
            }],
        },
        date(2025, 1, 2),
    )

    child = result["children"][0]
    assert child["claim"]["parse_status"] == "HOLD"
    assert child["admission_route"] != "KOSIS_PIPELINE_ELIGIBLE"
    assert result["status"] == "HUMAN_REVIEW"


def test_saved_child_is_grounded_only_against_its_target_expression() -> None:
    result = revalidate_saved_context_result(
        {
            "claim_id": "C",
            "children": [{
                "claim_id": "C-child",
                "admission_route": "KOSIS_PIPELINE_ELIGIBLE",
                "twelve_slot_complete": True,
                "claim": {
                    "claim_id": "C-child",
                    "source_sentence": "\uace0\uc6a9\ub960\uc740 60%\uc600\uace0 \ubb3c\uac00\uc0c1\uc2b9\ub960\uc740 5%\uc600\ub2e4.",
                    "indicator": "\ubb3c\uac00\uc0c1\uc2b9\ub960",
                    "value": 60,
                    "unit": "%",
                    "time": "2024",
                    "frequency": "\ub144",
                    "calculation": "DIRECT_VALUE",
                    "parse_status": "AUTO_OK",
                },
                "recovery_audit": {"target_numeric_expression": "5%"},
            }],
        },
        date(2025, 1, 2),
    )

    child = result["children"][0]
    assert child["claim"]["parse_status"] == "HOLD"
    assert child["claim"]["parse_reason"] == "TARGET_VALUE_NOT_IN_SOURCE_SENTENCE"
    assert child["admission_route"] != "KOSIS_PIPELINE_ELIGIBLE"
