from schemas.claim import ClaimSchema


def test_flags_flattened_processed_food_inflation_indicator() -> None:
    from core.claim_slot_quality import assess_claim_slot_quality

    claim = ClaimSchema(
        claim_id="C1",
        source_sentence="지난달 가공식품 물가는 전년 동월 대비 3.1% 올랐다.",
        indicator="물가상승률",
        value=3.1,
        unit="%",
        time="2025년 3월",
        frequency="월",
        parse_status="AUTO_OK",
    )

    decision = assess_claim_slot_quality(claim)

    assert decision.status == "HOLD"
    assert decision.reason_code == "CLAIM_PARSE_UNCERTAIN"
    assert decision.detected_modifier == "가공식품"


def test_keeps_generic_national_inflation_indicator_eligible() -> None:
    from core.claim_slot_quality import assess_claim_slot_quality

    claim = ClaimSchema(
        claim_id="C2",
        source_sentence="지난달 소비자물가 상승률은 전년 동월 대비 2.1%였다.",
        indicator="물가상승률",
        value=2.1,
        unit="%",
        time="2025년 3월",
        frequency="월",
        parse_status="AUTO_OK",
    )

    decision = assess_claim_slot_quality(claim)

    assert decision.status == "PASS"
    assert decision.reason_code is None
    assert decision.detected_modifier is None


def test_flags_import_amount_misparsed_from_imported_car_registration_share() -> None:
    from core.claim_slot_quality import assess_claim_slot_quality

    claim = ClaimSchema(
        claim_id="C3",
        source_sentence="2022년에도 39.1%로, 40% 가까운 이들이 법인 명의로 수입차를 등록했다.",
        indicator="수입액",
        value=39.1,
        unit="%",
        time="2022",
        frequency="Y",
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )

    decision = assess_claim_slot_quality(claim)

    assert decision.status == "HOLD"
    assert decision.reason_code == "CLAIM_PARSE_UNCERTAIN"
    assert decision.detected_modifier == "수입차 등록 비율"


def test_flags_product_specific_export_when_product_dimension_is_missing() -> None:
    from core.claim_slot_quality import assess_claim_slot_quality

    claim = ClaimSchema(
        claim_id="A01989_15",
        source_sentence="작년 대미 철강 수출액은 35억5000만달러를 기록했다.",
        indicator="수출액",
        value=3_550_000_000,
        unit="달러",
        time="2024",
        frequency="Y",
        dimension={"raw": '{"교역상대국": ["미국"]}'},
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )

    decision = assess_claim_slot_quality(claim)

    assert decision.status == "HOLD"
    assert decision.reason_code == "CLAIM_PARSE_UNCERTAIN"
    assert decision.detected_modifier == "철강"


def test_keeps_country_total_export_eligible_without_product_modifier() -> None:
    from core.claim_slot_quality import assess_claim_slot_quality

    claim = ClaimSchema(
        claim_id="A00312_4",
        source_sentence="지난해 대미 수출액은 1277억8600만달러로 집계됐다.",
        indicator="수출액",
        value=127_786_000_000,
        unit="달러",
        time="2024",
        frequency="Y",
        dimension={"raw": '{"교역상대국": ["미국"]}'},
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )

    decision = assess_claim_slot_quality(claim)

    assert decision.status == "PASS"

def test_flags_total_and_country_export_when_selected_value_scope_disagrees() -> None:
    from core.claim_slot_quality import assess_claim_slot_quality

    claim = ClaimSchema(
        claim_id="A01180_3",
        source_sentence=(
            "지난해 우리나라 수출 6836억달러 중 대미(對美) 수출은 "
            "1278억달러로 18.7%에 달했다."
        ),
        indicator="수출액",
        value=683_600_000_000,
        unit="달러",
        time="2024",
        frequency="Y",
        dimension={"raw": '{"교역상대국": ["미국"]}'},
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )

    decision = assess_claim_slot_quality(claim)

    assert decision.status == "HOLD"
    assert decision.reason_code == "CLAIM_PARSE_UNCERTAIN"
    assert decision.detected_modifier == "국가 총수출/대미 수출 다중 대상"

