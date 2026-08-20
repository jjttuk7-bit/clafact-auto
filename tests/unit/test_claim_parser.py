import json
from dataclasses import dataclass
from datetime import date

import pytest

from core.claim_parser import parse_claim
from core.hcx_claim_extractor import HcxClaimExtractor
from schemas.claim import ClaimSchema


@dataclass
class FakeStructuredExtractor:
    response: ClaimSchema

    def extract(self, source_sentence: str) -> ClaimSchema:
        return self.response


@dataclass
class FakeContextualExtractor:
    response: ClaimSchema
    received_article_date: date | None = None
    received_article_context: str | None = None

    def extract(
        self,
        source_sentence: str,
        *,
        article_published_at: date | None = None,
        article_context: str | None = None,
    ) -> ClaimSchema:
        self.received_article_date = article_published_at
        self.received_article_context = article_context
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


def test_parse_claim_derives_explicit_year_over_year_comparison() -> None:
    result = parse_claim(
        "2025년 10월 배추 물가는 전년 동월 대비 34.5% 하락했다.",
        FakeStructuredExtractor(
            auto_claim(
                indicator="배추 물가",
                value=-34.5,
                time="2025년 10월",
                comparison=None,
                calculation="GROWTH_RATE",
            )
        ),
    )

    assert result.comparison == {
        "type": "YEAR_OVER_YEAR",
        "reference_period": "전년 동월",
    }


def test_parse_claim_normalizes_explicit_percentage_decrease_to_negative() -> None:
    result = parse_claim(
        "2025년 10월 배추 물가는 전년 동월 대비 34.5% 하락했다.",
        FakeStructuredExtractor(
            auto_claim(
                indicator="배추 물가",
                value=34.5,
                unit="%",
                time="2025년 10월",
                comparison={"기준": "전년 동월 대비", "방향": "하락"},
            )
        ),
    )

    assert result.value == -34.5


def test_parse_claim_normalizes_openai_percent_unit_before_decrease_sign() -> None:
    result = parse_claim(
        "2025년 10월 배추 물가는 전년 동월 대비 34.5% 하락했다.",
        FakeStructuredExtractor(
            auto_claim(
                indicator="배추 물가",
                value=34.5,
                unit="percent",
                time="2025년 10월",
            )
        ),
    )

    assert result.unit == "%"
    assert result.value == -34.5


def test_parse_claim_normalizes_iso_month_to_korean_month() -> None:
    result = parse_claim(
        "2025년 10월 배추 물가는 전년 동월 대비 34.5% 하락했다.",
        FakeStructuredExtractor(
            auto_claim(value=-34.5, unit="%", time="2025-10")
        ),
    )

    assert result.time == "2025년 10월"


def test_parse_claim_uses_article_date_to_resolve_target_last_month() -> None:
    extractor = FakeContextualExtractor(
        auto_claim(indicator="가공식품 물가", value=3.1, unit="%", time="지난달", frequency="M", comparison={"type": "YEAR_OVER_YEAR"}, calculation="GROWTH_RATE")
    )
    result = parse_claim(
        "지난달 가공식품 물가는 전년 대비 3.1% 올랐다.", extractor, article_published_at=date(2025, 4, 5)
    )
    assert extractor.received_article_date == date(2025, 4, 5)
    assert result.time == "2025년 3월"
    assert result.frequency == "월"
    assert result.parse_status == "AUTO_OK"


def test_parse_claim_keeps_historical_reference_out_of_target_time() -> None:
    extractor = FakeContextualExtractor(
        auto_claim(indicator="가공식품 물가", value=3.1, unit="%", time="지난달", comparison={"type": "YEAR_OVER_YEAR", "reference_period": "2023년 12월"}, calculation="GROWTH_RATE")
    )
    result = parse_claim(
        "지난달 가공식품 물가는 전년 대비 3.1% 올라 2023년 12월 이후 최대였다.", extractor, article_published_at=date(2025, 4, 5)
    )
    assert result.time == "2025년 3월"
    assert result.comparison == {"type": "YEAR_OVER_YEAR", "reference_period": "2023년 12월"}


@pytest.mark.parametrize(("source_sentence", "value"), [("2025년 10월 소비자물가는 2.4% 상승했다.", 2.4), ("2025년 10월 배추 물가는 -34.5% 하락했다.", -34.5)])
def test_parse_claim_preserves_already_consistent_percentage_sign(source_sentence: str, value: float) -> None:
    result = parse_claim(source_sentence, FakeStructuredExtractor(auto_claim(value=value, unit="%", time="2025년 10월")))

    assert result.value == value


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


def test_parse_claim_holds_invalid_growth_contract_before_kosis() -> None:
    result = parse_claim(
        "2024년 고용률은 전년 대비 3.1%였다.",
        FakeStructuredExtractor(auto_claim(
            value=3.1,
            calculation="GROWTH_RATE",
            comparison={"type": "YEAR_OVER_YEAR"},
            condition=None,
        )),
    )

    assert result.parse_status == "HOLD"
    assert result.parse_reason == "MISSING_REQUIRED_SLOTS:condition"

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

