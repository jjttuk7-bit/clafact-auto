from datetime import date
import json

from core.kosis_fetcher import OfficialValueFetcher
from core.kosis_publication import PublicationEvidence
from schemas.evidence import EvidenceCellSchema


def cell() -> EvidenceCellSchema:
    return EvidenceCellSchema(org_id="101", tbl_id="DT", itm_id="T", prd_se="M", prd_de="202505", canonical_key="key", status="CONFIRMED")


def test_unified_fetcher_reads_asof_structured_snapshot(tmp_path) -> None:
    path = tmp_path / "official.json"
    path.write_text(json.dumps({"org_id":"101","tbl_id":"DT","item_id":"T","records":[{"period":"202505","value":109.67,"last_changed_at":"2025-05-30"}]}), encoding="utf-8")

    result = OfficialValueFetcher([path]).fetch(cell(), article_date=date(2025, 6, 26))

    assert result.status == "SUCCESS"
    assert result.value == 109.67
    assert result.source == "SNAPSHOT"


def test_unified_fetcher_holds_structured_snapshot_after_article_date(tmp_path) -> None:
    path = tmp_path / "official.json"
    path.write_text(json.dumps({"org_id":"101","tbl_id":"DT","item_id":"T","records":[{"period":"202505","value":109.67,"last_changed_at":"2026-07-22"}]}), encoding="utf-8")

    result = OfficialValueFetcher([path]).fetch(cell(), article_date=date(2025, 6, 26))

    assert result.status == "AS_OF_UNAVAILABLE"
    assert result.value is None


def test_unified_fetcher_uses_api_rows_when_snapshot_has_no_value() -> None:
    rows = [{"TBL_ID":"DT","ITM_ID":"T","PRD_DE":"202505","DT":"109.67","LST_CHN_DE":"2025-05-30"}]
    result = OfficialValueFetcher([], api_lookup=lambda _cell: rows).fetch(cell(), article_date=date(2025, 6, 26))

    assert result.status == "SUCCESS"
    assert result.source == "API"

    assert len(result.snapshot_hash) == 64

def test_unified_fetcher_matches_dimension_codes(tmp_path) -> None:
    path = tmp_path / "official.json"
    path.write_text(json.dumps({"org_id":"101","tbl_id":"DT","item_id":"T","records":[{"period":"202402","value":3026.9,"last_changed_at":"2025-04-08","dimension_codes":{"C1":"Q"}},{"period":"202402","value":1593.8,"last_changed_at":"2025-04-08","dimension_codes":{"C1":"872"}}]}), encoding="utf-8")
    selected = EvidenceCellSchema(org_id="101", tbl_id="DT", itm_id="T", prd_se="H", prd_de="202402", dimension_codes={"C1":"872"}, canonical_key="key", status="CONFIRMED")

    result = OfficialValueFetcher([path]).fetch(selected, article_date=date(2025, 10, 27))

    assert result.status == "SUCCESS"
    assert result.value == 1593.8


def test_unified_fetcher_accepts_api_row_without_echoed_dimension_codes() -> None:
    rows = [{"TBL_ID":"DT", "ITM_ID":"T", "PRD_DE":"202405", "DT":"70", "LST_CHN_DE":"2024-06-01"}]
    selected = EvidenceCellSchema(
        org_id="101", tbl_id="DT", itm_id="T", prd_se="M", prd_de="202405",
        dimension_codes={"B":"0", "J":"00"}, canonical_key="key", status="CONFIRMED",
    )

    result = OfficialValueFetcher([], api_lookup=lambda _cell: rows).fetch(selected, article_date=date(2024, 6, 2))

    assert result.status == "SUCCESS"
    assert result.value == 70.0

def test_unified_fetcher_matches_native_kosis_c_columns() -> None:
    rows = [{"TBL_ID":"DT", "ITM_ID":"T", "PRD_DE":"202405", "C1":"00", "DT":"70", "LST_CHN_DE":"2024-06-01"}]
    cell = EvidenceCellSchema(org_id="101", tbl_id="DT", itm_id="T", prd_se="M", prd_de="202405", dimension_codes={"C1":"00"}, canonical_key="key", status="CONFIRMED")
    result = OfficialValueFetcher([], api_lookup=lambda _cell: rows).fetch(cell, article_date=date(2024, 6, 2))
    assert result.status == "SUCCESS"


