from datetime import date
from pathlib import Path

from core.calculator import calculate
from core.kosis_fetcher import OfficialValueFetcher
from schemas.evidence import CalculationPlan, EvidenceCellSchema


def test_goldset_b023_reproduces_five_item_growth_rates() -> None:
    fetcher = OfficialValueFetcher([Path("data/kosis_snapshots/official_goldset_v3_news_b023.json")])
    expected = {"A02A01701": -34.5, "A02A01708": -40.5, "A01A01101": 21.3, "A03A01601": 21.6, "A05A01405": 6.9}
    for item_code, claim_growth in expected.items():
        def value(period: str) -> float:
            cell = EvidenceCellSchema(org_id="101", tbl_id="DT_1J22112", itm_id="T", prd_se="M", prd_de=period, dimension_codes={"C1":"T10","C2":item_code}, canonical_key=f"{item_code}-{period}", status="CONFIRMED")
            return fetcher.fetch(cell, article_date=date(2025, 11, 4)).value
        growth = calculate(CalculationPlan(calculation_type="GROWTH_RATE"), [value("202510"), value("202410")])
        assert round(growth, 1) == claim_growth