def test_hcx_extractor_returns_claim_for_supported_frequency(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        def read(self) -> bytes:
            return json.dumps(
                {
                    "result": {
                        "message": {
                            "content": json.dumps(
                                {
                                    "claim_id": "hcx-id",
                                    "source_sentence": "2024년 고용률은 70%였다.",
                                    "indicator": "고용률",
                                    "value": 70,
                                    "unit": "%",
                                    "time": "2024",
                                    "frequency": "year",
                                    "region": None,
                                    "population": None,
                                    "dimension": None,
                                    "comparison": None,
                                    "calculation": None,
                                    "condition": None,
                                    "source_hint": None,
                                    "parse_status": "AUTO_OK",
                                    "parse_reason": None,
                                }
                            )
                        }
                    }
                }
            ).encode()

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
            return None

    monkeypatch.setattr("core.hcx_claim_extractor.urlopen", lambda *args, **kwargs: FakeResponse())

    result = HcxClaimExtractor(api_key="test-key").extract("2024년 고용률은 70%였다.")

    assert result.frequency == "year"
    assert result.indicator == "고용률"

def test_hcx_extractor_restores_month_frequency_from_structured_time(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        def read(self) -> bytes:
            return json.dumps(
                {"result": {"message": {"content": json.dumps({
                    "claim_id": "hcx-id",
                    "source_sentence": "2025년 3월 취업자 수는 2858만9000명이었다.",
                    "indicator": "취업자 수",
                    "value": 28589000,
                    "unit": "명",
                    "time": "2025년 3월",
                    "frequency": "월 | 분기 | 년",
                    "region": None,
                    "population": None,
                    "dimension": None,
                    "comparison": None,
                    "calculation": None,
                    "condition": None,
                    "source_hint": None,
                    "parse_status": "AUTO_OK",
                    "parse_reason": None,
                })}}}
            ).encode()

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
            return None

    monkeypatch.setattr("core.hcx_claim_extractor.urlopen", lambda *args, **kwargs: FakeResponse())

    result = HcxClaimExtractor(api_key="test-key").extract("2025년 3월 취업자 수는 2858만9000명이었다.")

    assert result.frequency == "월"


def test_hcx_extractor_does_not_convert_required_claim_id_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """A blank model identifier is normalized by parse_claim, never hidden as None."""
    class FakeResponse:
        def read(self) -> bytes:
            return json.dumps(
                {"result": {"message": {"content": json.dumps({
                    "claim_id": "",
                    "source_sentence": "10월 소비자물가는 2.4% 상승했다.",
                    "indicator": "소비자물가",
                    "value": 2.4,
                    "unit": "%",
                    "time": "2025년 10월",
                    "frequency": None,
                    "region": None,
                    "population": None,
                    "dimension": None,
                    "comparison": None,
                    "calculation": None,
                    "condition": None,
                    "source_hint": None,
                    "parse_status": "AUTO_OK",
                    "parse_reason": None,
                })}}}
            ).encode()

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
            return None

    monkeypatch.setattr("core.hcx_claim_extractor.urlopen", lambda *args, **kwargs: FakeResponse())

    extracted = HcxClaimExtractor(api_key="test-key").extract("10월 소비자물가는 2.4% 상승했다.")
    parsed = parse_claim("10월 소비자물가는 2.4% 상승했다.", FakeStructuredExtractor(extracted))

    assert extracted.claim_id == ""
    assert parsed.claim_id.startswith("claim_")

def test_parse_claim_backfills_explicit_share_comparison_before_contract_check() -> None:
    from core.claim_parser import parse_claim

    class Extractor:
        def extract(self, source_sentence, *, article_published_at=None):
            return ClaimSchema(
                claim_id="temporary", source_sentence=source_sentence, indicator="취업자 수",
                value=40, unit="%", time="2024년 12월", frequency="MONTHLY",
                calculation="SHARE", parse_status="AUTO_OK",
            )

    result = parse_claim("2024년 12월 여성 취업자 수는 전체 취업자 수의 40%였다.", Extractor())

    assert result.comparison == {
        "type": "SHARE_OF_TOTAL",
        "numerator": "여성 취업자 수",
        "denominator": "전체 취업자 수",
        "denominator_member": "전체",
    }
    assert result.parse_status == "AUTO_OK"
    assert result.parse_reason is None
def test_parse_claim_normalizes_explicit_share_type_from_structured_output() -> None:
    class Extractor:
        def extract(self, source_sentence, *, article_published_at=None):
            return ClaimSchema(
                claim_id="temporary", source_sentence=source_sentence, indicator="취업자 수",
                value=40, unit="%", time="2024년 12월", frequency="MONTHLY",
                dimension={"sex": "여성"}, calculation="SHARE",
                comparison={
                    "type": "SHARE", "numerator": "여성 취업자 수",
                    "denominator": "전체 취업자 수", "denominator_member": "전체",
                },
                parse_status="AUTO_OK",
            )

    result = parse_claim("2024년 12월 여성 취업자 수는 전체 취업자 수의 40%였다.", Extractor())

    assert result.parse_status == "AUTO_OK"
    assert result.comparison is not None
    assert result.comparison["type"] == "SHARE_OF_TOTAL"


def test_parse_claim_passes_limited_article_context_to_contextual_extractor() -> None:
    extractor = FakeContextualExtractor(auto_claim())

    parse_claim(
        "고용률은 70%였다.",
        extractor,
        article_published_at=date(2025, 4, 5),
        article_context="제목: 2025년 3월 고용 동향\n주변 문장: 지난달 고용률은 70%였다.",
    )

    assert extractor.received_article_context == (
        "제목: 2025년 3월 고용 동향\n주변 문장: 지난달 고용률은 70%였다."
    )