def test_unified_fetcher_prefers_api_over_snapshot_when_enabled(tmp_path) -> None:
    path = tmp_path / "official.json"
    path.write_text(json.dumps({"org_id":"101","tbl_id":"DT","item_id":"T","records":[{"period":"202505","value":109.67,"last_changed_at":"2025-05-30"}]}), encoding="utf-8")
    rows = [{"TBL_ID":"DT", "ITM_ID":"T", "PRD_DE":"202505", "DT":"110.01", "LST_CHN_DE":"2025-05-30"}]

    result = OfficialValueFetcher([path], api_lookup=lambda _cell: rows, prefer_api=True).fetch(
        cell(), article_date=date(2025, 6, 26)
    )

    assert result.status == "SUCCESS"
    assert result.value == 110.01
    assert result.source == "API"


def test_prefer_api_falls_back_to_dated_snapshot_when_api_has_no_asof_metadata(tmp_path) -> None:
    path = tmp_path / "official.json"
    path.write_text(json.dumps({"org_id":"101","tbl_id":"DT","item_id":"T","records":[{"period":"202505","value":109.67,"last_changed_at":"2025-05-30"}]}), encoding="utf-8")
    api_rows = [{"TBL_ID":"DT", "ITM_ID":"T", "PRD_DE":"202505", "DT":"110.01"}]

    result = OfficialValueFetcher([path], api_lookup=lambda _cell: api_rows, prefer_api=True).fetch(
        cell(), article_date=date(2025, 6, 26)
    )

    assert result.status == "SUCCESS"
    assert result.value == 109.67
    assert result.source == "SNAPSHOT"


def test_missing_snapshot_returns_fetch_failed_instead_of_raising(tmp_path) -> None:
    result = OfficialValueFetcher([
        tmp_path / "missing-official-snapshot.json"
    ]).fetch(cell(), article_date=date(2025, 6, 26))

    assert result.status == "FETCH_FAILED"
    assert result.value is None

def test_live_api_value_uses_release_metadata_without_snapshot_value_fallback(tmp_path) -> None:
    release = tmp_path / "release.json"
    release.write_text(json.dumps({
        "org_id": "101",
        "tbl_id": "DT",
        "item_id": "T",
        "source_published_at": "2025-06-01",
        "records": [{
            "period": "202505",
            "value": 999.0,
            "official_published_at": "2025-06-01",
            "official_release_verified": True,
        }],
    }), encoding="utf-8")
    api_rows = [{"TBL_ID":"DT", "ITM_ID":"T", "PRD_DE":"202505", "DT":"110.01"}]

    result = OfficialValueFetcher(
        [], api_lookup=lambda _cell: api_rows, prefer_api=True,
        as_of_metadata_paths=[release],
    ).fetch(cell(), article_date=date(2025, 6, 26))

    assert result.status == "SUCCESS"

    assert result.value == 110.01
    assert result.source == "API"

def test_fetch_many_uses_one_api_range_response_for_all_cells() -> None:
    class Lookup:
        calls = 0

        def __call__(self, _cell):
            raise AssertionError("single-cell API lookup must not run")

        def fetch_many(self, _cells):
            self.calls += 1
            return [
                {"TBL_ID":"DT", "ITM_ID":"T", "PRD_DE":"202410", "DT":"208.57", "LST_CHN_DE":"2025-01-01"},
                {"TBL_ID":"DT", "ITM_ID":"T", "PRD_DE":"202510", "DT":"136.62", "LST_CHN_DE":"2025-11-01"},
            ]

    lookup = Lookup()
    cells = [
        EvidenceCellSchema(
            org_id="101", tbl_id="DT", itm_id="T", prd_se="M", prd_de=period,
            canonical_key=period, status="CONFIRMED",
        )
        for period in ("2025-10", "2024-10")
    ]
    results = OfficialValueFetcher(
        [], api_lookup=lookup, prefer_api=True,
    ).fetch_many(cells, article_date=date(2025, 11, 4))

    assert lookup.calls == 1
    assert [result.value for result in results] == [136.62, 208.57]
    assert all(result.source == "API" for result in results)


def test_strict_live_asof_holds_without_verified_release_metadata() -> None:
    rows = [{
        "TBL_ID": "DT", "ITM_ID": "T", "PRD_DE": "202505",
        "DT": "109.67", "LST_CHN_DE": "2025-05-30",
    }]

    result = OfficialValueFetcher(
        [],
        api_lookup=lambda _cell: rows,
        prefer_api=True,
        require_verified_release_metadata=True,
    ).fetch(cell(), article_date=date(2025, 6, 26))

    assert result.status == "AS_OF_UNAVAILABLE"
    assert result.value is None


