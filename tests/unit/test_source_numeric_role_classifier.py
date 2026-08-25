from core.source_numeric_inventory import inventory_numeric_mentions
from core.source_numeric_role_classifier import classify_numeric_roles


def _roles(source: str, value: float, unit: str, indicator: str) -> list[str]:
    result = classify_numeric_roles(
        source_sentence=source,
        mentions=inventory_numeric_mentions(source),
        claim_value=value,
        claim_unit=unit,
        indicator=indicator,
    )
    return [assignment.role for assignment in result.assignments]


def test_classifies_age_period_and_grounded_main_value() -> None:
    source = "20대 인구는 2020년 703만명이다."

    result = classify_numeric_roles(
        source_sentence=source,
        mentions=inventory_numeric_mentions(source),
        claim_value=7_030_000,
        claim_unit="명",
        indicator="인구",
    )

    assert [assignment.role for assignment in result.assignments] == ["연령", "기간", "대상값"]
    assert result.target_status == "TARGET_SELECTED"
    assert result.assignments[2].auto_target_eligible is True


def test_blocks_duration_and_rank_from_becoming_target() -> None:
    duration = classify_numeric_roles(
        source_sentence="5개월 연속 출생아 수가 늘었다.",
        mentions=inventory_numeric_mentions("5개월 연속 출생아 수가 늘었다."),
        claim_value=5,
        claim_unit="개",
        indicator="출생아 수",
    )
    rank = classify_numeric_roles(
        source_sentence="상위 7개 채널 중 6개가 증가했다.",
        mentions=inventory_numeric_mentions("상위 7개 채널 중 6개가 증가했다."),
        claim_value=7,
        claim_unit="개",
        indicator="채널",
    )

    assert duration.assignments[0].role == "기간"
    assert duration.assignments[0].auto_target_eligible is False
    assert rank.assignments[0].role == "순위"
    assert rank.assignments[0].auto_target_eligible is False


def test_classifies_equivalent_value_and_change_value() -> None:
    equivalent_source = "수출액은 533억6000만달러(약 78조원)였다."
    change_source = "취업자는 전년보다 5만2000명 감소했다."

    assert _roles(equivalent_source, 53_360_000_000, "달러", "수출액") == ["대상값", "환산값"]
    assert _roles(change_source, 52_000, "명", "취업자") == ["증감값"]


def test_excludes_model_identifier_and_selects_statistic() -> None:
    source = "보잉 737 맥스 사고로 189명이 사망했다."

    result = classify_numeric_roles(
        source_sentence=source,
        mentions=inventory_numeric_mentions(source),
        claim_value=189,
        claim_unit="명",
        indicator="사망자 수",
    )

    assert [assignment.role for assignment in result.assignments] == ["제외", "대상값"]
    assert result.assignments[0].exclusion_reason == "MODEL_OR_ORDINAL_CONTEXT"


def test_uses_indicator_proximity_when_same_value_occurs_twice() -> None:
    source = "경제성장률은 2%였고 잠재성장률도 2%였다."

    result = classify_numeric_roles(
        source_sentence=source,
        mentions=inventory_numeric_mentions(source),
        claim_value=2,
        claim_unit="%",
        indicator="경제성장률",
    )

    assert [assignment.auto_target_eligible for assignment in result.assignments] == [True, False]
