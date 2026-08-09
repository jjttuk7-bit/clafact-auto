from datetime import date
from pathlib import Path

from core.calculator import calculate
from core.kosis_fetcher import OfficialValueFetcher
from schemas.evidence import CalculationPlan, EvidenceCellSchema


def test_goldset_seed019_reproduces_household_and_aging_changes() -> None:
    fetcher = OfficialValueFetcher([Path("data/kosis_snapshots/official_goldset_v3_seed019_households.json"), Path("data/kosis_snapshots/official_goldset_v3_seed019_population.json")])
    def value(table: str, item: str, period: str, code: str | None = None) -> float:
        cell = EvidenceCellSchema(org_id="101", tbl_id=table, itm_id=item, prd_se="Y", prd_de=period, dimension_codes={"C2":code} if code else {}, canonical_key=f"{table}-{period}-{code}", status="CONFIRMED")
        return fetcher.fetch(cell, article_date=date(2025, 5, 1)).value
    household_growth = calculate(CalculationPlan(calculation_type="GROWTH_RATE"), [value("DT_1FA7001","FORESTRY_HOUSEHOLDS","2024"), value("DT_1FA7001","FORESTRY_HOUSEHOLDS","2023")])
    share_2023 = calculate(CalculationPlan(calculation_type="SHARE"), [value("DT_1FA7009","FORESTRY_POPULATION","2023","AGED65PLUS"), value("DT_1FA7009","FORESTRY_POPULATION","2023","TOTAL")])
    share_2024 = calculate(CalculationPlan(calculation_type="SHARE"), [value("DT_1FA7009","FORESTRY_POPULATION","2024","AGED65PLUS"), value("DT_1FA7009","FORESTRY_POPULATION","2024","TOTAL")])
    assert round(household_growth, 1) == -1.2
    assert round(share_2023, 1) == 52.8 and round(share_2024, 1) == 56.4
    assert round(calculate(CalculationPlan(calculation_type="DIFFERENCE"), [round(share_2024, 1), round(share_2023, 1)]), 1) == 3.6


