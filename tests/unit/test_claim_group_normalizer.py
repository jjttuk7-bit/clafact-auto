from core.claim_group_normalizer import normalize_grouping_plan
from schemas.claim_group import ClaimGroupingPlan, NumericMention


def _plan(assignments: list[dict], groups: list[dict]) -> ClaimGroupingPlan:
    return ClaimGroupingPlan.model_validate(
        {"status": "READY", "assignments": assignments, "groups": groups}
    )


def test_change_only_group_anchor_becomes_the_main_claim_value() -> None:
    mentions = [NumericMention(mention_id="n1", expression="15만명", start=5, end=9)]
    plan = _plan(
        [{"mention_id": "n1", "role": "CHANGE_VALUE", "group_id": "g1"}],
        [{"group_id": "g1", "main_mention_id": "n1"}],
    )

    normalized = normalize_grouping_plan("취업자는 15만명 감소했다.", mentions, plan)

    assert normalized.assignments[0].role == "MAIN_VALUE"


def test_context_value_is_removed_from_a_claim_group() -> None:
    mentions = [
        NumericMention(mention_id="n1", expression="1개월", start=0, end=3),
        NumericMention(mention_id="n2", expression="15만명", start=6, end=10),
    ]
    plan = _plan(
        [
            {"mention_id": "n1", "role": "CONTEXT_VALUE", "group_id": "g1"},
            {"mention_id": "n2", "role": "MAIN_VALUE", "group_id": "g1"},
        ],
        [{"group_id": "g1", "main_mention_id": "n2"}],
    )

    normalized = normalize_grouping_plan("1개월 동안 15만명 감소", mentions, plan)

    assert normalized.assignments[0].group_id is None


def test_parenthetical_comparison_amount_is_merged_as_reference_value() -> None:
    sentence = "둘을 합치면 17만9000명으로, 전체 취업자 증가 규모(15만9000명)를 뛰어넘은 것이다."
    first = sentence.index("17만9000명")
    second = sentence.index("15만9000명")
    mentions = [
        NumericMention(mention_id="n1", expression="17만9000명", start=first, end=first + 8),
        NumericMention(mention_id="n2", expression="15만9000명", start=second, end=second + 8),
    ]
    plan = _plan(
        [
            {"mention_id": "n1", "role": "MAIN_VALUE", "group_id": "g1"},
            {"mention_id": "n2", "role": "MAIN_VALUE", "group_id": "g2"},
        ],
        [
            {"group_id": "g1", "main_mention_id": "n1"},
            {"group_id": "g2", "main_mention_id": "n2"},
        ],
    )

    normalized = normalize_grouping_plan(sentence, mentions, plan)

    assert len(normalized.groups) == 1
    assert normalized.assignments[1].role == "REFERENCE_VALUE"
    assert normalized.assignments[1].group_id == "g1"


def test_two_independent_values_are_not_merged_without_cross_value_cue() -> None:
    sentence = "남성은 15만명 감소했고 여성은 12만명 감소했다."
    mentions = [
        NumericMention(mention_id="n1", expression="15만명", start=4, end=8),
        NumericMention(mention_id="n2", expression="12만명", start=15, end=19),
    ]
    plan = _plan(
        [
            {"mention_id": "n1", "role": "CHANGE_VALUE", "group_id": "g1"},
            {"mention_id": "n2", "role": "CHANGE_VALUE", "group_id": "g2"},
        ],
        [
            {"group_id": "g1", "main_mention_id": "n1"},
            {"group_id": "g2", "main_mention_id": "n2"},
        ],
    )

    normalized = normalize_grouping_plan(sentence, mentions, plan)

    assert len(normalized.groups) == 2
    assert [assignment.role for assignment in normalized.assignments] == [
        "MAIN_VALUE",
        "MAIN_VALUE",
    ]
