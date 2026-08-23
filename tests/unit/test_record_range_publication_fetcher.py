from datetime import date

import pytest

from core.kosis_fetcher import OfficialValueFetcher
from core.kosis_publication import PublicationEvidence
from schemas.evidence import EvidenceCellSchema


def _cells() -> list[EvidenceCellSchema]:
    return [
        EvidenceCellSchema(
            org_id="101",
            tbl_id="DT_1DA7002S",
            itm_id="T20",
            dimension_codes={"A": "00"},
            prd_se="M",
            prd_de=period,
            unit="%",
            canonical_key=f"record:{period}",
            status="CONFIRMED",
        )
        for period in ("1999-06", "2025-06")
    ]


class RangeLookup:
    def __init__(self, rows: list[dict[str, str]]) -> None:
        self.rows = rows
        self.calls = 0

    def fetch_many(self, cells: list[EvidenceCellSchema]) -> list[dict[str, str]]:
        self.calls += 1
        assert [cell.prd_de for cell in cells] == ["1999-06", "2025-06"]
        return self.rows


class ReleaseLookup:
    def __init__(self, evidence: PublicationEvidence) -> None:
        self.evidence = evidence
        self.periods: list[str] = []

    def fetch(self, org_id: str, table_id: str, *, period: str) -> PublicationEvidence:
        assert (org_id, table_id) == ("101", "DT_1DA7002S")
        self.periods.append(period)
        return self.evidence


def _rows() -> list[dict[str, str]]:
    return [
        {"TBL_ID": "DT_1DA7002S", "ITM_ID": "T20", "PRD_DE": "199906", "A": "00", "DT": "60.3", "LST_CHN_DE": "2009-03-18"},
        {"TBL_ID": "DT_1DA7002S", "ITM_ID": "T20", "PRD_DE": "202506", "A": "00", "DT": "70.3", "LST_CHN_DE": "2025-07-03"},
    ]


def _release(*, status: str = "VERIFIED", published_at: date | None = date(2025, 7, 16)) -> PublicationEvidence:
    return PublicationEvidence(
        status=status,
        reference_period="2025-06",
        published_at=published_at,
        source_url="https://www.kostat.go.kr/board.es?act=view&list_no=437607",
        retrieved_at="2026-08-23T00:00:00Z",
        content_hash="a" * 64,
    )


def _fetcher(rows: list[dict[str, str]], release: PublicationEvidence) -> tuple[OfficialValueFetcher, RangeLookup, ReleaseLookup]:
    api = RangeLookup(rows)
    publication = ReleaseLookup(release)
    return (
        OfficialValueFetcher([], api_lookup=api, prefer_api=True, publication_lookup=publication, require_verified_release_metadata=True),
        api,
        publication,
    )


def test_record_history_uses_one_range_request_and_one_target_release() -> None:
    fetcher, api, publication = _fetcher(_rows(), _release())

    values = fetcher.fetch_record_history(_cells(), article_date=date(2025, 7, 16))

    assert api.calls == 1
    assert publication.periods == ["2025-06"]
    assert [value.value for value in values] == [60.3, 70.3]
    assert [value.value_last_changed_at for value in values] == [date(2009, 3, 18), date(2025, 7, 3)]
    assert len({value.snapshot_hash for value in values}) == 1
    assert all(value.status == "SUCCESS" and value.source == "API" for value in values)
    assert all("startPrdDe=199906" in value.source_url and "endPrdDe=202506" in value.source_url for value in values)
    assert all(value.publication and value.publication.evidence_scope == "CALCULATION_RANGE" for value in values)
    assert all(value.publication and value.publication.reference_period == "2025-06" for value in values)
    assert all(value.publication and value.publication.coverage_start_period == "1999-06" for value in values)
    assert all(value.publication and value.publication.coverage_end_period == "2025-06" for value in values)


@pytest.mark.parametrize(
    ("release", "expected"),
    [
        (_release(status="UNRESOLVED", published_at=None), "AS_OF_UNAVAILABLE"),
        (_release(status="FETCH_FAILED", published_at=None), "PUBLICATION_FETCH_FAILED"),
        (_release(published_at=date(2025, 7, 17)), "AS_OF_UNAVAILABLE"),
    ],
)
def test_record_history_fails_closed_when_target_release_is_not_usable(release: PublicationEvidence, expected: str) -> None:
    fetcher, _, _ = _fetcher(_rows(), release)
    values = fetcher.fetch_record_history(_cells(), article_date=date(2025, 7, 16))
    assert {value.status for value in values} == {expected}
    assert all(value.value is None for value in values)


@pytest.mark.parametrize("changed", [None, "not-a-date", "2025-07-17"])
def test_record_history_fails_closed_for_missing_invalid_or_late_row_change_date(changed: str | None) -> None:
    rows = _rows()
    if changed is None:
        rows[0].pop("LST_CHN_DE")
    else:
        rows[0]["LST_CHN_DE"] = changed
    fetcher, _, _ = _fetcher(rows, _release())
    values = fetcher.fetch_record_history(_cells(), article_date=date(2025, 7, 16))
    assert {value.status for value in values} == {"AS_OF_UNAVAILABLE"}


def test_record_history_fails_closed_when_requested_period_is_missing() -> None:
    fetcher, _, _ = _fetcher(_rows()[1:], _release())
    values = fetcher.fetch_record_history(_cells(), article_date=date(2025, 7, 16))
    assert {value.status for value in values} == {"NO_DATA"}
