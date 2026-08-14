import pytest

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

def test_builds_growth_plan_from_openai_period_alias() -> None:
    claim = ClaimSchema(
        claim_id="C3",
        source_sentence="",
        comparison={"period": "전년 동월 대비"},
        parse_status="AUTO_OK",
    )
    current = EvidenceCellSchema(
        org_id="101", tbl_id="DT", itm_id="T", prd_se="M", prd_de="202510", canonical_key="now", status="CONFIRMED"
    )

    plan = build_calculation_plan(claim, current)

    assert plan is not None
    assert [cell.prd_de for cell in plan.required_cells] == ["202510", "202410"]

def test_builds_share_plan_with_part_and_explicit_total_member() -> None:
    from schemas.candidate import KosisCandidateSchema

    claim = ClaimSchema(
        claim_id="share-1", source_sentence="청년 취업자 비중은 27%다.",
        value=27, unit="%", time="2024년 12월", frequency="월",
        calculation="SHARE",
        comparison={"type": "SHARE_OF_TOTAL", "numerator": "청년 취업자 수", "denominator": "전체 취업자 수", "denominator_member": "전체"},
        parse_status="AUTO_OK",
    )
    current = EvidenceCellSchema(
        org_id="101", tbl_id="DT_EMP", itm_id="T", prd_se="월", prd_de="2024-12",
        dimension_members={"C1": "청년"}, dimension_codes={"C1": "YOUTH"},
        canonical_key="ORG=101|TBL=DT_EMP|ITM=T|PRD_DE=2024-12|C1:청년", unit="천명", status="CONFIRMED",
    )
    candidate = KosisCandidateSchema(
        org_id="101", tbl_id="DT_EMP", tbl_name="연령별 취업자 수", core_item_ids=["T"], core_item_names=["취업자 수"],
        dimension_ids=["C1"], dimension_names=["연령별"],
        dimension_members={"C1": ["청년", "중장년", "전체"]},
        dimension_member_codes={"C1": {"청년": "YOUTH", "중장년": "MID", "전체": "TOTAL"}},
        unit_names=["천명"], item_units={"T": "천명"}, frequency="월", metadata_status="OFFICIAL_METADATA_READY",
    )

    plan = build_calculation_plan(claim, current, candidate)

    assert plan is not None
    assert plan.calculation_type == "SHARE"
    assert [cell.dimension_codes for cell in plan.required_cells] == [{"C1": "YOUTH"}, {"C1": "TOTAL"}]

@pytest.mark.parametrize("calculation", ["RATIO", "MULTIPLE"])
def test_builds_ratio_family_plan_with_explicit_reference_member(calculation: str) -> None:
    from schemas.candidate import KosisCandidateSchema

    claim = ClaimSchema(
        claim_id=f"{calculation}-1", source_sentence="여성은 남성의 1.2배다.",
        value=1.2, unit="배", time="2024년 12월", frequency="월", calculation=calculation,
        comparison={"numerator": "여성 취업자 수", "denominator": "남성 취업자 수", "denominator_member": "남성"},
        dimension={"성별": "여성"}, parse_status="AUTO_OK",
    )
    current = EvidenceCellSchema(
        org_id="101", tbl_id="DT_EMP", itm_id="T", prd_se="월", prd_de="2024-12",
        dimension_members={"C1": "여성"}, dimension_codes={"C1": "F"},
        canonical_key="ORG=101|TBL=DT_EMP|ITM=T|C1:여성", unit="천명", status="CONFIRMED",
    )
    candidate = KosisCandidateSchema(
        org_id="101", tbl_id="DT_EMP", tbl_name="성별 취업자 수", core_item_ids=["T"], core_item_names=["취업자 수"],
        dimension_ids=["C1"], dimension_names=["성별"], dimension_members={"C1": ["남성", "여성"]},
        dimension_member_codes={"C1": {"남성": "M", "여성": "F"}}, unit_names=["천명"],
        item_units={"T": "천명"}, frequency="월", metadata_status="OFFICIAL_METADATA_READY",
    )

    plan = build_calculation_plan(claim, current, candidate)

    assert plan is not None
    assert [cell.dimension_codes for cell in plan.required_cells] == [{"C1": "F"}, {"C1": "M"}]

