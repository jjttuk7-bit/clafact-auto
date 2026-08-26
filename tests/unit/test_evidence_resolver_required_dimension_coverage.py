from core.evidence_resolver import resolve_evidence_cell
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema


def test_age_population_must_be_present_in_final_coordinate() -> None:
    claim = ClaimSchema(
        claim_id="age-education",
        source_sentence="30대 대졸 이상 실업률은 2.4%였다.",
        indicator="실업률",
        value=2.4,
        unit="%",
        time="2025년 1분기",
        frequency="분기",
        population="30대",
        dimension={"학력": "대졸 이상"},
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )
    education_only = KosisCandidateSchema(
        org_id="101",
        tbl_id="DT_EDU_ONLY",
        tbl_name="교육정도별 경제활동인구",
        core_item_ids=["T80"],
        core_item_names=["실업률"],
        dimension_ids=["H"],
        dimension_names=["교육정도별"],
        dimension_members={"H": ["계", "대졸이상"]},
        dimension_member_codes={"H": {"계": "00", "대졸이상": "40"}},
        unit_names=["%"],
        frequency="분기",
        metadata_status="OFFICIAL_METADATA_READY",
    )

    cell = resolve_evidence_cell(claim, education_only)

    assert cell.status == "UNRESOLVED"

def test_composite_population_does_not_duplicate_explicit_age_and_education_axes() -> None:
    claim = ClaimSchema(
        claim_id="age-education-composite",
        source_sentence="지난 1분기 기준 30대 고졸 실업률은 4.2%였다.",
        indicator="실업률",
        value=4.2,
        unit="%",
        time="2025년 1분기",
        frequency="분기",
        population="30대 고졸",
        dimension={"age": "30대", "education": "고졸"},
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )
    candidate = KosisCandidateSchema(
        org_id="101",
        tbl_id="DT_AGE_EDU",
        tbl_name="연령/교육정도별 실업률",
        core_item_ids=["T80"],
        core_item_names=["실업률"],
        dimension_ids=["G", "H"],
        dimension_names=["연령계층별", "교육정도별"],
        dimension_members={"G": ["계", "30 - 39세"], "H": ["계", "고졸"]},
        dimension_member_codes={"G": {"계": "00", "30 - 39세": "30"}, "H": {"계": "00", "고졸": "30"}},
        unit_names=["%"],
        item_units={"T80": "%"},
        frequency="분기|년",
        metadata_status="OFFICIAL_METADATA_READY",
    )

    cell = resolve_evidence_cell(claim, candidate)

    assert cell.status == "CONFIRMED"
    assert cell.dimension_members == {"G": "30 - 39세", "H": "고졸"}