import pytest


@pytest.mark.parametrize("unit", ["%", "%p", "대", "개"])
def test_flags_non_currency_unit_for_direct_export_amount(unit: str) -> None:
    from core.claim_slot_quality import assess_claim_slot_quality

    claim = ClaimSchema(
        claim_id=f"DIRECT-{unit}",
        source_sentence="수출 관련 지표는 15를 기록했다.",
        indicator="수출액",
        value=15,
        unit=unit,
        time="2024",
        frequency="Y",
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )

    decision = assess_claim_slot_quality(claim)

    assert decision.status == "HOLD"
    assert decision.reason_code == "CLAIM_PARSE_UNCERTAIN"
    assert decision.detected_modifier == f"수출액/비화폐 단위 불일치:{unit}"


def test_keeps_monetary_product_export_direct_value_eligible() -> None:
    from core.claim_slot_quality import assess_claim_slot_quality

    claim = ClaimSchema(
        claim_id="A01642_8",
        source_sentence="실제 지난해 화장품 수출액은 68억달러로 역대 최고를 기록했다.",
        indicator="수출액",
        value=6_800_000_000,
        unit="달러",
        time="2024",
        frequency="Y",
        dimension={"품목": "화장품"},
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )

    decision = assess_claim_slot_quality(claim)

    assert decision.status == "PASS"

def test_flags_currency_value_that_is_not_an_export_amount_target() -> None:
    from core.claim_slot_quality import assess_claim_slot_quality

    claim = ClaimSchema(
        claim_id="A01539_16",
        source_sentence=(
            "3만달러를 넘은 2014년쯤에는 자동차·화학·정유가 "
            "반도체와 함께 수출을 쌍끌이했다."
        ),
        indicator="수출액",
        value=30_000,
        unit="달러",
        time="2014",
        frequency="Y",
        dimension={"raw": '{"품목": ["반도체", "자동차"]}'},
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )

    decision = assess_claim_slot_quality(claim)

    assert decision.status == "HOLD"
    assert decision.reason_code == "CLAIM_PARSE_UNCERTAIN"
    assert decision.detected_modifier == "수출액 대상 표현 없음"


def test_flags_technology_export_as_outside_goods_export_concept() -> None:
    from core.claim_slot_quality import assess_claim_slot_quality

    claim = ClaimSchema(
        claim_id="A01953_7",
        source_sentence="국내 제약 바이오 기술 수출액이 62억달러에 달했다.",
        indicator="수출액",
        value=6_200_000_000,
        unit="달러",
        time="2025",
        frequency="Y",
        dimension={"품목": "바이오"},
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )

    decision = assess_claim_slot_quality(claim)

    assert decision.status == "HOLD"
    assert decision.reason_code == "CLAIM_PARSE_UNCERTAIN"
    assert decision.detected_modifier == "기술 수출액/상품 수출액 개념 불일치"

@pytest.mark.parametrize(
    ("condition", "expected_modifier"),
    [
        (None, "THRESHOLD condition 누락"),
        ({"operator": "GTE"}, "THRESHOLD threshold_value 누락"),
        ({"operator": "EQ", "threshold_value": "100", "threshold_unit": "달러"}, "THRESHOLD operator 불일치:EQ"),
        ({"operator": "GTE", "threshold_value": "많이", "threshold_unit": "달러"}, "THRESHOLD threshold_value 비수치"),
        ({"operator": "GTE", "threshold_value": "100", "threshold_unit": "%"}, "THRESHOLD 단위 불일치:달러/%"),
    ],
)
def test_flags_incomplete_export_threshold_condition(
    condition: dict[str, str] | None, expected_modifier: str,
) -> None:
    from core.claim_slot_quality import assess_claim_slot_quality

    claim = ClaimSchema(
        claim_id="THRESHOLD-BAD",
        source_sentence="지난해 화장품 수출액은 100억달러 이상이었다.",
        indicator="수출액",
        value=10_200_000_000,
        unit="달러",
        time="2024",
        frequency="Y",
        dimension={"품목": "화장품"},
        calculation="THRESHOLD",
        condition=condition,
        parse_status="AUTO_OK",
    )

    decision = assess_claim_slot_quality(claim)

    assert decision.status == "HOLD"
    assert decision.reason_code == "CLAIM_PARSE_UNCERTAIN"
    assert decision.detected_modifier == expected_modifier


