from core.claim_group_validator import validate_grouping_plan
from schemas.claim_group import ClaimGroupingPlan, NumericMention


def _mentions() -> list[NumericMention]:
    return [
        NumericMention(mention_id="n1", expression="60%", start=4, end=7),
        NumericMention(mention_id="n2", expression="58%", start=11, end=14),
        NumericMention(mention_id="n3", expression="2%포인트", start=17, end=22),
    ]


def _plan(assignments: list[dict], groups: list[dict] | None = None) -> ClaimGroupingPlan:
    return ClaimGroupingPlan.model_validate(
        {
            "status": "READY",
            "assignments": assignments,
            "groups": groups
            or [{"group_id": "g1", "main_mention_id": "n1"}],
        }
    )


def test_accepts_current_reference_and_change_as_one_claim_group() -> None:
    result = validate_grouping_plan(
        _mentions(),
        _plan(
            [
                {"mention_id": "n1", "role": "MAIN_VALUE", "group_id": "g1"},
                {"mention_id": "n2", "role": "REFERENCE_VALUE", "group_id": "g1"},
                {"mention_id": "n3", "role": "CHANGE_VALUE", "group_id": "g1"},
            ]
        ),
    )

    assert result.valid is True
    assert len(result.groups) == 1
    assert result.groups[0].main_expression == "60%"
    assert result.groups[0].numeric_roles == (
        ("60%", "MAIN_VALUE"),
        ("58%", "REFERENCE_VALUE"),
        ("2%포인트", "CHANGE_VALUE"),
    )


def test_rejects_missing_numeric_mention() -> None:
    result = validate_grouping_plan(
        _mentions(),
        _plan(
            [
                {"mention_id": "n1", "role": "MAIN_VALUE", "group_id": "g1"},
                {"mention_id": "n2", "role": "REFERENCE_VALUE", "group_id": "g1"},
            ]
        ),
    )

    assert result.valid is False
    assert result.reason_code == "GROUPING_MENTION_MISSING"


def test_rejects_unknown_numeric_mention() -> None:
    result = validate_grouping_plan(
        _mentions(),
        _plan(
            [
                {"mention_id": "n1", "role": "MAIN_VALUE", "group_id": "g1"},
                {"mention_id": "n2", "role": "REFERENCE_VALUE", "group_id": "g1"},
                {"mention_id": "n3", "role": "CHANGE_VALUE", "group_id": "g1"},
                {"mention_id": "n4", "role": "CONTEXT_VALUE", "group_id": None},
            ]
        ),
    )

    assert result.valid is False
    assert result.reason_code == "GROUPING_UNKNOWN_MENTION"


def test_rejects_duplicate_assignment() -> None:
    result = validate_grouping_plan(
        _mentions(),
        _plan(
            [
                {"mention_id": "n1", "role": "MAIN_VALUE", "group_id": "g1"},
                {"mention_id": "n1", "role": "REFERENCE_VALUE", "group_id": "g1"},
                {"mention_id": "n2", "role": "REFERENCE_VALUE", "group_id": "g1"},
                {"mention_id": "n3", "role": "CHANGE_VALUE", "group_id": "g1"},
            ]
        ),
    )

    assert result.valid is False
    assert result.reason_code == "GROUPING_DUPLICATE_ASSIGNMENT"


def test_rejects_non_context_number_without_group() -> None:
    result = validate_grouping_plan(
        _mentions(),
        _plan(
            [
                {"mention_id": "n1", "role": "MAIN_VALUE", "group_id": "g1"},
                {"mention_id": "n2", "role": "REFERENCE_VALUE", "group_id": None},
                {"mention_id": "n3", "role": "CONTEXT_VALUE", "group_id": None},
            ]
        ),
    )

    assert result.valid is False
    assert result.reason_code == "GROUPING_MAIN_VALUE_INVALID"


def test_human_review_never_returns_executable_groups() -> None:
    plan = ClaimGroupingPlan.model_validate(
        {
            "status": "HUMAN_REVIEW",
            "reason": "지표 관계가 불명확함",
            "assignments": [],
            "groups": [],
        }
    )

    result = validate_grouping_plan(_mentions(), plan)

    assert result.valid is False
    assert result.groups == ()
    assert result.reason_code == "GROUPING_AMBIGUOUS"
