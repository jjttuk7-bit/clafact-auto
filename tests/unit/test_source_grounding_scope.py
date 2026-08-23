from datetime import date

from core.validated_claim_recovery import recover_validated_claim
from schemas.claim import ClaimSchema


def _auto(source: str, *, value: float, unit: str) -> ClaimSchema:
    return ClaimSchema(
        claim_id="C", source_sentence=source, indicator="indicator",
        value=value, unit=unit, time="2024", frequency="annual",
        calculation="DIRECT_VALUE", parse_status="AUTO_OK",
    )


def test_existing_auto_count_unit_is_not_blocked_by_context_grounding_guard() -> None:
    claim = _auto("2024\ub144 \uc790\ub3d9\ucc28 \ud310\ub9e4\ub7c9\uc740 100\ub300\uc600\ub2e4.", value=100, unit="\ub300")

    assert recover_validated_claim(claim, date(2025, 1, 1)).parse_status == "AUTO_OK"


def test_context_grounding_accepts_count_units_outside_the_old_whitelist() -> None:
    claim = _auto("2024\ub144 \uc790\ub3d9\ucc28 \ud310\ub9e4\ub7c9\uc740 100\ub300\uc600\ub2e4.", value=100, unit="\ub300")

    recovered = recover_validated_claim(
        claim,
        date(2025, 1, 1),
        source_value_text="100\ub300",
    )

    assert recovered.parse_status == "AUTO_OK"


def test_existing_auto_compound_korean_number_is_not_miscalculated() -> None:
    claim = _auto("2024\ub144 \uc778\uad6c\ub294 2\ucc9c804\ub9cc \uba85\uc774\uc5c8\ub2e4.", value=28_040_000, unit="\uba85")

    assert recover_validated_claim(claim, date(2025, 1, 1)).parse_status == "AUTO_OK"


def test_percent_does_not_match_percent_point_target() -> None:
    claim = _auto("\uc0c1\uc2b9\ud3ed\uc740 1.1%\ud3ec\uc778\ud2b8\uc600\ub2e4.", value=1.1, unit="%")

    recovered = recover_validated_claim(
        claim, date(2025, 1, 1), source_value_text="1.1%\ud3ec\uc778\ud2b8"
    )

    assert recovered.parse_status == "HOLD"
    assert recovered.parse_reason == "TARGET_VALUE_NOT_IN_SOURCE_SENTENCE"


def test_explicit_target_expression_is_the_only_grounding_text_for_child() -> None:
    claim = _auto("employment was 60% and inflation was 5%.", value=60, unit="%")

    recovered = recover_validated_claim(
        claim,
        date(2025, 1, 1),
        source_value_text="5%",
    )

    assert recovered.parse_status == "HOLD"
    assert recovered.parse_reason == "TARGET_VALUE_NOT_IN_SOURCE_SENTENCE"
