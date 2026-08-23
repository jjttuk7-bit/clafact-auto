from datetime import date
from core.validated_claim_recovery import recover_validated_claim
from schemas.claim import ClaimSchema


def test_preserves_accepted_direct_claim_despite_other_numbers_in_sentence() -> None:
    claim = ClaimSchema(
        claim_id="R", source_sentence="올해 67만8000ha로 전년(69만8000ha)보다 감소했다.",
        indicator="재배 면적", value=698000, unit="ha", time="2024년",
        calculation="DIRECT_VALUE", parse_status="AUTO_OK",
    )
    assert recover_validated_claim(claim, date(2025, 8, 1)) == claim


def test_repairs_explicit_difference_comparison_without_resampling() -> None:
    claim = ClaimSchema(
        claim_id="E", source_sentence="취업자는 전년 동월 대비 31만2000명 증가했다.",
        indicator="취업자 수", value=312000, unit="명", time="2025년 9월",
        calculation="DIFFERENCE", comparison={"current_value":"29154000","reference_value":"28842000","operand_unit":"명"},
        condition={"direction":"INCREASE"}, parse_status="HOLD", parse_reason="MISSING_REQUIRED_SLOTS:comparison",
    )
    recovered = recover_validated_claim(claim, date(2025, 10, 17))
    assert recovered.parse_status == "AUTO_OK"
    assert recovered.comparison["type"] == "YEAR_OVER_YEAR"


def test_does_not_invent_missing_time() -> None:
    claim = ClaimSchema(
        claim_id="D", source_sentence="80대 사망자는 전년 대비 400명 줄었다.",
        indicator="사망자 수", value=400, unit="명", time=None,
        calculation="DIFFERENCE", comparison={"type":"YEAR_OVER_YEAR"},
        condition={"direction":"DECREASE"}, parse_status="HOLD", parse_reason="MISSING_REQUIRED_SLOTS:time",
    )
    assert recover_validated_claim(claim, date(2025, 2, 26)).parse_reason == "MISSING_REQUIRED_SLOTS:time"


def test_item_difference_stays_held_until_official_two_cell_plan_exists() -> None:
    claim = ClaimSchema(
        claim_id="D",
        source_sentence="이에 따라 대중 수출액이 대미 수출액보다 52억3500만달러 더 많았다.",
        indicator="수출액",
        value=52.35,
        unit="억 달러",
        time="지난해",
        frequency="년",
        calculation="DIFFERENCE",
        comparison={
            "type": "DIFFERENCE",
            "current_item": "대중 수출액",
            "reference_item": "대미 수출액",
            "current_value": "1330.26",
            "reference_value": "1277.91",
            "operand_unit": "억 달러",
        },
        condition={"direction": "INCREASE"},
        parse_status="HOLD",
        parse_reason="AMBIGUOUS_COMPARISON",
    )

    recovered = recover_validated_claim(claim, date(2025, 1, 6))

    assert recovered.parse_status == "HOLD"
    assert recovered.parse_reason == "CLAIM_COMPARISON_UNSUPPORTED"
    assert recovered.time == "2024년"


def test_does_not_promote_context_value_absent_from_target_sentence() -> None:
    claim = ClaimSchema(
        claim_id="D",
        source_sentence="지난해 역대 최대 수출 실적과 무역수지 흑자를 동시에 기록했다.",
        indicator="수출 실적",
        value=6838,
        unit="억 달러",
        time="2024년",
        frequency="년",
        calculation="DIRECT_VALUE",
        parse_status="HOLD",
        parse_reason="두 개의 독립적인 수치성 주장을 포함함",
    )

    recovered = recover_validated_claim(claim, date(2025, 1, 1))

    assert recovered.parse_status == "HOLD"
    assert recovered.parse_reason == "TARGET_VALUE_NOT_IN_SOURCE_SENTENCE"


def test_does_not_promote_unresolved_same_period_time() -> None:
    claim = ClaimSchema(
        claim_id="D",
        source_sentence="같은 기간 18.2% 늘어난 6만2378대를 수출했다.",
        indicator="수출량",
        value=18.2,
        unit="%",
        time="같은 기간",
        frequency="년",
        calculation="GROWTH_RATE",
        comparison={"type": "YEAR_OVER_YEAR", "reference_period": "2023년 같은 기간"},
        condition={"direction": "INCREASE"},
        parse_status="HOLD",
        parse_reason="AMBIGUOUS_COMPARISON",
    )

    recovered = recover_validated_claim(claim, date(2025, 1, 3))

    assert recovered.parse_status == "HOLD"
    assert recovered.parse_reason == "RELATIVE_TIME_UNRESOLVED"


def test_does_not_reduce_record_high_claim_to_direct_value_only() -> None:
    claim = ClaimSchema(
        claim_id="D",
        source_sentence="반도체 수출액이 1419억달러로 역대 최대치를 기록했다.",
        indicator="수출액",
        value=1419,
        unit="억달러",
        time="2024년",
        frequency="년",
        calculation="DIRECT_VALUE",
        comparison={"type": "RECORD_HIGH"},
        parse_status="HOLD",
        parse_reason="AMBIGUOUS_COMPARISON",
    )

    recovered = recover_validated_claim(claim, date(2025, 1, 2))

    assert recovered.parse_status == "HOLD"
    assert recovered.parse_reason == "RECORD_COMPARISON_REQUIRES_SEPARATE_CLAIM"
