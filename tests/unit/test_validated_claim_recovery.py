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


def test_reclassifies_source_grounded_count_decrease_as_official_difference() -> None:
    claim = ClaimSchema(
        claim_id="employment-change",
        source_sentence="임시근로자는 전년 같은 달보다 1만9000명 감소했다.",
        indicator="취업자 수", value=19000, unit="명", time="2024년 12월", frequency="월",
        comparison={"type": "YEAR_OVER_YEAR"}, calculation="DIRECT_VALUE",
        condition={"direction": "DECREASE"}, parse_status="AUTO_OK",
    )

    recovered = recover_validated_claim(
        claim, date(2025, 1, 15), source_value_text="1만9000명",
    )

    assert recovered.calculation == "DIFFERENCE"
    assert recovered.comparison == {
        "type": "YEAR_OVER_YEAR",
        "operand_source": "OFFICIAL_EVIDENCE",
    }
    assert recovered.parse_status == "AUTO_OK"


def test_reclassifies_coordinated_count_decrease_target() -> None:
    claim = ClaimSchema(
        claim_id="coordinated-change",
        source_sentence="40대와 50대는 각각 4만9000명, 2만6000명 줄었다.",
        indicator="취업자 수", value=49000, unit="명", time="2025년 3월", frequency="월",
        comparison={"type": "YEAR_OVER_YEAR"}, calculation="DIRECT_VALUE",
        condition={"direction": "DECREASE"}, parse_status="AUTO_OK",
    )

    recovered = recover_validated_claim(
        claim, date(2025, 4, 15), source_value_text="4만9000명",
    )

    assert recovered.calculation == "DIFFERENCE"


def test_does_not_reclassify_direct_level_followed_by_separate_comparison() -> None:
    claim = ClaimSchema(
        claim_id="area-level",
        source_sentence="올해 재배면적은 67만8000ha로 전년 69만8000ha보다 감소했다.",
        indicator="재배 면적", value=678000, unit="ha", time="2024년", frequency="년",
        comparison={"type": "YEAR_OVER_YEAR"}, calculation="DIRECT_VALUE",
        condition={"direction": "DECREASE"}, parse_status="AUTO_OK",
    )

    recovered = recover_validated_claim(
        claim, date(2025, 1, 15), source_value_text="67만8000ha",
    )

    assert recovered.calculation == "DIRECT_VALUE"


def test_reclassifies_non_percent_growth_output_as_source_grounded_difference() -> None:
    claim = ClaimSchema(
        claim_id="employment-change-growth",
        source_sentence="제조업 취업자는 전년 동월 대비 8만3000명 줄었다.",
        indicator="취업자 수", value=83000, unit="명", time="2025년 9월", frequency="월",
        comparison={"type": "YEAR_OVER_YEAR"}, calculation="GROWTH_RATE",
        condition={"direction": "DECREASE"}, parse_status="HOLD",
        parse_reason="CLAIM_UNIT_INCOMPATIBLE",
    )

    recovered = recover_validated_claim(
        claim, date(2025, 10, 17), source_value_text="8만3000명",
    )

    assert recovered.calculation == "DIFFERENCE"
    assert recovered.comparison == {
        "type": "YEAR_OVER_YEAR",
        "operand_source": "OFFICIAL_EVIDENCE",
    }
    assert recovered.parse_status == "AUTO_OK"
    assert recovered.parse_reason is None


def test_reclassifies_non_percent_growth_output_as_source_grounded_level() -> None:
    claim = ClaimSchema(
        claim_id="employment-level-growth",
        source_sentence=(
            "지난달 20대 취업자는 343만5000명으로 "
            "지난해 9월 356만9000명보다 13만4000명 줄었다."
        ),
        indicator="취업자 수", value=3435000, unit="명", time="2025년 9월", frequency="월",
        comparison={"type": "YEAR_OVER_YEAR", "reference_value": "3569000"},
        calculation="GROWTH_RATE", condition={"direction": "DECREASE"},
        parse_status="HOLD", parse_reason="CLAIM_UNIT_INCOMPATIBLE",
    )

    recovered = recover_validated_claim(
        claim, date(2025, 10, 17), source_value_text="343만5000명",
    )

    assert recovered.calculation == "DIRECT_VALUE"
    assert recovered.parse_status == "AUTO_OK"
    assert recovered.parse_reason is None


