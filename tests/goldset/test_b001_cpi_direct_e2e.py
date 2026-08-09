from datetime import date
from pathlib import Path

from core.calculator import calculate
from core.kosis_fetcher import OfficialValueFetcher
from core.verdict_engine import make_verdict
from schemas.evidence import CalculationPlan, EvidenceCellSchema


def test_goldset_b001_reproduces_cpi_index_and_yoy() -> None:
    fetcher = OfficialValueFetcher([Path("data/kosis_snapshots/official_goldset_v3_news_b001_index.json"), Path("data/kosis_snapshots/official_goldset_v3_news_b001_yoy.json")])
    index = fetcher.fetch(EvidenceCellSchema(org_id="101", tbl_id="DT_1J22003", itm_id="CPI_TOTAL", prd_se="M", prd_de="202505", canonical_key="index", status="CONFIRMED"), article_date=date(2025, 6, 4))
    yoy = fetcher.fetch(EvidenceCellSchema(org_id="101", tbl_id="DT_1J22042", itm_id="YOY_TOTAL", prd_se="M", prd_de="202505", canonical_key="yoy", status="CONFIRMED"), article_date=date(2025, 6, 4))
    index_verdict = make_verdict("NEWS_B-001-A01", 116.27, [index.value], calculate(CalculationPlan(calculation_type="DIRECT_VALUE"), [index.value]), tolerance=0.01)
    yoy_verdict = make_verdict("NEWS_B-001-A01", 1.9, [yoy.value], calculate(CalculationPlan(calculation_type="DIRECT_VALUE"), [yoy.value]), tolerance=0.01)
    assert (index_verdict.verdict, yoy_verdict.verdict) == ("MATCH", "MATCH")