def test_keeps_complete_export_threshold_condition_eligible() -> None:
    from core.claim_slot_quality import assess_claim_slot_quality

    claim = ClaimSchema(
        claim_id="THRESHOLD-GOOD",
        source_sentence="지난해 화장품 수출액은 100억달러 이상이었다.",
        indicator="수출액",
        value=10_200_000_000,
        unit="달러",
        time="2024",
        frequency="Y",
        dimension={"품목": "화장품"},
        calculation="THRESHOLD",
        condition={
            "operator": "GTE",
            "threshold_value": "10000000000",
            "threshold_unit": "달러",
        },
        parse_status="AUTO_OK",
    )

    decision = assess_claim_slot_quality(claim)

    assert decision.status == "PASS"

@pytest.mark.parametrize(
    ("updates", "expected_modifier"),
    [
        ({"unit": "%", "value": 27}, "RANK 단위 불일치:%"),
        ({"value": 1.5}, "RANK 순위 비정수:1.5"),
        ({"dimension": {"raw": '{"품목": ["자동차", "반도체"]}'}}, "RANK 대상 품목 복수:2"),
        ({"condition": None}, "RANK condition 누락"),
        ({"condition": {"rank": "1위"}}, "RANK rank_value 누락"),
        ({"condition": {"rank_value": "1"}}, "RANK order 누락"),
        ({"condition": {"rank_value": "1", "order": "TOP", "population_scope": "전체 수출 품목"}}, "RANK order 불일치:TOP"),
        ({"condition": {"rank_value": "2", "order": "DESC", "population_scope": "전체 수출 품목"}}, "RANK value 불일치:1/2"),
        ({"condition": {"rank_value": "1", "order": "DESC"}}, "RANK population_scope 누락"),
    ],
)
def test_flags_incomplete_export_rank_contract(
    updates: dict[str, object], expected_modifier: str,
) -> None:
    from core.claim_slot_quality import assess_claim_slot_quality

    data: dict[str, object] = {
        "claim_id": "RANK-BAD",
        "source_sentence": "지난해 대미 수출에서 자동차는 1위를 기록했다.",
        "indicator": "수출액",
        "value": 1,
        "unit": "위",
        "time": "2024",
        "frequency": "Y",
        "dimension": {"raw": '{"품목": ["자동차"], "교역상대국": ["미국"]}'},
        "calculation": "RANK",
        "condition": {
            "rank_value": "1",
            "order": "DESC",
            "population_scope": "대미 수출 전체 품목",
        },
        "parse_status": "AUTO_OK",
    }
    data.update(updates)
    claim = ClaimSchema(**data)

    decision = assess_claim_slot_quality(claim)

    assert decision.status == "HOLD"
    assert decision.reason_code == "CLAIM_PARSE_UNCERTAIN"
    assert decision.detected_modifier == expected_modifier


def test_keeps_complete_single_target_export_rank_contract_eligible() -> None:
    from core.claim_slot_quality import assess_claim_slot_quality

    claim = ClaimSchema(
        claim_id="RANK-GOOD",
        source_sentence="지난해 대미 수출에서 자동차는 1위를 기록했다.",
        indicator="수출액",
        value=1,
        unit="위",
        time="2024",
        frequency="Y",
        dimension={"raw": '{"품목": ["자동차"], "교역상대국": ["미국"]}'},
        calculation="RANK",
        condition={
            "rank_value": "1",
            "order": "DESC",
            "population_scope": "대미 수출 전체 품목",
        },
        parse_status="AUTO_OK",
    )

    decision = assess_claim_slot_quality(claim)

    assert decision.status == "PASS"
