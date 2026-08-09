from pathlib import Path
from core.kosis_fetcher import fetch_kosis_value
from core.unit_normalizer import convert_value
from core.verdict_engine import make_verdict
from schemas.evidence import EvidenceCellSchema

def test_goldset_one_person_household_matches_snapshot_after_scale_conversion() -> None:
    cell = EvidenceCellSchema(org_id="101", tbl_id="DT_1ES4I001S", itm_id="T1", prd_se="년", prd_de="2024", unit="천가구", canonical_key="ORG=101|TBL=DT_1ES4I001S|ITM=T1|OBJ=None|MEMBER=None|PRD_SE=년|PRD_DE=2024", status="CONFIRMED")
    official = fetch_kosis_value(cell, Path("data/kosis_snapshots/goldset_pilot.json"))
    verdict = make_verdict("KOSIS_SEED-002-A01", convert_value(8_000_000, "가구", "천가구"), [official.value], official.value, tolerance=5)
    assert official.status == "SUCCESS"
    assert verdict.verdict == "MATCH" and verdict.route_status == "AUTO"
