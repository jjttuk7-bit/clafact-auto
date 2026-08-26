from core.evidence_resolver import resolve_evidence_cell
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema


def _claim(*, indicator: str = "취업자 수", dimension: dict[str, str]) -> ClaimSchema:
    return ClaimSchema(
        claim_id="explicit-dimension",
        source_sentence="",
        indicator=indicator,
        value=1.0,
        unit="%" if indicator == "실업률" else "명",
        time="2025-01",
        frequency="월",
        dimension=dimension,
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )


def _candidate(
    *,
    item: str,
    unit: str,
    axis_name: str,
    members: list[str],
) -> KosisCandidateSchema:
    return KosisCandidateSchema(
        org_id="101",
        tbl_id="DT_EXPLICIT",
        tbl_name="explicit dimensions",
        core_item_ids=["T1"],
        core_item_names=[item],
        dimension_ids=["I"],
        dimension_names=[axis_name],
        dimension_members={"I": members},
        dimension_member_codes={"I": {name: str(index) for index, name in enumerate(members)}},
        unit_names=[unit],
        frequency="월",
        metadata_status="OFFICIAL_METADATA_READY",
    )


def test_explicit_industry_never_falls_back_to_total_member() -> None:
    cell = resolve_evidence_cell(
        _claim(dimension={"산업": "건설업"}),
        _candidate(item="취업자 수", unit="명", axis_name="산업별", members=["계", "제조업"]),
    )

    assert cell.status == "UNRESOLVED"
    assert cell.dimension_members == {}


def test_explicit_education_never_falls_back_to_total_member() -> None:
    cell = resolve_evidence_cell(
        _claim(indicator="실업률", dimension={"학력": "대졸 이상"}),
        _candidate(item="실업률", unit="%", axis_name="교육정도별", members=["계", "고졸"]),
    )

    assert cell.status == "UNRESOLVED"
    assert cell.dimension_members == {}


def test_explicit_industry_matches_unique_official_coded_label() -> None:
    cell = resolve_evidence_cell(
        _claim(dimension={"산업": "건설업"}),
        _candidate(
            item="취업자 수", unit="명", axis_name="산업별",
            members=["계", "C 제조업(10~34)", "F 건설업(41~42)"],
        ),
    )
    assert cell.status == "CONFIRMED"
    assert cell.dimension_members == {"I": "F 건설업(41~42)"}
