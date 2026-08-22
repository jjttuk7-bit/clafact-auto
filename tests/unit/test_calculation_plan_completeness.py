from core.calculation_planner import build_calculation_plan
from schemas.claim import ClaimSchema
from schemas.evidence import EvidenceCellSchema


def test_month_over_month_plan_includes_previous_month_across_year_boundary() -> None:
    claim = ClaimSchema(
        claim_id="mom-plan",
        source_sentence="2025년 1월 실업률은 전월보다 0.1%포인트 하락했다.",
        calculation="DIFFERENCE",
        comparison={"type": "MONTH_OVER_MONTH"},
        parse_status="AUTO_OK",
    )
    current = EvidenceCellSchema(
        org_id="101",
        tbl_id="DT_UNEMP",
        itm_id="T",
        prd_se="월",
        prd_de="2025-01",
        canonical_key="DT_UNEMP|PRD_DE=2025-01",
        status="CONFIRMED",
    )

    plan = build_calculation_plan(claim, current)

    assert plan is not None
    assert [cell.prd_de for cell in plan.required_cells] == ["2025-01", "2024-12"]
    assert plan.required_cells[1].canonical_key.endswith("PRD_DE=2024-12")