def test_builds_rank_plan_for_all_members_on_explicit_rank_axis() -> None:
    from schemas.candidate import KosisCandidateSchema

    claim = ClaimSchema(
        claim_id="rank-1", source_sentence="반도체 수출은 1위다.", value=1, unit="위", time="2024년 12월", frequency="월",
        calculation="RANK", dimension={"품목": "반도체"},
        condition={"rank_value": "1", "order": "DESC", "population_scope": "전체 수출 품목", "rank_axis": "품목"}, parse_status="AUTO_OK",
    )
    current = EvidenceCellSchema(org_id="101", tbl_id="DT_EXP", itm_id="T", prd_se="월", prd_de="2024-12", dimension_members={"C1": "반도체"}, dimension_codes={"C1": "S"}, canonical_key="DT_EXP|C1:반도체", unit="천달러", status="CONFIRMED")
    candidate = KosisCandidateSchema(
        org_id="101", tbl_id="DT_EXP", tbl_name="품목별 수출액", core_item_ids=["T"], core_item_names=["수출액"],
        dimension_ids=["C1"], dimension_names=["품목별"], dimension_members={"C1": ["반도체", "자동차", "선박", "계"]},
        dimension_member_codes={"C1": {"반도체": "S", "자동차": "C", "선박": "V", "계": "T"}}, unit_names=["천달러"], item_units={"T": "천달러"}, frequency="월", metadata_status="OFFICIAL_METADATA_READY",
    )

    plan = build_calculation_plan(claim, current, candidate)

    assert plan is not None
    assert plan.calculation_type == "RANK"
    assert [cell.dimension_codes["C1"] for cell in plan.required_cells] == ["S", "C", "V"]


def test_builds_threshold_plan_with_literal_boundary() -> None:
    claim = ClaimSchema(
        claim_id="threshold-1", source_sentence="실업률은 4%를 넘었다.", value=1, unit="%", time="2024년 12월", frequency="월",
        calculation="THRESHOLD", condition={"operator": "GT", "threshold_value": "4", "threshold_unit": "%"}, parse_status="AUTO_OK",
    )
    current = EvidenceCellSchema(org_id="101", tbl_id="DT_UNEMP", itm_id="T", prd_se="월", prd_de="2024-12", canonical_key="DT_UNEMP", unit="%", status="CONFIRMED")

    plan = build_calculation_plan(claim, current)

    assert plan is not None
    assert plan.required_cells == [current]
    assert plan.literal_values == [4.0]
    assert plan.operator == "GT"

def test_builds_difference_plan_with_two_year_over_year_cells() -> None:
    claim = ClaimSchema(claim_id="diff-1", source_sentence="", calculation="DIFFERENCE", comparison={"type": "YEAR_OVER_YEAR"}, parse_status="AUTO_OK")
    current = EvidenceCellSchema(org_id="101", tbl_id="DT", itm_id="T", prd_se="월", prd_de="2024-12", canonical_key="DT|PRD_DE=2024-12", status="CONFIRMED")

    plan = build_calculation_plan(claim, current)

    assert plan is not None
    assert plan.calculation_type == "DIFFERENCE"
    assert [cell.prd_de for cell in plan.required_cells] == ["2024-12", "2023-12"]

def test_share_counterpart_rewrites_single_dimension_member_and_canonical_key() -> None:
    from schemas.candidate import KosisCandidateSchema

    claim = ClaimSchema(
        claim_id="share-key", source_sentence="여성 취업자 수는 전체의 44%였다.",
        calculation="SHARE", comparison={"denominator_member": "전체"}, parse_status="AUTO_OK",
    )
    current = EvidenceCellSchema(
        org_id="101", tbl_id="DT_EMP", itm_id="T30", obj_id="B", member_code="여자",
        prd_se="월", prd_de="2024-12", dimension_members={"B": "여자"},
        dimension_codes={"B": "3"},
        canonical_key="ORG=101|TBL=DT_EMP|ITM=T30|OBJ=B|MEMBER=여자|PRD_SE=월|PRD_DE=2024-12",
        unit="천명", status="CONFIRMED",
    )
    candidate = KosisCandidateSchema(
        org_id="101", tbl_id="DT_EMP", tbl_name="성별 취업자", core_item_ids=["T30"],
        core_item_names=["취업자"], dimension_ids=["B"], dimension_names=["성별"],
        dimension_members={"B": ["계", "여자"]}, dimension_member_codes={"B": {"계": "0", "여자": "3"}},
        unit_names=["천명"], frequency="월", metadata_status="OFFICIAL_METADATA_READY",
    )

    plan = build_calculation_plan(claim, current, candidate)

    assert plan is not None
    denominator = plan.required_cells[1]
    assert denominator.member_code == "계"
    assert denominator.canonical_key.endswith("MEMBER=계|PRD_SE=월|PRD_DE=2024-12")
    assert denominator.canonical_key != current.canonical_key