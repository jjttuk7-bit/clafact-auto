import pytest

from core.dynamic_kosis_verifier import _claim_tolerance
from schemas.claim import ClaimSchema


def _percent_claim(source_sentence: str, value: float) -> ClaimSchema:
    return ClaimSchema(
        claim_id="precision",
        source_sentence=source_sentence,
        indicator="취업자 수",
        value=value,
        unit="%",
        time="2024년 12월",
        frequency="MONTHLY",
        parse_status="AUTO_OK",
    )


def test_one_decimal_percent_claim_uses_half_of_reported_unit() -> None:
    claim = _percent_claim(
        "2024년 12월 취업자 수는 전년 동월 대비 0.2% 감소했다.",
        -0.2,
    )

    assert _claim_tolerance(claim) == pytest.approx(0.05)


def test_two_decimal_percent_claim_uses_half_of_reported_unit() -> None:
    claim = _percent_claim("고용률은 전년보다 1.23% 증가했다.", 1.23)

    assert _claim_tolerance(claim) == pytest.approx(0.005)


def test_integer_percent_claim_uses_half_percentage_point() -> None:
    claim = _percent_claim("비중은 3%였다.", 3.0)

    assert _claim_tolerance(claim) == pytest.approx(0.5)


def test_scaled_count_claim_uses_reported_precision() -> None:
    claim = ClaimSchema(
        claim_id="scaled-count", source_sentence="2025년 5월 취업자는 2916만명이었다.",
        indicator="취업자 수", value=2916.0, unit="만명", time="2025년 5월",
        frequency="월", calculation="DIRECT_VALUE", parse_status="AUTO_OK",
    )
    assert _claim_tolerance(claim) == pytest.approx(0.5)


def test_scaled_decimal_claim_uses_reported_precision() -> None:
    claim = ClaimSchema(
        claim_id="scaled-count-decimal", source_sentence="2025년 5월 취업자는 2915.9만명이었다.",
        indicator="취업자 수", value=2915.9, unit="만명", time="2025년 5월",
        frequency="월", calculation="DIRECT_VALUE", parse_status="AUTO_OK",
    )
    assert _claim_tolerance(claim) == pytest.approx(0.05)
