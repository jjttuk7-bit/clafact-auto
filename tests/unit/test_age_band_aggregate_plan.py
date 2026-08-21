from core.calculation_planner import build_calculation_plan
from core.calculator import calculate
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.evidence import EvidenceCellSchema


def test_eighties_death_difference_uses_two_age_cells_per_year() -> None:
    claim = ClaimSchema(
        claim_id="D", source_sentence="80대 사망자는 전년 대비 400명 줄었다.",
        indicator="사망자 수", value=400, unit="명", time="2024", frequency="년",
        dimension={"age": "80대"}, comparison={"type": "YEAR_OVER_YEAR"},
        calculation="DIFFERENCE", condition={"direction": "DECREASE"}, parse_status="AUTO_OK",
    )
    current = EvidenceCellSchema(
        org_id="101", tbl_id="DT_1B80A13", itm_id="T2",
        dimension_members={"SBB": "계", "YRE": "80 - 84세"},
        dimension_codes={"SBB": "0", "YRE": "360"}, prd_se="년", prd_de="2024",
        unit="명", canonical_key="ORG=101|TBL=DT_1B80A13|PRD_DE=2024|DIMS=SBB:계,YRE:80 - 84세",
        status="CONFIRMED",
    )
    candidate = KosisCandidateSchema(
        org_id="101", tbl_id="DT_1B80A13", tbl_name="성/연령(5세)별 사망자수",
        core_item_ids=["T2"], core_item_names=["사망"], unit_names=["명"],
        dimension_ids=["SBB", "YRE"], dimension_names=["성별", "연령(5세)별"],
        dimension_members={"SBB": ["계"], "YRE": ["80 - 84세", "85 - 89세"]},
        dimension_member_codes={"SBB": {"계": "0"}, "YRE": {"80 - 84세": "360", "85 - 89세": "380"}},
        frequency="년", metadata_status="OFFICIAL_METADATA_READY",
    )

    plan = build_calculation_plan(claim, current, candidate)
    assert plan is not None
    assert plan.calculation_type == "SUM_DIFFERENCE"
    assert [(c.dimension_codes["YRE"], c.prd_de) for c in plan.required_cells] == [
        ("360", "2024"), ("380", "2024"), ("360", "2023"), ("380", "2023")
    ]
    assert calculate(plan, [63769, 68907, 66302, 66674]) == -300
