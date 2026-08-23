import pytest

from core.record_periods import enumerate_record_periods


def test_enumerates_annual_history_through_claim_period() -> None:
    assert enumerate_record_periods("2022", "2024", "\ub144") == ["2022", "2023", "2024"]


@pytest.mark.parametrize(
    ("start", "current", "expected"),
    [
        ("2024.10", "2024-12", ["2024-10", "2024-11", "2024-12"]),
        ("2024.01", "2024.03", ["2024.01", "2024.02", "2024.03"]),
        ("202401", "202403", ["202401", "202402", "202403"]),
    ],
)
def test_enumerates_monthly_history_in_current_coordinate_format(
    start: str, current: str, expected: list[str]
) -> None:
    assert enumerate_record_periods(start, current, "\uc6d4") == expected


def test_enumerates_quarterly_history() -> None:
    assert enumerate_record_periods("2023-Q3", "2024-Q1", "\ubd84\uae30") == [
        "2023-Q3", "2023-Q4", "2024-Q1",
    ]


@pytest.mark.parametrize(
    ("start", "current", "frequency"),
    [(None, "2024", "\ub144"), ("2025", "2024", "\ub144"), ("2020", "2024", "\ubc18\uae30")],
)
def test_rejects_incomplete_or_unsupported_record_ranges(
    start: str | None, current: str, frequency: str
) -> None:
    assert enumerate_record_periods(start, current, frequency) is None


def test_rejects_a_range_larger_than_the_safety_limit() -> None:
    assert enumerate_record_periods("1900.01", "2024.12", "\uc6d4", max_periods=1200) is None
