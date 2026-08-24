from core.claim_group_normalizer import (
    build_source_anchored_grouping_plan,
    normalize_grouping_plan,
)
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


def test_values_attached_to_distinct_months_become_independent_groups() -> None:
    sentence = "수입 물가지수는 작년 10월(2.1%), 11월(0.9%) 등으로 올랐다."
    first = sentence.index("2.1%")
    second = sentence.index("0.9%")
    mentions = [
        NumericMention(mention_id="n1", expression="2.1%", start=first, end=first + 4),
        NumericMention(mention_id="n2", expression="0.9%", start=second, end=second + 4),
    ]
    plan = _plan(
        [
            {"mention_id": "n1", "role": "MAIN_VALUE", "group_id": "g1"},
            {"mention_id": "n2", "role": "CHANGE_VALUE", "group_id": "g1"},
        ],
        [{"group_id": "g1", "main_mention_id": "n1"}],
    )

    normalized = normalize_grouping_plan(sentence, mentions, plan)

    assert [group.group_id for group in normalized.groups] == ["g1", "g2"]
    assert [group.main_mention_id for group in normalized.groups] == ["n1", "n2"]
    assert [(item.mention_id, item.role, item.group_id) for item in normalized.assignments] == [
        ("n1", "MAIN_VALUE", "g1"),
        ("n2", "MAIN_VALUE", "g2"),
    ]


def test_missing_period_linked_value_is_recovered_as_an_independent_group() -> None:
    sentence = "수입 물가지수는 작년 10월(2.1%), 11월(0.9%) 등으로 올랐다."
    first = sentence.index("2.1%")
    second = sentence.index("0.9%")
    mentions = [
        NumericMention(mention_id="n1", expression="2.1%", start=first, end=first + 4),
        NumericMention(mention_id="n2", expression="0.9%", start=second, end=second + 4),
    ]
    plan = _plan(
        [{"mention_id": "n2", "role": "MAIN_VALUE", "group_id": "g1"}],
        [{"group_id": "g1", "main_mention_id": "n2"}],
    )

    normalized = normalize_grouping_plan(sentence, mentions, plan)

    assert [(item.mention_id, item.role, item.group_id) for item in normalized.assignments] == [
        ("n1", "MAIN_VALUE", "g1"),
        ("n2", "MAIN_VALUE", "g2"),
    ]
    assert [group.main_mention_id for group in normalized.groups] == ["n1", "n2"]


def test_missing_share_value_with_explicit_ownership_cue_is_recovered() -> None:
    sentence = (
        "반도체 수출의 중국 비율이 9%p 이상 줄어 "
        "우리나라 수출의 20%가량을 맡고 있는 핵심 품목의 지형이 변했다."
    )
    first = sentence.index("9%p")
    second = sentence.index("20%")
    mentions = [
        NumericMention(mention_id="n1", expression="9%p", start=first, end=first + 3),
        NumericMention(mention_id="n2", expression="20%", start=second, end=second + 3),
    ]
    plan = _plan(
        [{"mention_id": "n1", "role": "MAIN_VALUE", "group_id": "g1"}],
        [{"group_id": "g1", "main_mention_id": "n1"}],
    )

    normalized = normalize_grouping_plan(sentence, mentions, plan)

    assert [(item.mention_id, item.role, item.group_id) for item in normalized.assignments] == [
        ("n1", "MAIN_VALUE", "g1"),
        ("n2", "MAIN_VALUE", "g2"),
    ]
    assert [group.main_mention_id for group in normalized.groups] == ["n1", "n2"]


def test_ownership_recovery_does_not_guess_without_share_assertion_cue() -> None:
    sentence = "상반기 9%p 줄었고 관련 수치는 20%로 알려졌다."
    first = sentence.index("9%p")
    second = sentence.index("20%")
    mentions = [
        NumericMention(mention_id="n1", expression="9%p", start=first, end=first + 3),
        NumericMention(mention_id="n2", expression="20%", start=second, end=second + 3),
    ]
    plan = _plan(
        [{"mention_id": "n1", "role": "MAIN_VALUE", "group_id": "g1"}],
        [{"group_id": "g1", "main_mention_id": "n1"}],
    )

    normalized = normalize_grouping_plan(sentence, mentions, plan)

    assert [item.mention_id for item in normalized.assignments] == ["n1"]


