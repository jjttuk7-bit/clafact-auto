import json

from core.kosis_fetcher import fetch_kosis_value
from schemas.evidence import EvidenceCellSchema


def cell() -> EvidenceCellSchema:
    return EvidenceCellSchema(org_id="101", tbl_id="DT", itm_id="T1", prd_se="Y", prd_de="2024", canonical_key="key", status="CONFIRMED")


def test_fetch_reads_official_value_from_snapshot(tmp_path) -> None:
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps({"key": 70.0}), encoding="utf-8")
    value = fetch_kosis_value(cell(), path)
    assert value.status == "SUCCESS"
    assert value.value == 70.0
    assert value.snapshot_hash


def test_fetch_returns_no_data_when_snapshot_has_no_cell(tmp_path) -> None:
    path = tmp_path / "snapshot.json"
    path.write_text("{}", encoding="utf-8")
    value = fetch_kosis_value(cell(), path)
    assert value.status == "NO_DATA"
    assert value.value is None
