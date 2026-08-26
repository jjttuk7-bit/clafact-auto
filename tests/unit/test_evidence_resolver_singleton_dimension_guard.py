from core.evidence_resolver import resolve_evidence_cell
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema


def test_explicit_industry_never_uses_singleton_total_axis() -> None:
    claim = ClaimSchema(
        claim_id="industry-singleton",
        source_sentence="건설업 취업자는 190만9000명이다.",
        indicator="취업자",
        value=1_909_000,
        unit="명",
        time="2025-02",
        frequency="월",
        dimension={"산업": "건설업"},
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )
    candidate = KosisCandidateSchema(
        org_id="101",
        tbl_id="DT_TOTAL_ONLY",
        tbl_name="전체 취업자",
        core_item_ids=["T30"],
        core_item_names=["취업자"],
        dimension_ids=["I"],
        dimension_names=["산업별"],
        dimension_members={"I": ["계"]},
        dimension_member_codes={"I": {"계": "00"}},
        unit_names=["천명"],
        frequency="월",
        metadata_status="OFFICIAL_METADATA_READY",
    )

    cell = resolve_evidence_cell(claim, candidate)

    assert cell.status == "UNRESOLVED"
    assert cell.dimension_members == {}
