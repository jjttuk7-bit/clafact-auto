from datetime import date
from pathlib import Path

from core.calculator import calculate
from core.kosis_fetcher import OfficialValueFetcher
from core.verdict_engine import make_verdict
from schemas.evidence import CalculationPlan, EvidenceCellSchema


def test_goldset_seed016_reproduces_construction_employment_difference() -> None:
    fetcher = OfficialValueFetcher([Path("data/kosis_snapshots/official_goldset_v3_seed016.json")])
    common = {"org_id":"101", "tbl_id":"DT_1DA7E06S_NEW", "itm_id":"T30", "prd_se":"M", "dimension_codes":{"C1":"41"}, "status":"CONFIRMED"}
    before = fetcher.fetch(EvidenceCellSchema(**common, prd_de="202401", canonical_key="202401"), article_date=date(2025, 2, 6))
    current = fetcher.fetch(EvidenceCellSchema(**common, prd_de="202501", canonical_key="202501"), article_date=date(2025, 2, 6))
    difference = calculate(CalculationPlan(calculation_type="DIFFERENCE"), [current.value, before.value])
    verdict = make_verdict("KOSIS_SEED-016-A01", -169.0, [before.value, current.value], difference, tolerance=0.5)

    assert round(difference, 1) == -168.6
    assert (verdict.verdict, verdict.route_status) == ("MATCH", "AUTO")
