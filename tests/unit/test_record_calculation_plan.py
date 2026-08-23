from core.calculation_planner import build_calculation_plan
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.evidence import EvidenceCellSchema


def test_builds_record_high_plan_from_official_metadata_start_period() -> None:
    claim = ClaimSchema(
        claim_id="record",
        source_sentence="\uc218\ucd9c\uc561\uc740 1419\uc5b5\ub2ec\ub7ec\ub85c \uc5ed\ub300 \ucd5c\ub300\uc600\ub2e4.",
        indicator="\uc218\ucd9c\uc561", value=1419, unit="\uc5b5\ub2ec\ub7ec",
        time="2024\ub144", frequency="\ub144", calculation="RECORD_HIGH",
        comparison={"type": "RECORD_HIGH"}, parse_status="AUTO_OK",
    )
    current = EvidenceCellSchema(
        org_id="101", tbl_id="DT_EXP", itm_id="T",
        dimension_members={"C1": "\ubc18\ub3c4\uccb4"}, dimension_codes={"C1": "S"},
        prd_se="\ub144", prd_de="2024", unit="\uc5b5\ub2ec\ub7ec",
        canonical_key="ORG=101|TBL=DT_EXP|ITM=T|C1:\ubc18\ub3c4\uccb4|PRD_DE=2024",
        status="CONFIRMED",
    )
    candidate = KosisCandidateSchema(
        org_id="101", tbl_id="DT_EXP", tbl_name="\ud488\ubaa9\ubcc4 \uc218\ucd9c\uc561",
        core_item_ids=["T"], core_item_names=["\uc218\ucd9c\uc561"],
        dimension_ids=["C1"], dimension_names=["\ud488\ubaa9\ubcc4"],
        dimension_members={"C1": ["\ubc18\ub3c4\uccb4"]},
        dimension_member_codes={"C1": {"\ubc18\ub3c4\uccb4": "S"}},
        unit_names=["\uc5b5\ub2ec\ub7ec"], frequency="\ub144",
        start_period="2022", end_period="2025",
        metadata_status="OFFICIAL_METADATA_READY",
    )

    plan = build_calculation_plan(claim, current, candidate)

    assert plan is not None
    assert plan.calculation_type == "RECORD_HIGH"
    assert [cell.prd_de for cell in plan.required_cells] == ["2022", "2023", "2024"]
    assert all(cell.tbl_id == "DT_EXP" for cell in plan.required_cells)
    assert all(cell.dimension_codes == {"C1": "S"} for cell in plan.required_cells)
    assert len({cell.canonical_key for cell in plan.required_cells}) == 3


def test_record_plan_requires_official_start_period() -> None:
    claim = ClaimSchema(
        claim_id="record", source_sentence="x", indicator="x", value=1, unit="\uac74",
        time="2024\ub144", frequency="\ub144", calculation="RECORD_LOW",
        comparison={"type": "RECORD_LOW"}, parse_status="AUTO_OK",
    )
    current = EvidenceCellSchema(
        org_id="101", tbl_id="DT", itm_id="T", prd_se="\ub144", prd_de="2024",
        canonical_key="DT|PRD_DE=2024", status="CONFIRMED",
    )
    candidate = KosisCandidateSchema(
        org_id="101", tbl_id="DT", tbl_name="x", frequency="\ub144",
        metadata_status="OFFICIAL_METADATA_READY",
    )

    assert build_calculation_plan(claim, current, candidate) is None
