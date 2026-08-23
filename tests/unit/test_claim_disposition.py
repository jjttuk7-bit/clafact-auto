from core.claim_disposition import classify_claim_disposition
from schemas.claim import ClaimSchema


def _claim(source: str, **updates: object) -> ClaimSchema:
    values: dict[str, object] = {
        "claim_id": "C-1",
        "source_sentence": source,
        "indicator": "consumer price growth",
        "value": 1.8,
        "unit": "%",
        "time": "2025",
        "frequency": "annual",
        "calculation": "DIRECT_VALUE",
        "parse_status": "AUTO_OK",
    }
    values.update(updates)
    return ClaimSchema.model_validate(values)


def test_explicit_forecast_is_excluded_before_official_search() -> None:
    result = classify_claim_disposition(
        _claim("정부는 물가 상승률을 1.8%로 내다봤다.")
    )

    assert result.disposition == "FORECAST_OR_POLICY"
    assert result.reason_code == "EXPLICIT_FORECAST_OR_POLICY_MARKER"
    assert result.next_route == "PRE_VERIFICATION_EXCLUDE"


def test_explicit_policy_plan_is_excluded_before_official_search() -> None:
    result = classify_claim_disposition(
        _claim("정부는 무역금융 360조원을 공급한다는 방침이다.")
    )

    assert result.disposition == "FORECAST_OR_POLICY"


def test_complete_historical_numeric_fact_enters_official_search() -> None:
    result = classify_claim_disposition(
        _claim("2024년 소비자 물가 상승률은 1.8%였다.")
    )

    assert result.disposition == "OFFICIAL_VERIFICATION_TARGET"
    assert result.next_route == "OFFICIAL_SEARCH"


def test_sentence_without_statistical_target_value_is_safely_excluded() -> None:
    result = classify_claim_disposition(
        _claim(
            "지난해 수출이 역대 최대 실적을 기록했다.",
            value=None,
            unit=None,
            time="2024",
            calculation=None,
            parse_status="HOLD",
            parse_reason="MISSING_REQUIRED_SLOTS:value,unit,calculation",
        )
    )

    assert result.disposition == "NO_VERIFIABLE_NUMERIC_ASSERTION"
    assert result.reason_code == "NO_STATISTICAL_TARGET_VALUE"
    assert result.next_route == "PRE_VERIFICATION_EXCLUDE"


def test_numeric_fact_with_missing_time_remains_context_insufficient() -> None:
    result = classify_claim_disposition(
        _claim(
            "수출액은 480억 달러였다.",
            indicator="export value",
            value=480.0,
            unit="USD 100m",
            time=None,
            parse_status="HOLD",
            parse_reason="MISSING_REQUIRED_SLOTS:time",
        )
    )

    assert result.disposition == "SOURCE_CONTEXT_INSUFFICIENT"
    assert result.reason_code == "MISSING_REQUIRED_SLOTS:time"
    assert result.next_route == "CONTEXT_REVIEW"


def test_historical_fact_is_not_excluded_only_because_reason_mentions_forecast() -> None:
    result = classify_claim_disposition(
        _claim(
            "2024년 소비자 물가 상승률은 1.8%였다.",
            parse_reason="과거 정부 전망치와 비교한 실제 확정값",
        )
    )

    assert result.disposition == "OFFICIAL_VERIFICATION_TARGET"
