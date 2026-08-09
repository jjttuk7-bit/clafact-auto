from pathlib import Path
from core.calculator import calculate
from core.kosis_fetcher import fetch_kosis_value
from core.verdict_engine import make_verdict
from schemas.evidence import CalculationPlan, EvidenceCellSchema

def test_goldset_youth_unemployment_multiple_matches_snapshot() -> None:
    base = "ORG=101|TBL=DT_1DA7102S|ITM=T80|OBJ=G|MEMBER="
    cells = [EvidenceCellSchema(org_id="101",tbl_id="DT_1DA7102S",itm_id="T80",obj_id="G",member_code=member,prd_se="월",prd_de="GOLD",unit="%",canonical_key=base+member+"|PRD_SE=월|PRD_DE=GOLD",status="CONFIRMED") for member in ("15-29세","계")]
    values = [fetch_kosis_value(cell,Path("data/kosis_snapshots/goldset_pilot.json")).value for cell in cells]
    calculated = calculate(CalculationPlan(calculation_type="RATIO",required_cells=cells),values)
    verdict = make_verdict("NEWS_B-007-A01",2.4,values,calculated,tolerance=0.05)
    assert verdict.verdict == "MATCH" and verdict.route_status == "AUTO"
