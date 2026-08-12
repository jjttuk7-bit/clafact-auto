import pytest

from core.claim_contract import assess_claim_contract
from schemas.claim import ClaimSchema


def claim(**updates: object) -> ClaimSchema:
    payload: dict[str, object] = {
        "claim_id": "C1",
        "source_sentence": "2024년 취업자 수는 2,800만 명이었다.",
        "indicator": "취업자 수",
        "value": 28_000_000,
        "unit": "명",
        "time": "2024",
        "frequency": "년",
        "calculation": "DIRECT_VALUE",
        "parse_status": "AUTO_OK",
    }
    payload.update(updates)
    return ClaimSchema.model_validate(payload)


@pytest.mark.parametrize("status", ["HOLD", "HUMAN_REVIEW"])
def test_contract_preserves_existing_non_auto_claims(status: str) -> None:
    decision = assess_claim_contract(claim(parse_status=status, calculation=None))

    assert decision.status == "PASS"
    assert decision.reason_code is None


def test_complete_direct_value_claim_passes() -> None:
    decision = assess_claim_contract(claim())

    assert decision.status == "PASS"
    assert decision.reason_code is None
    assert decision.missing_slots == ()


def test_auto_claim_requires_common_slots_in_canonical_order() -> None:
    decision = assess_claim_contract(claim(
        indicator=None,
        value=None,
        unit=" ",
        time=None,
        calculation=None,
    ))

    assert decision.status == "HOLD"
    assert decision.missing_slots == (
        "indicator",
        "value",
        "unit",
        "time",
        "calculation",
    )
    assert decision.reason_code == (
        "MISSING_REQUIRED_SLOTS:indicator,value,unit,time,calculation"
    )


def test_unknown_calculation_type_is_held() -> None:
    decision = assess_claim_contract(claim(calculation="PART_TO_WHOLE"))

    assert decision.status == "HOLD"
    assert decision.reason_code == "CLAIM_CALCULATION_UNSUPPORTED"
    assert decision.detail == "PART_TO_WHOLE"


def test_contract_does_not_mutate_source_claim() -> None:
    source = claim(calculation=None)

    assess_claim_contract(source)

    assert source.parse_status == "AUTO_OK"
    assert source.parse_reason is None


def test_complete_growth_rate_claim_passes() -> None:
    decision = assess_claim_contract(claim(
        value=3.2,
        unit="%",
        calculation="GROWTH_RATE",
        comparison={"type": "YEAR_OVER_YEAR"},
        condition={"direction": "INCREASE"},
    ))

    assert decision.status == "PASS"


@pytest.mark.parametrize(
    ("updates", "missing_slot"),
    [
        ({"comparison": None, "condition": {"direction": "INCREASE"}}, "comparison"),
        ({"comparison": {"type": "YEAR_OVER_YEAR"}, "condition": None}, "condition"),
        ({"comparison": {}, "condition": {"direction": "INCREASE"}}, "comparison"),
        ({"comparison": {"type": "YEAR_OVER_YEAR"}, "condition": {}}, "condition"),
    ],
)
def test_growth_rate_requires_comparison_and_direction(
    updates: dict[str, object], missing_slot: str
) -> None:
    decision = assess_claim_contract(claim(
        value=3.2,
        unit="%",
        calculation="GROWTH_RATE",
        **updates,
    ))

    assert decision.status == "HOLD"
    assert decision.missing_slots == (missing_slot,)


def test_growth_rate_rejects_invalid_comparison_type() -> None:
    decision = assess_claim_contract(claim(
        value=3.2,
        unit="%",
        calculation="GROWTH_RATE",
        comparison={"type": "SHARE_OF_TOTAL"},
        condition={"direction": "INCREASE"},
    ))

    assert decision.reason_code == "CLAIM_COMPARISON_UNSUPPORTED"


def test_growth_rate_requires_percent_compatible_unit() -> None:
    decision = assess_claim_contract(claim(
        unit="명",
        calculation="GROWTH_RATE",
        comparison={"type": "YEAR_OVER_YEAR"},
        condition={"direction": "INCREASE"},
    ))

    assert decision.reason_code == "CLAIM_UNIT_INCOMPATIBLE"


def test_complete_difference_claim_passes() -> None:
    decision = assess_claim_contract(claim(
        value=0.3,
        unit="%p",
        calculation="DIFFERENCE",
        comparison={
            "type": "YEAR_OVER_YEAR",
            "current_value": "61.4",
            "reference_value": "61.7",
            "operand_unit": "%",
        },
        condition={"direction": "DECREASE"},
    ))

    assert decision.status == "PASS"


