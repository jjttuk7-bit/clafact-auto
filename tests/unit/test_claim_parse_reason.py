import pytest

from core.claim_parse_reason import operational_parse_reason


@pytest.mark.parametrize(
    ("detail", "expected"),
    [
        ("SLOT_AMBIGUOUS", "SLOT_AMBIGUOUS"),
        ("SOMETHING_NEW", "CLAIM_PARSE_UNCERTAIN"),
        ("API_KEY_INVALID", "CLAIM_PARSE_UNCERTAIN"),
        ("MISSING_REQUIRED_SLOTS:time", "MISSING_REQUIRED_SLOTS:time"),
        ("MISSING_REQUIRED_SLOTS:time,indicator,time", "MISSING_REQUIRED_SLOTS:indicator,time"),
        ("MISSING_REQUIRED_SLOTS:banana", "CLAIM_PARSE_UNCERTAIN"),
        ("MISSING_REQUIRED_SLOTS:api_key", "CLAIM_PARSE_UNCERTAIN"),
        ("MISSING_REQUIRED_SLOTS:time,xyz", "CLAIM_PARSE_UNCERTAIN"),
        (
            "한 문장에 수출액과 수입액이라는 서로 독립적인 두 수치가 포함되어 단일 주장으로 추출할 수 없음",
            "MULTIPLE_CLAIMS",
        ),
        ("목표 시점과 기준 기간이 명시되지 않아 자동 확정할 수 없음", "TIME_UNCLEAR"),
        ("구체적인 수치가 없고 단일 값으로 표현할 수 없음", "VALUE_UNCLEAR"),
        ("비교 기준이 명시되지 않아 성장률 유형을 확정할 수 없음", "COMPARISON_UNCLEAR"),
        ("향후 발생할 수 있다는 전망이며 실제 기록값이 아니다", "FORECAST_CLAIM"),
        ("해석이 충분히 명확하지 않습니다.", "CLAIM_PARSE_UNCERTAIN"),
        (None, "CLAIM_PARSE_UNCERTAIN"),
    ],
)
def test_operational_parse_reason_uses_stable_taxonomy(detail, expected) -> None:
    assert operational_parse_reason(detail) == expected
