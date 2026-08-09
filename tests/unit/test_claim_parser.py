from dataclasses import dataclass

import pytest

from core.claim_parser import parse_claim
from schemas.claim import ClaimSchema


@dataclass
class FakeStructuredExtractor:
    response: ClaimSchema

    def extract(self, source_sentence: str) -> ClaimSchema:
        return self.response


def auto_claim(**updates: object) -> ClaimSchema:
    payload: dict[str, object] = {
        "claim_id": "model-id",
        "source_sentence": "model sentence",
        "indicator": "고용률",
        "value": 70.0,
        "unit": "%",
        "time": "2024",
        "calculation": "DIRECT_VALUE",
        "parse_status": "AUTO_OK",
    }
    payload.update(updates)
    return ClaimSchema(**payload)


def test_parse_claim_uses_structured_claim_response() -> None:
    result = parse_claim("2024년 고용률은 70%였다.", FakeStructuredExtractor(auto_claim()))

    assert result.indicator == "고용률"
    assert result.parse_status == "AUTO_OK"


def test_parse_claim_preserves_the_original_source_sentence() -> None:
    result = parse_claim("  2024년 고용률은 70%였다.  ", FakeStructuredExtractor(auto_claim()))

    assert result.source_sentence == "2024년 고용률은 70%였다."


def test_parse_claim_generates_stable_claim_id_from_source() -> None:
    extractor = FakeStructuredExtractor(auto_claim())

    assert parse_claim("2024년 고용률은 70%였다.", extractor).claim_id == parse_claim(
        "2024년 고용률은 70%였다.", extractor
    ).claim_id


def test_parse_claim_routes_missing_indicator_to_hold() -> None:
    result = parse_claim("수치는 70%였다.", FakeStructuredExtractor(auto_claim(indicator=None)))

    assert result.parse_status == "HOLD"
    assert result.parse_reason == "MISSING_REQUIRED_SLOTS:indicator"


def test_parse_claim_routes_missing_value_to_hold() -> None:
    result = parse_claim("고용률이었다.", FakeStructuredExtractor(auto_claim(value=None)))

    assert result.parse_status == "HOLD"
    assert result.parse_reason == "MISSING_REQUIRED_SLOTS:value"


def test_parse_claim_routes_missing_unit_to_hold() -> None:
    result = parse_claim("2024년 고용률은 70이었다.", FakeStructuredExtractor(auto_claim(unit=None)))

    assert result.parse_status == "HOLD"
    assert result.parse_reason == "MISSING_REQUIRED_SLOTS:unit"


def test_parse_claim_routes_missing_time_to_hold() -> None:
    result = parse_claim("고용률은 70%였다.", FakeStructuredExtractor(auto_claim(time=None)))

    assert result.parse_status == "HOLD"
    assert result.parse_reason == "MISSING_REQUIRED_SLOTS:time"


def test_parse_claim_preserves_explicit_human_review_route() -> None:
    result = parse_claim(
        "향후 고용률은 70%가 될 전망이다.",
        FakeStructuredExtractor(auto_claim(parse_status="HUMAN_REVIEW", parse_reason="FORECAST_CLAIM")),
    )

    assert result.parse_status == "HUMAN_REVIEW"
    assert result.parse_reason == "FORECAST_CLAIM"


def test_parse_claim_without_extractor_returns_hold_contract() -> None:
    result = parse_claim("2024년 고용률은 70%였다.")

    assert result.parse_status == "HOLD"
    assert result.parse_reason == "STRUCTURED_EXTRACTOR_NOT_CONFIGURED"


def test_parse_claim_rejects_blank_source_sentence() -> None:
    with pytest.raises(ValueError, match="source_sentence"):
        parse_claim("   ", FakeStructuredExtractor(auto_claim()))


def test_parse_claim_rejects_non_schema_extractor_response() -> None:
    class InvalidExtractor:
        def extract(self, source_sentence: str) -> object:
            return {"indicator": "고용률"}

    with pytest.raises(TypeError, match="ClaimSchema"):
        parse_claim("2024년 고용률은 70%였다.", InvalidExtractor())
