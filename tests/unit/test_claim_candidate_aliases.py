from core.claim_candidate_aliases import normalize_claim_for_candidate
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema


def test_education_shorthand_maps_only_to_confirmed_official_member() -> None:
    claim = ClaimSchema(
        claim_id="EDU-1", source_sentence="2024년 대졸 실업률은 3.1%였다.",
        indicator="실업률", value=3.1, unit="%", time="2024년", frequency="년",
        dimension={"학력": "대졸"}, calculation="DIRECT_VALUE", parse_status="AUTO_OK",
    )
    candidate = KosisCandidateSchema(
        org_id="101", tbl_id="DT_1DA7103S", tbl_name="교육정도별 실업률",
        dimension_members={"H1": ["계", "고졸", "대졸이상", "전문대졸"]},
        metadata_status="READY",
    )
    normalized = normalize_claim_for_candidate(claim, candidate)
    assert normalized.dimension == {"교육정도": "대졸이상"}

def test_raw_json_youth_dimension_maps_to_confirmed_official_age_member() -> None:
    claim = ClaimSchema(
        claim_id="YOUTH-RAW-1", source_sentence="청년층 쉬었음 인구는 50만 명이었다.",
        indicator="비경제활동인구", value=500_000, unit="명", time="2024년",
        frequency="년", population="청년", dimension={"raw": '{"연령집단": "청년"}'},
        calculation="DIRECT_VALUE", parse_status="AUTO_OK",
    )
    candidate = KosisCandidateSchema(
        org_id="101", tbl_id="DT_1DA7147S",
        tbl_name="연령/활동상태별(쉬었음) 비경제활동인구",
        dimension_names=["연령계층별", "활동상태별"],
        dimension_members={"G": ["계", "15 - 29세"], "M": ["쉬었음"]},
        metadata_status="READY",
    )

    normalized = normalize_claim_for_candidate(claim, candidate)

    assert normalized.dimension == {"연령": "15 - 29세"}


def test_descriptive_youth_population_maps_to_confirmed_official_age_member() -> None:
    claim = ClaimSchema(
        claim_id="YOUTH-DESCRIPTOR-1",
        source_sentence="사회 초년생인 청년층 고용률은 46.2%였다.",
        indicator="고용률", value=46.2, unit="%", time="2025년 6월",
        frequency="월", population="사회 초년생인 청년층",
        calculation="DIRECT_VALUE", parse_status="AUTO_OK",
    )
    candidate = KosisCandidateSchema(
        org_id="101", tbl_id="DT_1DA7002S", tbl_name="연령별 고용률",
        dimension_names=["연령계층별"],
        dimension_members={"G": ["15세 이상 전체", "15 - 29세"]},
        metadata_status="READY",
    )

    normalized = normalize_claim_for_candidate(claim, candidate)

    assert normalized.population == "15 - 29세"


def test_birth_year_and_generation_descriptors_are_not_official_dimensions() -> None:
    claim = ClaimSchema(
        claim_id="BIRTH-DESCRIPTOR-1",
        source_sentence="1992년생은 출생아 수가 73만명이었다.",
        indicator="출생아 수", value=730_000, unit="명", time="1992년",
        frequency="년", population="1992년생",
        dimension={"출생연도": "1992년생", "세대": "2차 에코 붐 세대"},
        calculation="DIRECT_VALUE", parse_status="AUTO_OK",
    )
    candidate = KosisCandidateSchema(
        org_id="101", tbl_id="DT_1B8000G", tbl_name="출생사망혼인이혼",
        dimension_names=["행정구역별", "종류별"],
        dimension_members={"B": ["전국"], "A": ["출생아수(명)"]},
        metadata_status="READY",
    )

    normalized = normalize_claim_for_candidate(claim, candidate)

    assert normalized.population is None
    assert normalized.dimension is None
