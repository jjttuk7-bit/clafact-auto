from core.evidence_resolver import resolve_evidence_cell
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema


def test_full_province_name_maps_to_official_abbreviation_coordinate() -> None:
    claim = ClaimSchema(
        claim_id="province-coordinate",
        source_sentence="2024년 경상북도 농가 수는 10만 가구였다.",
        indicator="농가 수",
        value=100_000,
        unit="가구",
        time="2024년",
        frequency="년",
        region="경상북도",
        parse_status="AUTO_OK",
    )
    candidate = KosisCandidateSchema(
        org_id="101",
        tbl_id="DT_FARM",
        tbl_name="시도별 농가 수",
        core_item_ids=["T"],
        core_item_names=["농가 수"],
        dimension_ids=["C1"],
        dimension_names=["시도별"],
        dimension_members={"C1": ["전국", "경북", "경남"]},
        dimension_member_codes={"C1": {"전국": "00", "경북": "47", "경남": "48"}},
        unit_names=["가구"],
        frequency="년",
        metadata_status="OFFICIAL_METADATA_READY",
    )

    cell = resolve_evidence_cell(claim, candidate)

    assert cell.status == "CONFIRMED"
    assert cell.dimension_members == {"C1": "경북"}
    assert cell.dimension_codes == {"C1": "47"}