@pytest.mark.parametrize(
    ("updates", "expected_modifier"),
    [
        ({"unit": "달러"}, "GROWTH_RATE 단위 불일치:달러"),
        ({"comparison": None}, "GROWTH_RATE comparison 누락"),
        ({"comparison": {"type": "UNKNOWN"}}, "GROWTH_RATE comparison.type 불일치:UNKNOWN"),
        ({"condition": None}, "GROWTH_RATE direction 누락"),
        (
            {"condition": None, "comparison": {"type": "YEAR_OVER_YEAR", "claimed_operands": "[{'value': 5.1, 'unit': '%'}, {'value': 7.0, 'unit': '%'}]"}},
            "GROWTH_RATE 다중 대상 미분리:3",
        ),
        ({"condition": {"direction": "UP"}}, "GROWTH_RATE direction 불일치:UP"),
        (
            {"comparison": {"type": "YEAR_OVER_YEAR", "claimed_operands": "[{'value': 6.1, 'unit': '%'}]"}},
            "GROWTH_RATE target value 불일치:27.5/6.1",
        ),
        (
            {"comparison": {"type": "YEAR_OVER_YEAR", "claimed_operands": "[{'value': 5.1, 'unit': '%'}, {'value': 7.0, 'unit': '%'}]"}},
            "GROWTH_RATE 다중 대상 미분리:3",
        ),
    ],
)
def test_flags_incomplete_export_growth_rate_contract(
    updates: dict[str, object], expected_modifier: str,
) -> None:
    from core.claim_slot_quality import assess_claim_slot_quality

    data: dict[str, object] = {
        "claim_id": "GROWTH-BAD",
        "source_sentence": "지난해 수출액은 전년 대비 27.5% 증가했다.",
        "indicator": "수출액",
        "value": 27.5,
        "unit": "%",
        "time": "2024",
        "frequency": "Y",
        "comparison": {"type": "YEAR_OVER_YEAR"},
        "calculation": "GROWTH_RATE",
        "condition": {"direction": "INCREASE"},
        "parse_status": "AUTO_OK",
    }
    data.update(updates)
    decision = assess_claim_slot_quality(ClaimSchema(**data))

    assert decision.status == "HOLD"
    assert decision.reason_code == "CLAIM_PARSE_UNCERTAIN"
    assert decision.detected_modifier == expected_modifier


def test_flags_missing_used_car_dimension_in_export_growth_rate() -> None:
    from core.claim_slot_quality import assess_claim_slot_quality

    claim = ClaimSchema(
        claim_id="GROWTH-USED-CAR",
        source_sentence="올해 1분기 중고차 수출액은 지난해보다 31% 증가했다.",
        indicator="수출액",
        value=31,
        unit="%",
        time="2024-Q1",
        frequency="Q",
        comparison={"type": "YEAR_OVER_YEAR"},
        calculation="GROWTH_RATE",
        condition={"direction": "INCREASE"},
        parse_status="AUTO_OK",
    )

    decision = assess_claim_slot_quality(claim)

    assert decision.status == "HOLD"
    assert decision.detected_modifier == "중고차"


def test_keeps_complete_export_growth_rate_contract_eligible() -> None:
    from core.claim_slot_quality import assess_claim_slot_quality

    claim = ClaimSchema(
        claim_id="GROWTH-GOOD",
        source_sentence="올해 1분기 중고차 수출액은 지난해보다 31% 증가했다.",
        indicator="수출액",
        value=31,
        unit="%",
        time="2024-Q1",
        frequency="Q",
        dimension={"품목": "중고차"},
        comparison={"type": "YEAR_OVER_YEAR"},
        calculation="GROWTH_RATE",
        condition={"direction": "INCREASE"},
        parse_status="AUTO_OK",
    )

    assert assess_claim_slot_quality(claim).status == "PASS"
