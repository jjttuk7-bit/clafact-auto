from core.evidence_resolver_v2 import enrich_claim_for_official_axes
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema


def _candidate(members):
    return KosisCandidateSchema(
        org_id="101", tbl_id="T", tbl_name="T", core_item_ids=["T1"],
        core_item_names=["통계값"], dimension_ids=["C2"], dimension_names=["종류별"],
        dimension_members={"C2": members}, unit_names=["명"], frequency="월",
        metadata_status="STRUCTURAL_READY",
    )


def test_birth_indicator_selects_kind_axis_member() -> None:
    claim = ClaimSchema(claim_id="c", source_sentence="s", indicator="출생아 수", value=1, unit="명", time="2025년 1월", calculation="DIRECT_VALUE", parse_status="AUTO_OK")
    enriched = enrich_claim_for_official_axes(claim, _candidate(["출생아수", "사망자수"]))
    assert enriched.dimension == {"종류별": "출생아수"}


def test_cpi_defaults_to_total_index_member() -> None:
    claim = ClaimSchema(claim_id="c", source_sentence="s", indicator="소비자물가지수", value=1, unit="2020=100", time="2025년 1월", calculation="DIRECT_VALUE", parse_status="AUTO_OK")
    enriched = enrich_claim_for_official_axes(claim, _candidate(["총지수", "외식"]))
    assert enriched.dimension == {"종류별": "총지수"}
