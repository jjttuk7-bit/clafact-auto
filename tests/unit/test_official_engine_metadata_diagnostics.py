from pathlib import Path

from core.official_engine_factory import OfficialEnginePaths, build_official_evidence_service
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema


def test_factory_reports_safe_metadata_api_error_diagnostics(tmp_path: Path, monkeypatch) -> None:
    import core.official_engine_factory as factory

    paths = OfficialEnginePaths(tmp_path / "concepts.json", tmp_path / "catalog.json", [])
    paths.standard_path.write_text("[]", encoding="utf-8")
    paths.catalog_path.write_text("[]", encoding="utf-8")
    candidate = KosisCandidateSchema(
        org_id="101", tbl_id="DT_EMP", tbl_name="취업자 수", metadata_status="LIVE_SEARCH_UNRESOLVED"
    )

    class FailingRepository:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def __call__(self, *_args, **_kwargs):
            raise RuntimeError("KOSIS_METADATA_API_ERROR_30")

    def refresh(candidates, claim, api_key, *, metadata_fetcher, **_kwargs):
        candidate_to_refresh = list(candidates)[0]
        try:
            metadata_fetcher(api_key, candidate_to_refresh.org_id, candidate_to_refresh.tbl_id, meta_type="ITM")
        except RuntimeError:
            return [candidate_to_refresh.model_copy(update={"metadata_status": "OFFICIAL_ITEM_METADATA_UNAVAILABLE"})]
        raise AssertionError("metadata request must fail in this test")

    monkeypatch.setattr(factory, "KosisMetadataRepository", FailingRepository)
    monkeypatch.setattr(factory, "search_semantic_catalog", lambda *_args: [candidate])
    monkeypatch.setattr(factory, "discover_catalog_candidates", lambda *_args, **_kwargs: [candidate])
    monkeypatch.setattr(factory, "refresh_item_metadata_for_claim", refresh)

    resolution = build_official_evidence_service(paths, kosis_api_key="configured")._catalog_resolver(
        ClaimSchema(claim_id="claim", source_sentence="", indicator="취업자 수", parse_status="AUTO_OK"),
        StandardConceptSchema(concept_id="employment_count", canonical_name="취업자 수", standard_key="employment_count", status="MATCHED"),
    )

    assert resolution.diagnostics["metadata_itm_attempted"] == 1
    assert resolution.diagnostics["metadata_itm_failed"] == 1
    assert resolution.diagnostics["metadata_failure_KOSIS_METADATA_API_ERROR_30"] == 1

def test_safe_metadata_diagnostics_classify_client_errors_without_messages() -> None:
    from core.official_engine_factory import _safe_metadata_failure_code

    assert _safe_metadata_failure_code(TypeError("sensitive detail")) == "KOSIS_METADATA_CLIENT_TYPE_ERROR"
    assert _safe_metadata_failure_code(ValueError("sensitive detail")) == "KOSIS_METADATA_CLIENT_VALUE_ERROR"
    assert (
        _safe_metadata_failure_code(RuntimeError("KOSIS_METADATA_SNAPSHOT_HASH_MISMATCH"))
        == "KOSIS_METADATA_SNAPSHOT_HASH_MISMATCH"
    )
