from datetime import date

from core.calculation_execution import execute_calculation_plan
from core.calculation_planner import build_calculation_plan
from core.kosis_fetcher import KosisValue
from schemas.claim import ClaimSchema
from schemas.evidence import EvidenceCellSchema


class _Fetcher:
    def fetch(self, cell, *, article_date=None):
        return KosisValue(136.62 if cell.prd_de == "202510" else 208.57, "SUCCESS", cell.prd_de)


def test_growth_claim_plan_and_execution_reproduce_baechu_example() -> None:
    claim = ClaimSchema(claim_id="baechu", source_sentence="", value=-34.5, unit="%", calculation="GROWTH_RATE", comparison={"basis":"전년 동월 대비"}, parse_status="AUTO_OK")
    cell = EvidenceCellSchema(org_id="101", tbl_id="DT_1J22112", itm_id="T", dimension_codes={"C1":"T10","C2":"A02A01701"}, prd_se="M", prd_de="202510", canonical_key="DT_1J22112|T|202510|C1:T10|C2:A02A01701", status="CONFIRMED")
    plan = build_calculation_plan(claim, cell)
    assert plan is not None
    execution = execute_calculation_plan(plan, _Fetcher(), article_date=date(2025, 11, 1))
    assert round(execution.calculated_value or 0, 1) == -34.5