def test_strict_live_asof_uses_dynamic_official_publication_lookup() -> None:
    rows = [{
        "TBL_ID": "DT", "ITM_ID": "T", "PRD_DE": "202505",
        "DT": "109.67", "LST_CHN_DE": "2025-07-01",
    }]

    class PublicationLookup:
        def fetch(self, org_id: str, table_id: str, *, period: str) -> PublicationEvidence:
            assert (org_id, table_id, period) == ("101", "DT", "202505")
            return PublicationEvidence(
                status="VERIFIED",
                published_at=date(2025, 6, 1),
                pub_period="월",
                pub_date_text="2025-06-01",
                publication_method_url="https://kostat.go.kr/board.es?list_no=1",
                source_url="https://kosis.kr/openapi/statisticsExplData.do?orgId=101&tblId=DT",
                retrieved_at="2025-06-02T00:00:00Z",
                content_hash="a" * 64,
            )

    result = OfficialValueFetcher(
        [], api_lookup=lambda _cell: rows, prefer_api=True,
        publication_lookup=PublicationLookup(),
        require_verified_release_metadata=True,
    ).fetch(cell(), article_date=date(2025, 6, 26))

    assert result.status == "SUCCESS"
    assert result.value == 109.67
    assert result.publication is not None
    assert result.publication.source_url.startswith("https://kosis.kr/")


def test_dynamic_publication_after_article_date_is_not_accepted() -> None:
    rows = [{"TBL_ID": "DT", "ITM_ID": "T", "PRD_DE": "202505", "DT": "109.67"}]

    class PublicationLookup:
        def fetch(self, _org_id: str, _table_id: str, *, period: str) -> PublicationEvidence:
            return PublicationEvidence(
                status="VERIFIED",
                published_at=date(2025, 7, 1),
                source_url="https://kosis.kr/official",
                retrieved_at="2025-07-01T00:00:00Z",
                content_hash="b" * 64,
            )

    result = OfficialValueFetcher(
        [], api_lookup=lambda _cell: rows, prefer_api=True,
        publication_lookup=PublicationLookup(),
        require_verified_release_metadata=True,
    ).fetch(cell(), article_date=date(2025, 6, 26))

    assert result.status == "AS_OF_UNAVAILABLE"

def test_publication_lookup_is_cached_per_table_and_period() -> None:
    rows = [
        {"TBL_ID": "DT", "ITM_ID": "T", "PRD_DE": "202504", "DT": "1"},
        {"TBL_ID": "DT", "ITM_ID": "T", "PRD_DE": "202505", "DT": "2"},
    ]

    class PublicationLookup:
        def __init__(self) -> None:
            self.periods: list[str] = []

        def fetch(self, _org_id: str, _table_id: str, *, period: str) -> PublicationEvidence:
            self.periods.append(period)
            return PublicationEvidence(
                status="VERIFIED", published_at=date(2025, 6, 1),
                source_url="https://kosis.kr/official", retrieved_at="2025-06-01T00:00:00Z",
                content_hash=period.ljust(64, "0"),
            )

    lookup = PublicationLookup()
    fetcher = OfficialValueFetcher(
        [], api_lookup=lambda _cell: rows, prefer_api=True,
        publication_lookup=lookup, require_verified_release_metadata=True,
    )
    april = cell().model_copy(update={"prd_de": "202504"})
    may = cell().model_copy(update={"prd_de": "202505"})

    assert fetcher.fetch(april, article_date=date(2025, 6, 26)).status == "SUCCESS"
    assert fetcher.fetch(may, article_date=date(2025, 6, 26)).status == "SUCCESS"
    assert fetcher.fetch(april, article_date=date(2025, 6, 26)).status == "SUCCESS"
    assert lookup.periods == ["202504", "202505"]

def test_publication_transport_failure_is_distinct_from_unresolved_asof() -> None:
    rows = [{"TBL_ID": "DT", "ITM_ID": "T", "PRD_DE": "202505", "DT": "109.67"}]

    class PublicationLookup:
        def fetch(self, _org_id: str, _table_id: str, *, period: str) -> PublicationEvidence:
            return PublicationEvidence(
                status="FETCH_FAILED", source_url="https://kosis.kr/openapi/statisticsExplData.do",
                retrieved_at="2025-06-01T00:00:00Z", content_hash="",
            )

    result = OfficialValueFetcher(
        [], api_lookup=lambda _cell: rows, prefer_api=True,
        publication_lookup=PublicationLookup(), require_verified_release_metadata=True,
    ).fetch(cell(), article_date=date(2025, 6, 26))

    assert result.status == "PUBLICATION_FETCH_FAILED"

