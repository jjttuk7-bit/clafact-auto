from pathlib import Path
from core.calculator import calculate
from core.kosis_fetcher import fetch_kosis_value
from core.unit_normalizer import convert_value
from core.verdict_engine import make_verdict
from schemas.evidence import CalculationPlan, EvidenceCellSchema

def test_goldset_employment_change_matches_snapshot_after_scale_conversion() -> None:
    base = "ORG=101|TBL=DT_1DA7028S|ITM=T30|OBJ=B|MEMBER=계|PRD_SE=월|PRD_DE="
    cells = [EvidenceCellSchema(org_id="101",tbl_id="DT_1DA7028S",itm_id="T30",obj_id="B",member_code="계",prd_se="월",prd_de=period,unit="천명",canonical_key=base+period,status="CONFIRMED") for period in ("2025-03","2024-03")]
    values = [fetch_kosis_value(cell,Path("data/kosis_snapshots/goldset_pilot.json")).value for cell in cells]
    calculated = calculate(CalculationPlan(calculation_type="DIFFERENCE",required_cells=cells),values)
    verdict = make_verdict("NEWS_B-012-A01",convert_value(193_000,"명","천명"),values,calculated,tolerance=0.5)
    assert verdict.verdict == "MATCH" and verdict.route_status == "AUTO"
