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


def test_likely_future_expression_is_classified_as_forecast() -> None:
    result = classify_claim_disposition(
        _claim("이달 소비자 물가가 2% 오를 듯하다.")
    )

    assert result.disposition == "FORECAST_OR_POLICY"


def test_approximate_percent_claim_is_not_excluded_as_non_numeric() -> None:
    result = classify_claim_disposition(
        _claim(
            "내수 판매가 6%대 급감했다.",
            value=None,
            time=None,
            parse_status="HOLD",
            parse_reason="MISSING_REQUIRED_SLOTS:value,time",
        )
    )

    assert result.disposition == "SOURCE_CONTEXT_INSUFFICIENT"


def test_complete_slots_do_not_override_value_missing_from_target_sentence() -> None:
    result = classify_claim_disposition(
        _claim(
            "\uc9c0\ub09c\ud574 \uc5ed\ub300 \ucd5c\ub300 \uc218\ucd9c \uc2e4\uc801\uacfc \ubb34\uc5ed\uc218\uc9c0 \ud751\uc790\ub97c \uae30\ub85d\ud588\ub2e4.",
            indicator="\uc218\ucd9c \uc2e4\uc801",
            value=6838,
            unit="\uc5b5 \ub2ec\ub7ec",
            time="2024\ub144",
            frequency="\ub144",
            calculation="DIRECT_VALUE",
            parse_status="HOLD",
            parse_reason="TARGET_VALUE_NOT_IN_SOURCE_SENTENCE",
        )
    )

    assert result.disposition == "SOURCE_CONTEXT_INSUFFICIENT"
    assert result.reason_code == "TARGET_VALUE_NOT_IN_SOURCE_SENTENCE"
    assert result.next_route == "CONTEXT_REVIEW"


def test_complete_slots_do_not_override_unresolved_time_reason() -> None:
    result = classify_claim_disposition(
        _claim(
            "18.2% increased during the same period.",
            parse_status="HOLD",
            parse_reason="RELATIVE_TIME_UNRESOLVED",
        )
    )

    assert result.disposition == "SOURCE_CONTEXT_INSUFFICIENT"
    assert result.reason_code == "RELATIVE_TIME_UNRESOLVED"
    assert result.next_route == "CONTEXT_REVIEW"


def test_complete_slots_do_not_override_record_comparison_split_reason() -> None:
    result = classify_claim_disposition(
        _claim(
            "The value was 1419 and set a record high.",
            parse_status="HOLD",
            parse_reason="RECORD_COMPARISON_REQUIRES_SEPARATE_CLAIM",
        )
    )

    assert result.disposition == "SOURCE_CONTEXT_INSUFFICIENT"
    assert result.reason_code == "RECORD_COMPARISON_REQUIRES_SEPARATE_CLAIM"
    assert result.next_route == "CONTEXT_REVIEW"
