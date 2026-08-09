from pathlib import Path
from core.kosis_fetcher import fetch_kosis_value
from core.verdict_engine import make_verdict
from schemas.evidence import EvidenceCellSchema

def test_goldset_cpi_growth_matches_direct_snapshot_value() -> None:
    cell = EvidenceCellSchema(org_id="101",tbl_id="DT_1J22042",itm_id="T03",obj_id="I",member_code="총지수",prd_se="월",prd_de="GOLD",unit="%",canonical_key="ORG=101|TBL=DT_1J22042|ITM=T03|OBJ=I|MEMBER=총지수|PRD_SE=월|PRD_DE=GOLD",status="CONFIRMED")
    official = fetch_kosis_value(cell,Path("data/kosis_snapshots/goldset_pilot.json"))
    verdict = make_verdict("NEWS_B-006-A01",2.0,[official.value],official.value,tolerance=0.01)
    assert verdict.verdict == "MATCH" and verdict.route_status == "AUTO"
