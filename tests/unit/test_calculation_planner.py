from core.calculation_planner import build_calculation_plan
from schemas.claim import ClaimSchema
from schemas.evidence import EvidenceCellSchema


def test_builds_year_over_year_growth_plan_with_two_periods() -> None:
    claim = ClaimSchema(claim_id="C1", source_sentence="", calculation="GROWTH_RATE", comparison={"basis":"전년 동월 대비"}, parse_status="AUTO_OK")
    current = EvidenceCellSchema(org_id="101", tbl_id="DT", itm_id="T", prd_se="M", prd_de="202510", canonical_key="now", status="CONFIRMED")
    plan = build_calculation_plan(claim, current)
    assert plan is not None
    assert plan.calculation_type == "GROWTH_RATE"
    assert [cell.prd_de for cell in plan.required_cells] == ["202510", "202410"]


def test_infers_growth_rate_from_exact_yoy_basis_without_calculation_slot() -> None:
    claim = ClaimSchema(
        claim_id="C2",
        source_sentence="",
        comparison={"basis": "전년 동월 대비"},
        parse_status="AUTO_OK",
    )
    current = EvidenceCellSchema(
        org_id="101", tbl_id="DT", itm_id="T", prd_se="M", prd_de="202510", canonical_key="now", status="CONFIRMED"
    )

    plan = build_calculation_plan(claim, current)

    assert plan is not None
    assert plan.calculation_type == "GROWTH_RATE"