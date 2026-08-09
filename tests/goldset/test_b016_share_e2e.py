from datetime import date
from pathlib import Path

from core.calculator import calculate
from core.kosis_fetcher import OfficialValueFetcher
from core.verdict_engine import make_verdict
from schemas.evidence import CalculationPlan, EvidenceCellSchema


def test_goldset_b016_reproduces_fishing_household_aging_share_change() -> None:
    fetcher = OfficialValueFetcher([Path("data/kosis_snapshots/official_goldset_v3_news_b016.json")])
    def value(period: str, age: str) -> float:
        cell = EvidenceCellSchema(org_id="101", tbl_id="DT_1ZB7024", itm_id="T00", prd_se="Y", prd_de=period, dimension_codes={"C1":"00","C2":age,"C3":"B00"}, canonical_key=f"{period}-{age}", status="CONFIRMED")
        return fetcher.fetch(cell, article_date=date(2025, 5, 1)).value
    share_2023 = calculate(CalculationPlan(calculation_type="SHARE"), [value("2023", "A08"), value("2023", "A09"), value("2023", "A00")])
    share_2024 = calculate(CalculationPlan(calculation_type="SHARE"), [value("2024", "A08"), value("2024", "A09"), value("2024", "A00")])
    change = calculate(CalculationPlan(calculation_type="DIFFERENCE"), [share_2024, share_2023])
    verdict = make_verdict("NEWS_B-016-A01", 2.9, [share_2023, share_2024], change, tolerance=0.05)
    assert round(share_2023, 1) == 48.0 and round(share_2024, 1) == 50.9
    assert (verdict.verdict, verdict.route_status) == ("MATCH", "AUTO")
