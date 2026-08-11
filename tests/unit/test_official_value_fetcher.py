from datetime import date
import json

from core.kosis_fetcher import OfficialValueFetcher
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
