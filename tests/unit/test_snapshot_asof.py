from datetime import date

from core.snapshot_asof import filter_rows_as_of


def test_filter_rows_as_of_keeps_only_values_published_by_article_date() -> None:
    rows = [{"PRD_DE": "202405", "DT": "106.09", "LST_CHN_DE": "2024-06-26"}, {"PRD_DE": "202505", "DT": "109.67", "LST_CHN_DE": "2026-07-22"}]
    assert filter_rows_as_of(rows, date(2025, 6, 26)) == [rows[0]]


def test_filter_rows_as_of_holds_undated_records() -> None:
    assert filter_rows_as_of([{"PRD_DE": "202505", "DT": "109.67"}], date(2025, 6, 26)) == []


def test_filter_rows_as_of_accepts_explicit_goldset_adjudication() -> None:
    row = {"PRD_DE": "202502", "DT": "3027854", "as_of_verified_by_goldset": True}
    assert filter_rows_as_of([row], date(2025, 3, 9)) == [row]


def test_verified_official_release_date_overrides_earlier_last_changed_date() -> None:
    row = {
        "PRD_DE": "202510",
        "DT": "136.62",
        "last_changed_at": "2025-10-30",
        "official_published_at": "2025-11-04",
        "official_release_verified": True,
    }

    assert filter_rows_as_of([row], date(2025, 11, 3)) == []
    assert filter_rows_as_of([row], date(2025, 11, 4)) == [row]


def test_verified_release_does_not_override_post_article_value_revision() -> None:
    row = {
        "PRD_DE": "202501",
        "DT": "24099",
        "LST_CHN_DE": "2026-02-23",
        "official_published_at": "2025-03-26",
        "official_release_verified": True,
    }

    assert filter_rows_as_of([row], date(2025, 3, 27)) == []
    assert filter_rows_as_of([row], date(2026, 2, 23)) == [row]


def test_official_release_date_overrides_goldset_adjudication() -> None:
    row = {
        "PRD_DE": "202510",
        "DT": "136.62",
        "official_published_at": "2025-11-04",
        "official_release_verified": True,
        "as_of_verified_by_goldset": True,
    }

    assert filter_rows_as_of([row], date(2025, 11, 3)) == []
    assert filter_rows_as_of([row], date(2025, 11, 4)) == [row]
