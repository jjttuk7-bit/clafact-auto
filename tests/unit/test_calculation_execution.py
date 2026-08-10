from datetime import date

from core.calculation_execution import execute_calculation_plan
from core.kosis_fetcher import KosisValue
from schemas.evidence import CalculationPlan, EvidenceCellSchema


def _cell(period: str) -> EvidenceCellSchema:
    return EvidenceCellSchema(org_id="101", tbl_id="DT", itm_id="T", prd_se="M", prd_de=period, canonical_key=period, status="CONFIRMED")


class _Fetcher:
    def fetch(self, cell: EvidenceCellSchema, *, article_date: date | None = None) -> KosisValue:
        return KosisValue({"202510": 136.62, "202410": 208.57}[cell.prd_de], "SUCCESS", f"hash-{cell.prd_de}")


def test_executes_multi_cell_growth_rate_with_snapshot_hashes() -> None:
    plan = CalculationPlan(calculation_type="GROWTH_RATE", required_cells=[_cell("202510"), _cell("202410")])
    result = execute_calculation_plan(plan, _Fetcher(), article_date=date(2025, 11, 1))
    assert result.status == "SUCCESS"
    assert round(result.calculated_value or 0, 1) == -34.5
    assert result.snapshot_hashes == ["hash-202510", "hash-202410"]
