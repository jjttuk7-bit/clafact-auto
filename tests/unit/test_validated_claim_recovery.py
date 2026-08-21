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
