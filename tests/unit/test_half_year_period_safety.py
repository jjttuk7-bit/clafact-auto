from core.calculation_planner import build_calculation_plan
from core.catalog_metadata_refresh import _with_period_metadata
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.evidence import EvidenceCellSchema


def test_half_year_metadata_is_not_mislabeled_as_quarterly() -> None:
    candidate = KosisCandidateSchema(
        org_id="101",
        tbl_id="DT_MIXED",
        tbl_name="혼합 주기 표",
        metadata_status="OFFICIAL_ITEM_METADATA_READY",
    )

    refreshed = _with_period_metadata(candidate, [
        {"PRD_SE": "반기", "STRT_PRD_DE": "2013 1/2", "END_PRD_DE": "2025 2/2"},
        {"PRD_SE": "월", "STRT_PRD_DE": "2013.01", "END_PRD_DE": "2025.12"},
    ])

    assert refreshed.frequency == "월"
    assert set(refreshed.period_ranges) == {"월"}


def test_legacy_fallback_rejects_any_unrecognized_declared_frequency() -> None:
    claim = ClaimSchema(
        claim_id="record",
        source_sentence="고용률은 2025년 6월 역대 최대였다.",
        calculation="RECORD_HIGH",
        comparison={"type": "RECORD_HIGH"},
        parse_status="AUTO_OK",
    )
    current = EvidenceCellSchema(
        org_id="101",
        tbl_id="DT_MIXED",
        itm_id="T",
        prd_se="월",
        prd_de="2025-06",
        canonical_key="DT_MIXED|2025-06",
        status="CONFIRMED",
    )
    candidate = KosisCandidateSchema(
        org_id="101",
        tbl_id="DT_MIXED",
        tbl_name="월·반기 혼합 표",
        frequency="월|반기",
        start_period="2013.01",
        metadata_status="OFFICIAL_METADATA_READY",
    )

    assert build_calculation_plan(claim, current, candidate) is None
