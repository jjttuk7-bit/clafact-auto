import pytest

from core.source_numeric_inventory import inventory_numeric_mentions
from core.source_numeric_role_classifier import classify_numeric_roles
from core.source_target_grounding import repair_exact_target_grounding, trusted_target_expression
from core.validated_claim_recovery import recover_validated_claim
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


@pytest.mark.parametrize(
    ("source", "indicator", "value", "unit", "expression"),
    [
        (
            "지난달 소비자물가지수는 117.42(2020년=100)로 올랐다.",
            "소비자물가지수",
            117.42,
            "지수(2020년=100)",
            "117.42",
        ),
        (
            "대미 수출액은 52억5400만달러였다.",
            "대미 수출액",
            5.254,
            "billion USD",
            "52억5400만달러",
        ),
        (
            "철강 수출액은 35억5000만달러였다.",
            "철강 수출액",
            3_550_000_000,
            "미국 달러",
            "35억5000만달러",
        ),
        (
            "자살률은 인구 10만명당 36.3명이었다.",
            "자살률",
            36.3,
            "명/인구 10만명",
            "36.3명",
        ),
        (
            "남성 일반 혼인율은 9.9건이었다.",
            "일반 혼인율",
            9.9,
            "건/1,000명",
            "9.9건",
        ),
        (
            "30대 초반 출산율은 81.1명을 기록했다.",
            "출산율",
            81.1,
            "명/여성 1000명",
            "81.1명",
        ),
    ],
)
def test_source_numeric_grounding_supports_common_scaled_and_rate_units(
    source: str,
    indicator: str,
    value: float,
    unit: str,
    expression: str,
) -> None:
    result = classify_numeric_roles(
        source_sentence=source,
        mentions=inventory_numeric_mentions(source),
        claim_value=value,
        claim_unit=unit,
        indicator=indicator,
    )

    selected = [item for item in result.assignments if item.auto_target_eligible]
    assert result.target_status == "TARGET_SELECTED"
    assert len(selected) == 1
    assert selected[0].expression == expression

    claim = ClaimSchema(
        claim_id="unit-grounding",
        source_sentence=source,
        indicator=indicator,
        value=value,
        unit=unit,
        time="2025년",
        frequency="년",
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )
    recovered = recover_validated_claim(
        claim,
        None,
        source_value_text=(
            "117.42(2020년=100)"
            if unit == "지수(2020년=100)"
            else expression
        ),
    )
    assert recovered.parse_status == "AUTO_OK"


def test_index_grounding_preserves_the_source_basis_in_the_target_span() -> None:
    source = "지난달 소비자물가지수는 117.42(2020년=100)로 올랐다."
    record = ClaimRegistryRecord(
        article_id="A-INDEX",
        sentence_id="1",
        source_ref="test",
        claim=ClaimSchema(
            claim_id="index-grounding",
            source_sentence=source,
            indicator="소비자물가지수",
            value=117.42,
            unit="지수(2020년=100)",
            time="2025년 10월",
            frequency="월",
            calculation="DIRECT_VALUE",
            parse_status="AUTO_OK",
        ),
        slot_enrichment={"target_link_status": "TARGET_NOT_FOUND_IN_SOURCE"},
    )

    repaired = repair_exact_target_grounding(record)

    assert trusted_target_expression(repaired) == "117.42(2020년=100)"


def test_plain_index_value_is_grounded_by_indicator_predicate() -> None:
    source = "지난달 소비자물가지수는 116.38로 전년 동월 대비 2.1% 올랐다."
    roles = classify_numeric_roles(
        source_sentence=source,
        mentions=inventory_numeric_mentions(source),
        claim_value=116.38,
        claim_unit="지수",
        indicator="소비자물가지수",
    )
    assert roles.target_status == "TARGET_SELECTED"
    assert [item.expression for item in roles.assignments if item.auto_target_eligible] == ["116.38"]

    claim = ClaimSchema(
        claim_id="plain-index", source_sentence=source, indicator="소비자물가지수",
        value=116.38, unit="지수", time="2025년 4월", frequency="월",
        calculation="DIRECT_VALUE", parse_status="AUTO_OK",
    )
    assert recover_validated_claim(claim, None, source_value_text="116.38").parse_status == "AUTO_OK"