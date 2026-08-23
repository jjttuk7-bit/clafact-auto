from core.record_periods import enumerate_record_periods


def test_quarterly_history_accepts_official_kosis_fraction_format() -> None:
    assert enumerate_record_periods("1999 3/4", "2000-Q1", "분기") == [
        "1999-Q3",
        "1999-Q4",
        "2000-Q1",
    ]