@pytest.mark.parametrize(
    "comparison",
    [
        {"type": "YEAR_OVER_YEAR", "reference_value": "61.7", "operand_unit": "%"},
        {"type": "YEAR_OVER_YEAR", "current_value": "61.4", "operand_unit": "%"},
        {"type": "YEAR_OVER_YEAR", "current_value": "61.4", "reference_value": "61.7"},
    ],
)
def test_difference_requires_explicit_operands(comparison: dict[str, str]) -> None:
    decision = assess_claim_contract(claim(
        value=0.3,
        unit="%p",
        calculation="DIFFERENCE",
        comparison=comparison,
        condition={"direction": "DECREASE"},
    ))

    assert decision.status == "HOLD"
    assert decision.missing_slots == ("comparison",)


def test_complete_share_claim_passes() -> None:
    decision = assess_claim_contract(claim(
        value=27.0,
        unit="%",
        calculation="SHARE",
        comparison={
            "type": "SHARE_OF_TOTAL",
            "numerator": "반도체 수출액",
            "denominator": "전체 수출액",
        },
    ))

    assert decision.status == "PASS"


def test_share_requires_explicit_part_and_whole() -> None:
    decision = assess_claim_contract(claim(
        value=27.0,
        unit="%",
        calculation="SHARE",
        comparison={"type": "SHARE_OF_TOTAL"},
    ))

    assert decision.status == "HOLD"
    assert decision.missing_slots == ("comparison",)


@pytest.mark.parametrize("calculation", ["RATIO", "MULTIPLE"])
def test_complete_ratio_family_claim_passes(calculation: str) -> None:
    decision = assess_claim_contract(claim(
        value=2.4,
        unit="배",
        calculation=calculation,
        comparison={"numerator": "현재값", "denominator": "기준값"},
    ))

    assert decision.status == "PASS"


@pytest.mark.parametrize("calculation", ["RATIO", "MULTIPLE"])
def test_ratio_family_requires_explicit_operands(calculation: str) -> None:
    decision = assess_claim_contract(claim(
        value=2.4,
        unit="배",
        calculation=calculation,
        comparison={"numerator": "현재값"},
    ))

    assert decision.status == "HOLD"
    assert decision.missing_slots == ("comparison",)


def test_complete_rank_claim_passes() -> None:
    decision = assess_claim_contract(claim(
        value=1,
        unit="위",
        calculation="RANK",
        dimension={"품목": "반도체"},
        condition={
            "rank_value": "1",
            "order": "DESC",
            "population_scope": "전체 수출 품목",
        },
    ))

    assert decision.status == "PASS"


@pytest.mark.parametrize(
    "updates",
    [
        {"dimension": None},
        {"condition": None},
        {"condition": {"rank_value": "1", "order": "DESC"}},
        {"value": 1.5},
        {"unit": "%"},
    ],
)
def test_rank_requires_one_explicit_rank_contract(updates: dict[str, object]) -> None:
    rank_updates: dict[str, object] = {
        "value": 1,
        "unit": "위",
        "calculation": "RANK",
        "dimension": {"품목": "반도체"},
        "condition": {
            "rank_value": "1",
            "order": "DESC",
            "population_scope": "전체 수출 품목",
        },
    }
    rank_updates.update(updates)

    decision = assess_claim_contract(claim(**rank_updates))

    assert decision.status == "HOLD"


def test_complete_threshold_claim_passes() -> None:
    decision = assess_claim_contract(claim(
        value=3.2,
        unit="%",
        calculation="THRESHOLD",
        condition={
            "operator": "GT",
            "threshold_value": "3",
            "threshold_unit": "%",
        },
    ))

    assert decision.status == "PASS"


@pytest.mark.parametrize(
    "condition",
    [
        None,
        {"operator": "GT", "threshold_unit": "%"},
        {"operator": "BETWEEN", "threshold_value": "3", "threshold_unit": "%"},
        {"operator": "GT", "threshold_value": "three", "threshold_unit": "%"},
        {"operator": "GT", "threshold_value": "3", "threshold_unit": "명"},
    ],
)
def test_threshold_requires_explicit_compatible_boundary(
    condition: dict[str, str] | None,
) -> None:
    decision = assess_claim_contract(claim(
        value=3.2,
        unit="%",
        calculation="THRESHOLD",
        condition=condition,
    ))

    assert decision.status == "HOLD"