@pytest.mark.parametrize(
    ("updates", "expected_modifier"),
    [
        ({"comparison": None}, "DIFFERENCE comparison 누락"),
        ({"comparison": {"type": "YEAR_OVER_YEAR", "claimed_operands": "[{'value': 0.03, 'unit': '%'}, {'value': 19.8, 'unit': '%'}]"}}, "DIFFERENCE current/reference 미분리"),
        ({"comparison": {"type": "UNKNOWN", "current_value": "19.8", "reference_value": "20.4", "operand_unit": "%"}}, "DIFFERENCE comparison.type 불일치:UNKNOWN"),
        ({"comparison": {"type": "YEAR_OVER_YEAR", "reference_value": "20.4", "operand_unit": "%"}}, "DIFFERENCE current_value 누락"),
        ({"comparison": {"type": "YEAR_OVER_YEAR", "current_value": "19.8", "operand_unit": "%"}}, "DIFFERENCE reference_value 누락"),
        ({"comparison": {"type": "YEAR_OVER_YEAR", "current_value": "19.8", "reference_value": "20.4"}}, "DIFFERENCE operand_unit 누락"),
        ({"unit": "달러"}, "DIFFERENCE 단위 불일치:달러/%"),
        ({"condition": None}, "DIFFERENCE direction 누락"),
        ({"condition": {"direction": "UP"}}, "DIFFERENCE direction 불일치:UP"),
        ({"value": 0.5}, "DIFFERENCE value 불일치:0.5/0.6"),
        ({"condition": {"direction": "INCREASE"}}, "DIFFERENCE direction/value 불일치:INCREASE/DECREASE"),
    ],
)
def test_flags_incomplete_export_difference_contract(
    updates: dict[str, object], expected_modifier: str,
) -> None:
    from core.claim_slot_quality import assess_claim_slot_quality

    data: dict[str, object] = {
        "claim_id": "DIFFERENCE-BAD",
        "source_sentence": "반도체 수출 비중은 19.8%로 전년보다 0.6%포인트 줄었다.",
        "indicator": "수출액",
        "value": 0.6,
        "unit": "%p",
        "time": "2025",
        "frequency": "Y",
        "dimension": {"품목": "반도체"},
        "comparison": {
            "type": "YEAR_OVER_YEAR",
            "current_value": "19.8",
            "reference_value": "20.4",
            "operand_unit": "%",
        },
        "calculation": "DIFFERENCE",
        "condition": {"direction": "DECREASE"},
        "parse_status": "AUTO_OK",
    }
    data.update(updates)
    decision = assess_claim_slot_quality(ClaimSchema(**data))

    assert decision.status == "HOLD"
    assert decision.reason_code == "CLAIM_PARSE_UNCERTAIN"
    assert decision.detected_modifier == expected_modifier


def test_keeps_complete_export_difference_contract_eligible() -> None:
    from core.claim_slot_quality import assess_claim_slot_quality

    claim = ClaimSchema(
        claim_id="DIFFERENCE-GOOD",
        source_sentence="반도체 수출 비중은 19.8%로 전년보다 0.6%포인트 줄었다.",
        indicator="수출액",
        value=0.6,
        unit="%p",
        time="2025",
        frequency="Y",
        dimension={"품목": "반도체"},
        comparison={
            "type": "YEAR_OVER_YEAR",
            "current_value": "19.8",
            "reference_value": "20.4",
            "operand_unit": "%",
        },
        calculation="DIFFERENCE",
        condition={"direction": "DECREASE"},
        parse_status="AUTO_OK",
    )

    assert assess_claim_slot_quality(claim).status == "PASS"