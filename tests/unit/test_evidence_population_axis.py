from core.evidence_resolver_v2 import resolve_evidence_cell_v2 as resolve_evidence_cell
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema


def _candidate() -> KosisCandidateSchema:
    return KosisCandidateSchema(
        org_id="101", tbl_id="DT_1DA7147S",
        tbl_name="연령/활동상태별(쉬었음) 비경제활동인구",
        core_item_ids=["T50"], core_item_names=["비경제활동인구"],
        dimension_ids=["G", "M"], dimension_names=["연령계층별", "활동상태별"],
        dimension_members={"G": ["계", "15 - 29세"], "M": ["쉬었음"]},
        dimension_member_codes={
            "G": {"계": "00", "15 - 29세": "75"}, "M": {"쉬었음": "905"},
        },
        unit_names=["천명"], item_units={"T50": "천명"}, frequency="월",
        source_stat_id="OFFICIAL_RECURRING_DOMAIN_BINDING",
        metadata_status="OFFICIAL_METADATA_READY",
    )


def _claim(population: str) -> ClaimSchema:
    return ClaimSchema(
        claim_id="resting-population",
        source_sentence="2025년 5월 쉬었음 인구는 239만 명이었다.",
        indicator="쉬었음 인구", value=2_390_000, unit="명",
        time="2025년 5월", frequency="월", population=population,
        calculation="DIRECT_VALUE", parse_status="AUTO_OK",
    )


def test_descriptive_population_is_not_misused_as_an_age_coordinate() -> None:
    cell = resolve_evidence_cell(
        _claim("일도, 구직 활동도 하지 않은 사람 중 그냥 시간을 보낸 인구"),
        _candidate(),
    )

    assert cell.status == "CONFIRMED"
    assert cell.dimension_members == {"G": "계", "M": "쉬었음"}


def test_explicit_age_population_still_requires_exact_age_member() -> None:
    cell = resolve_evidence_cell(_claim("15~29세"), _candidate())

    assert cell.status == "CONFIRMED"
    assert cell.dimension_members["G"] == "15 - 29세"
