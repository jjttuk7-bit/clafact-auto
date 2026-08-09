from datetime import date
from pathlib import Path

from core.calculator import calculate
from core.kosis_fetcher import OfficialValueFetcher
from schemas.evidence import CalculationPlan, EvidenceCellSchema


def test_goldset_b003_reproduces_highest_april_birth_growth_rank() -> None:
    fetcher = OfficialValueFetcher([Path("data/kosis_snapshots/official_goldset_v3_news_b003.json")])
    def rate(period: str) -> float:
        cell = EvidenceCellSchema(org_id="101", tbl_id="DT_1B8000G", itm_id="T1", prd_se="M", prd_de=period, dimension_codes={"C1":"00","C2":"10"}, canonical_key=period, status="CONFIRMED")
        return fetcher.fetch(cell, article_date=date(2025, 6, 25)).value
    assert calculate(CalculationPlan(calculation_type="RANK"), [rate("202504"), rate("199104")]) == 1.0