def test_direct_publication_unresolved_is_not_hidden_by_static_metadata(tmp_path) -> None:
    release = tmp_path / "release.json"
    release.write_text(json.dumps({
        "org_id": "101", "tbl_id": "DT", "item_id": "T",
        "records": [{"period": "202505", "official_published_at": "2025-06-01", "official_release_verified": True}],
    }), encoding="utf-8")
    rows = [{"TBL_ID": "DT", "ITM_ID": "T", "PRD_DE": "202505", "DT": "109.67"}]

    class PublicationLookup:
        def fetch(self, _org_id: str, _table_id: str, *, period: str) -> PublicationEvidence:
            return PublicationEvidence(status="UNRESOLVED")

    result = OfficialValueFetcher([], api_lookup=lambda _cell: rows, prefer_api=True,
        as_of_metadata_paths=[release], publication_lookup=PublicationLookup(),
        require_verified_release_metadata=True).fetch(cell(), article_date=date(2025, 6, 26))

    assert result.status == "AS_OF_UNAVAILABLE"

def test_direct_publication_failure_is_not_hidden_by_static_metadata(tmp_path) -> None:
    release = tmp_path / "release.json"
    release.write_text(json.dumps({
        "org_id": "101", "tbl_id": "DT", "item_id": "T",
        "records": [{
            "period": "202505", "official_published_at": "2025-06-01",
            "official_release_verified": True,
        }],
    }), encoding="utf-8")
    rows = [{"TBL_ID": "DT", "ITM_ID": "T", "PRD_DE": "202505", "DT": "109.67"}]

    class PublicationLookup:
        def fetch(self, _org_id: str, _table_id: str, *, period: str) -> PublicationEvidence:
            return PublicationEvidence(
                status="FETCH_FAILED", source_url="https://kosis.kr/openapi/statisticsExplData.do",
                retrieved_at="2025-06-01T00:00:00Z", content_hash="d" * 64,
            )

    result = OfficialValueFetcher(
        [], api_lookup=lambda _cell: rows, prefer_api=True,
        as_of_metadata_paths=[release], publication_lookup=PublicationLookup(),
        require_verified_release_metadata=True,
    ).fetch(cell(), article_date=date(2025, 6, 26))

    assert result.status == "PUBLICATION_FETCH_FAILED"
def test_fetch_many_falls_back_to_single_official_calls_when_range_request_fails() -> None:
    class Lookup:
        def __init__(self) -> None:
            self.single_calls: list[str] = []

        def __call__(self, selected):
            self.single_calls.append(selected.prd_de)
            return [{"TBL_ID": "DT", "ITM_ID": "T", "PRD_DE": selected.prd_de.replace("-", ""), "DT": "10"}]

        def fetch_many(self, _cells):
            raise RuntimeError("range unavailable")

    lookup = Lookup()
    cells = [
        EvidenceCellSchema(org_id="101", tbl_id="DT", itm_id="T", prd_se="M", prd_de=period, canonical_key=period, status="CONFIRMED")
        for period in ("2025-10", "2024-10")
    ]

    results = OfficialValueFetcher([], api_lookup=lookup, prefer_api=True).fetch_many(cells)

    assert lookup.single_calls == ["2025-10", "2024-10"]
    assert [result.value for result in results] == [10.0, 10.0]


def test_official_fetcher_matches_quarter_api_period_code() -> None:
    selected = EvidenceCellSchema(
        org_id="101", tbl_id="DT", itm_id="T", prd_se="분기", prd_de="2025-Q1",
        dimension_codes={"B": "0"}, canonical_key="quarter", status="CONFIRMED",
    )
    rows = [
        {"TBL_ID": "DT", "ITM_ID": "T", "PRD_DE": "202501", "C1": "0", "DT": "28215.3"}
    ]

    result = OfficialValueFetcher(
        [], api_lookup=lambda _cell: rows, prefer_api=True
    ).fetch(selected)

    assert result.status == "SUCCESS"
    assert result.value == 28215.3
