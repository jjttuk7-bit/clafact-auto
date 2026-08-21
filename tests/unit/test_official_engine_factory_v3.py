from core.official_engine_factory_v3 import merge_catalog_resolutions
from core.official_evidence_service import CatalogResolution
from schemas.candidate import KosisCandidateSchema


def _candidate(table_id: str) -> KosisCandidateSchema:
    return KosisCandidateSchema(
        org_id="101",
        tbl_id=table_id,
        tbl_name=table_id,
        metadata_status="STRUCTURAL_READY",
    )


def test_merge_catalog_resolutions_deduplicates_official_identity() -> None:
    base = CatalogResolution([_candidate("A")], {"candidate_count": 1})
    overlay = CatalogResolution([_candidate("A"), _candidate("B")], {"candidate_count": 2})

    merged = merge_catalog_resolutions(base, overlay)

    assert [candidate.tbl_id for candidate in merged.candidates] == ["A", "B"]
    assert merged.diagnostics["base_candidate_count"] == 1
    assert merged.diagnostics["overlay_candidate_count"] == 2
