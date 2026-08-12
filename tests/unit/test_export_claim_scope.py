from datetime import date

import pytest

from core.export_claim_scope import classify_export_claim_scope
from schemas.claim import ClaimSchema


def claim(sentence: str, **updates: object) -> ClaimSchema:
    data: dict[str, object] = {
        "claim_id": "E1", "source_sentence": sentence,
        "indicator": "수출액", "value": 8.2, "unit": "%",
        "time": "2024", "frequency": "Y", "region": None,
        "dimension": None, "comparison": {"type": "YEAR_OVER_YEAR"},
        "calculation": "GROWTH_RATE", "parse_status": "AUTO_OK",
    }
    data.update(updates)
    return ClaimSchema(**data)


def test_accepts_complete_annual_total_export_yoy_claim() -> None:
    decision = classify_export_claim_scope(
        claim("작년 한 해 전체 수출액은 전년 대비 8.2% 증가했다."),
        date(2025, 1, 2),
    )

    assert decision.route == "ANNUAL_TOTAL_YOY"
    assert decision.reason_code is None


@pytest.mark.parametrize(
    ("sentence", "updates", "route", "reason"),
    [
        (
            "한은은 올해 수출 증가율을 1.5%로 내다보고 있다.",
            {"time": "2025", "comparison": None},
            "FORECAST", "EXPORT_FORECAST_CLAIM",
        ),
        (
            "이달 1~10일 수출액은 전년 동기 대비 3.8% 증가했다.",
            {"time": "2025"},
            "PARTIAL_PERIOD", "EXPORT_PARTIAL_PERIOD",
        ),
        (
            "지난해 K푸드 수출액은 전년보다 6.1% 증가했다.",
            {"dimension": {"품목": "K푸드"}},
            "DIMENSION_SPECIFIC", "EXPORT_DIMENSION_REQUIRED",
        ),
        (
            "지난해 수출액은 1년 전보다 5.9% 증가했다.",
            {"time": "2022"},
            "SLOT_MISMATCH", "EXPORT_TIME_SLOT_MISMATCH",
        ),
        (
            "수출 증가율은 3.0%였다.",
            {"comparison": None},
            "SLOT_MISMATCH", "EXPORT_COMPARISON_REQUIRED",
        ),
    ],
)
def test_routes_non_total_export_claims_to_controlled_hold(
    sentence: str,
    updates: dict[str, object],
    route: str,
    reason: str,
) -> None:
    decision = classify_export_claim_scope(claim(sentence, **updates), date(2025, 1, 8))

    assert decision.route == route
    assert decision.reason_code == reason