def test_removes_period_dimension_after_first_month_is_resolved() -> None:
    claim = ClaimSchema(
        claim_id="birth-first-month",
        source_sentence="올해 첫 달 출생아 수가 전년 동월 대비 11.6% 증가했다.",
        indicator="출생아 수", value=11.6, unit="%", time="올해 첫 달",
        frequency="MONTHLY", dimension={"month": "1월"},
        comparison={"type": "YEAR_OVER_YEAR", "reference_period": "전년 동월"},
        calculation="GROWTH_RATE", condition={"direction": "INCREASE"},
        parse_status="AUTO_OK",
    )

    recovered = recover_validated_claim(
        claim, date(2025, 2, 26), source_value_text="11.6%",
    )

    assert recovered.time == "2025년 1월"
    assert recovered.frequency == "월"
    assert recovered.dimension is None
    assert recovered.parse_status == "AUTO_OK"


def test_missing_comparison_basis_is_not_reclassified_without_context() -> None:
    claim = ClaimSchema(
        claim_id="context-change",
        source_sentence="60세 이상 취업자는 37만명 늘었다.",
        indicator="취업자 수 증가", value=370000, unit="명",
        time="2025년 5월", frequency="월", comparison=None,
        calculation="DIRECT_VALUE", condition={"direction": "INCREASE"},
        parse_status="AUTO_OK",
    )

    recovered = recover_validated_claim(
        claim, date(2025, 6, 11), source_value_text="37만명",
    )

    assert recovered.calculation == "DIRECT_VALUE"
    assert recovered.comparison is None


def test_reclassifies_change_amount_with_explicit_context_basis() -> None:
    claim = ClaimSchema(
        claim_id="context-change",
        source_sentence="60세 이상 취업자는 37만명 늘었다.",
        indicator="취업자 수 증가", value=370000, unit="명",
        time="2025년 5월", frequency="월",
        comparison={"비교 연령대": "30대", "비교 증가 수": "132000명"},
        calculation="DIRECT_VALUE", condition={"direction": "INCREASE"},
        parse_status="AUTO_OK",
    )

    recovered = recover_validated_claim(
        claim,
        date(2025, 6, 11),
        source_value_text="37만명",
        context_comparison_type="YEAR_OVER_YEAR",
    )

    assert recovered.calculation == "DIFFERENCE"
    assert recovered.comparison == {
        "type": "YEAR_OVER_YEAR",
        "operand_source": "OFFICIAL_EVIDENCE",
    }


def test_does_not_accept_unsupported_context_basis() -> None:
    claim = ClaimSchema(
        claim_id="context-change", source_sentence="취업자는 37만명 늘었다.",
        indicator="취업자 수", value=370000, unit="명", time="2025년 5월",
        frequency="월", calculation="DIRECT_VALUE",
        condition={"direction": "INCREASE"}, parse_status="AUTO_OK",
    )

    recovered = recover_validated_claim(
        claim, date(2025, 6, 11), source_value_text="37만명",
        context_comparison_type="ITEM_DIFFERENCE",
    )

    assert recovered.calculation == "DIRECT_VALUE"


def _missing_month_claim(*, value: float = 2.2, source: str = "6월 소비자물가 상승률은 2.2%였다.") -> ClaimSchema:
    return ClaimSchema(
        claim_id="previous-month",
        source_sentence=source,
        indicator="소비자물가 상승률",
        value=value,
        unit="%",
        time=None,
        calculation="DIRECT_VALUE",
        parse_status="HOLD",
        parse_reason="MISSING_REQUIRED_SLOTS:time",
    )


def test_readmits_source_grounded_claim_after_safe_previous_month_recovery() -> None:
    recovered = recover_validated_claim(
        _missing_month_claim(),
        date(2025, 7, 2),
    )

    assert recovered.time == "2025년 6월"
    assert recovered.frequency == "월"
    assert recovered.parse_status == "AUTO_OK"
    assert recovered.parse_reason is None


def test_previous_month_recovery_still_requires_target_value_grounding() -> None:
    recovered = recover_validated_claim(
        _missing_month_claim(value=2.3),
        date(2025, 7, 2),
    )

    assert recovered.parse_status == "HOLD"
    assert recovered.parse_reason == "TARGET_VALUE_NOT_IN_SOURCE_SENTENCE"


def test_non_previous_month_remains_held() -> None:
    recovered = recover_validated_claim(
        _missing_month_claim(source="4월 소비자물가 상승률은 2.2%였다."),
        date(2025, 7, 2),
    )

    assert recovered.time is None
    assert recovered.parse_status == "HOLD"
    assert recovered.parse_reason == "MISSING_REQUIRED_SLOTS:time"