def test_earlier_duplicate_amount_is_context_when_later_amount_has_equivalent() -> None:
    sentence = (
        "출연료 100만달러 이야기도 있었으나 결혼 비용으로 "
        "100만달러(약 14억7000만원)를 지출했다."
    )
    first = sentence.index("100만달러")
    second = sentence.index("100만달러", first + 1)
    equivalent = sentence.index("14억7000만원")
    mentions = [
        NumericMention(mention_id="n1", expression="100만달러", start=first, end=first + len("100만달러")),
        NumericMention(mention_id="n2", expression="100만달러", start=second, end=second + len("100만달러")),
        NumericMention(mention_id="n3", expression="14억7000만원", start=equivalent, end=equivalent + len("14억7000만원")),
    ]
    plan = _plan(
        [
            {"mention_id": "n1", "role": "EQUIVALENT_VALUE", "group_id": "g1"},
            {"mention_id": "n2", "role": "MAIN_VALUE", "group_id": "g1"},
            {"mention_id": "n3", "role": "EQUIVALENT_VALUE", "group_id": "g1"},
        ],
        [{"group_id": "g1", "main_mention_id": "n2"}],
    )

    normalized = normalize_grouping_plan(sentence, mentions, plan)

    assert [(item.mention_id, item.role, item.group_id) for item in normalized.assignments] == [
        ("n1", "CONTEXT_VALUE", None),
        ("n2", "MAIN_VALUE", "g1"),
        ("n3", "EQUIVALENT_VALUE", "g1"),
    ]


def test_historical_series_uses_latest_value_as_main_and_prior_values_as_references() -> None:
    sentence = "판매량은 1996년 1만315대, 1997년 8136대, 1998년 2075대로 2년 연속 줄었다."
    expressions = ["1만315대", "8136대", "2075대"]
    mentions = []
    for index, expression in enumerate(expressions, start=1):
        start = sentence.index(expression)
        mentions.append(NumericMention(
            mention_id=f"n{index}",
            expression=expression,
            start=start,
            end=start + len(expression),
        ))
    plan = _plan(
        [
            {"mention_id": "n1", "role": "REFERENCE_VALUE", "group_id": "g1"},
            {"mention_id": "n2", "role": "CHANGE_VALUE", "group_id": "g1"},
            {"mention_id": "n3", "role": "MAIN_VALUE", "group_id": "g1"},
        ],
        [{"group_id": "g1", "main_mention_id": "n3"}],
    )

    normalized = normalize_grouping_plan(sentence, mentions, plan)

    assert [(item.mention_id, item.role, item.group_id) for item in normalized.assignments] == [
        ("n1", "REFERENCE_VALUE", "g1"),
        ("n2", "REFERENCE_VALUE", "g1"),
        ("n3", "MAIN_VALUE", "g1"),
    ]


def test_one_value_shared_by_coordinated_each_indicators_is_held() -> None:
    sentence = (
        "건설업 취업자는 15만7000명 줄었고, 제조업과 도소매업 감소폭도 "
        "각각 10만명에 육박했다."
    )
    first = sentence.index("15만7000명")
    second = sentence.index("10만명")
    mentions = [
        NumericMention(mention_id="n1", expression="15만7000명", start=first, end=first + len("15만7000명")),
        NumericMention(mention_id="n2", expression="10만명", start=second, end=second + len("10만명")),
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

    assert normalized.status == "HUMAN_REVIEW"
    assert normalized.reason == "GROUPING_COORDINATED_EACH_AMBIGUOUS"
    assert normalized.assignments == []
    assert normalized.groups == []


def test_coordinated_each_with_one_value_per_indicator_is_not_held() -> None:
    sentence = "남성과 여성은 각각 10만명, 8만명 감소했다."
    first = sentence.index("10만명")
    second = sentence.index("8만명")
    mentions = [
        NumericMention(mention_id="n1", expression="10만명", start=first, end=first + len("10만명")),
        NumericMention(mention_id="n2", expression="8만명", start=second, end=second + len("8만명")),
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

    assert normalized.status == "READY"


def test_source_anchored_fallback_separates_change_and_owned_share() -> None:
    sentence = (
        "반도체 수출의 중국 비율이 9%p 이상 줄어 "
        "우리나라 수출의 20%가량을 맡고 있는 핵심 품목의 지형이 변했다."
    )
    first = sentence.index("9%p")
    second = sentence.index("20%")
    mentions = [
        NumericMention(mention_id="n1", expression="9%p", start=first, end=first + len("9%p")),
        NumericMention(mention_id="n2", expression="20%", start=second, end=second + len("20%")),
    ]

    plan = build_source_anchored_grouping_plan(sentence, mentions)

    assert plan is not None
    assert [(item.mention_id, item.role, item.group_id) for item in plan.assignments] == [
        ("n1", "MAIN_VALUE", "g1"),
        ("n2", "MAIN_VALUE", "g2"),
    ]


def test_source_anchored_fallback_refuses_uncued_percentages() -> None:
    sentence = "관련 비율은 9%와 20%로 알려졌다."
    first = sentence.index("9%")
    second = sentence.index("20%")
    mentions = [
        NumericMention(mention_id="n1", expression="9%", start=first, end=first + len("9%")),
        NumericMention(mention_id="n2", expression="20%", start=second, end=second + len("20%")),
    ]

    assert build_source_anchored_grouping_plan(sentence, mentions) is None
