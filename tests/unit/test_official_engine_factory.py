from pathlib import Path

from core.official_engine_factory import OfficialEnginePaths, build_official_evidence_service
from schemas.claim import ClaimSchema


def test_factory_builds_core_service_with_injected_catalog_dependencies(tmp_path: Path) -> None:
    paths = OfficialEnginePaths(
        standard_path=tmp_path / "concepts.json",
        catalog_path=tmp_path / "catalog.json",
        as_of_metadata_paths=[],
    )
    paths.standard_path.write_text("[]", encoding="utf-8")
    paths.catalog_path.write_text("[]", encoding="utf-8")

    service = build_official_evidence_service(paths, kosis_api_key=None)

    assert service is not None

def test_factory_accepts_a_live_time_budget(tmp_path: Path) -> None:
    paths = OfficialEnginePaths(tmp_path / "concepts.json", tmp_path / "catalog.json", [])
    paths.standard_path.write_text("[]", encoding="utf-8")
    paths.catalog_path.write_text("[]", encoding="utf-8")

    assert build_official_evidence_service(paths, kosis_api_key=None, live_time_budget_seconds=5) is not None
def test_factory_uses_local_candidate_when_all_live_catalog_queries_fail(tmp_path: Path, monkeypatch) -> None:
    import core.official_engine_factory as factory
    from schemas.candidate import KosisCandidateSchema
    from schemas.concept import StandardConceptSchema

    paths = OfficialEnginePaths(tmp_path / "concepts.json", tmp_path / "catalog.json", [])
    paths.standard_path.write_text("[]", encoding="utf-8")
    paths.catalog_path.write_text("[]", encoding="utf-8")
    local = KosisCandidateSchema(
        org_id="101", tbl_id="DT_LOCAL", tbl_name="취업자", metadata_status="STRUCTURAL_READY"
    )

    class FailedLiveSearch:
        attempted_queries = 2
        failed_queries = 2
        empty_queries = 0

        def __init__(self, *_args, **_kwargs):
            pass

    monkeypatch.setattr(factory, "KosisLiveCatalogSearch", FailedLiveSearch)
    monkeypatch.setattr(factory, "search_semantic_catalog", lambda *_args: [local])
    monkeypatch.setattr(factory, "discover_catalog_candidates", lambda *_args, **_kwargs: [local])
    monkeypatch.setattr(factory, "refresh_item_metadata_for_claim", lambda candidates, *_args, **_kwargs: list(candidates))

    service = build_official_evidence_service(paths, kosis_api_key="key")
    concept = StandardConceptSchema(
        concept_id="employment", canonical_name="취업자", standard_key="employment",
        status="MATCHED",
    )
    claim = ClaimSchema(claim_id="c", source_sentence="", indicator="취업자 수", parse_status="AUTO_OK")

    resolution = service._catalog_resolver(claim, concept)

    assert resolution.candidates == [local]
    assert resolution.diagnostics["empty_queries"] == 0

def test_factory_adds_official_metadata_candidate_for_concept_code(tmp_path: Path, monkeypatch) -> None:
    import hashlib
    import json
    import core.official_engine_factory as factory
    from schemas.concept import StandardConceptSchema

    snapshot = tmp_path / "cpi.json"
    snapshot.write_text(json.dumps({"dataset_version": "cpi-v1", "metadata": {
        "101|DT_CPI|ITM": [{"TBL_ID": "DT_CPI", "OBJ_ID": "I", "ITM_ID": "A02A01701", "ITM_NM": "배추"}]
    }}), encoding="utf-8")
    manifest = tmp_path / "cpi.manifest.json"
    manifest.write_text(json.dumps({"metadata_snapshot_version": "cpi-v1", "snapshot_path": "cpi.json", "content_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest()}), encoding="utf-8")
    paths = OfficialEnginePaths(tmp_path / "concepts.json", tmp_path / "catalog.json", [], [manifest])
    paths.standard_path.write_text("[]", encoding="utf-8")
    paths.catalog_path.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(factory, "discover_catalog_candidates", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(factory, "refresh_item_metadata_for_claim", lambda candidates, *_args, **_kwargs: list(candidates))

    service = build_official_evidence_service(paths, kosis_api_key=None)
    concept = StandardConceptSchema(concept_id="CPI_DETAIL:A02A01701", canonical_name="배추 소비자물가지수", standard_key="cpi_detail:A02A01701", status="MATCHED")
    claim = ClaimSchema(claim_id="c", source_sentence="", indicator="물가", dimension={"product": "배추"}, parse_status="AUTO_OK")

    resolution = service._catalog_resolver(claim, concept)
    candidates = resolution.candidates

    assert [(item.org_id, item.tbl_id, item.tbl_name) for item in candidates] == [("101", "DT_CPI", "배추 소비자물가지수")]

def test_factory_prioritizes_official_metadata_candidate_before_lexical_candidates(tmp_path: Path, monkeypatch) -> None:
    import hashlib
    import json
    import core.official_engine_factory as factory
    from schemas.candidate import KosisCandidateSchema
    from schemas.concept import StandardConceptSchema

    snapshot = tmp_path / "cpi.json"
    snapshot.write_text(json.dumps({"dataset_version": "cpi-v1", "metadata": {"101|DT_CPI|ITM": [{"TBL_ID": "DT_CPI", "OBJ_ID": "I", "ITM_ID": "A02A01701"}]}},), encoding="utf-8")
    manifest = tmp_path / "cpi.manifest.json"
    manifest.write_text(json.dumps({"metadata_snapshot_version": "cpi-v1", "snapshot_path": "cpi.json", "content_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest()}), encoding="utf-8")
    paths = OfficialEnginePaths(tmp_path / "concepts.json", tmp_path / "catalog.json", [], [manifest])
    paths.standard_path.write_text("[]", encoding="utf-8")
    paths.catalog_path.write_text("[]", encoding="utf-8")
    lexical = KosisCandidateSchema(org_id="101", tbl_id="DT_OTHER", tbl_name="물가", metadata_status="LIVE_SEARCH_UNRESOLVED")
    monkeypatch.setattr(factory, "discover_catalog_candidates", lambda *_args, **_kwargs: [lexical])
    monkeypatch.setattr(factory, "refresh_item_metadata_for_claim", lambda candidates, *_args, **_kwargs: list(candidates))

    service = build_official_evidence_service(paths, kosis_api_key=None)
    resolution = service._catalog_resolver(ClaimSchema(claim_id="c", source_sentence="", indicator="물가", parse_status="AUTO_OK"), StandardConceptSchema(concept_id="CPI_DETAIL:A02A01701", canonical_name="배추 소비자물가지수", standard_key="cpi_detail:A02A01701", status="MATCHED"))
    candidates = resolution.candidates

    assert [item.tbl_id for item in candidates] == ["DT_CPI", "DT_OTHER"]

def test_factory_marks_existing_live_candidate_as_official_concept_metadata_seed(tmp_path: Path, monkeypatch) -> None:
    import hashlib
    import json
    import core.official_engine_factory as factory
    from schemas.candidate import KosisCandidateSchema
    from schemas.concept import StandardConceptSchema

    snapshot = tmp_path / "cpi.json"
    snapshot.write_text(json.dumps({"dataset_version": "cpi-v1", "metadata": {"101|DT_CPI|ITM": [{"TBL_ID": "DT_CPI", "OBJ_ID": "I", "ITM_ID": "A02A01701"}]}},), encoding="utf-8")
    manifest = tmp_path / "cpi.manifest.json"
    manifest.write_text(json.dumps({"metadata_snapshot_version": "cpi-v1", "snapshot_path": "cpi.json", "content_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest()}), encoding="utf-8")
    paths = OfficialEnginePaths(tmp_path / "concepts.json", tmp_path / "catalog.json", [], [manifest])
    paths.standard_path.write_text("[]", encoding="utf-8")
    paths.catalog_path.write_text("[]", encoding="utf-8")
    live = KosisCandidateSchema(org_id="101", tbl_id="DT_CPI", tbl_name="소비자물가지수", source_stat_id="1964001", metadata_status="LIVE_SEARCH_UNRESOLVED")
    monkeypatch.setattr(factory, "discover_catalog_candidates", lambda *_args, **_kwargs: [live])
    monkeypatch.setattr(factory, "refresh_item_metadata_for_claim", lambda candidates, *_args, **_kwargs: list(candidates))

    resolution = build_official_evidence_service(paths, kosis_api_key=None)._catalog_resolver(ClaimSchema(claim_id="c", source_sentence="", indicator="물가", parse_status="AUTO_OK"), StandardConceptSchema(concept_id="CPI_DETAIL:A02A01701", canonical_name="배추 소비자물가지수", standard_key="cpi_detail:A02A01701", status="MATCHED"))
    candidates = resolution.candidates

    assert candidates[0].source_stat_id == "OFFICIAL_CONCEPT_METADATA_SEED"
def test_factory_bounds_official_value_request_budget(tmp_path: Path, monkeypatch) -> None:
    import core.official_engine_factory as factory

    paths = OfficialEnginePaths(tmp_path / "concepts.json", tmp_path / "catalog.json", [])
    paths.standard_path.write_text("[]", encoding="utf-8")
    paths.catalog_path.write_text("[]", encoding="utf-8")
    captured = {}
    monkeypatch.setattr(factory, "build_kosis_api_lookup", lambda _key, **kwargs: captured.update(kwargs) or object())

    build_official_evidence_service(paths, kosis_api_key="key", live_time_budget_seconds=8)

    assert captured == {"retries": 1, "timeout_seconds": 4.0}


def test_factory_routes_cultivated_area_and_rejects_unknown_official_author_keys(tmp_path: Path) -> None:
    paths = OfficialEnginePaths(tmp_path / "concepts.json", tmp_path / "catalog.json", [])
    paths.standard_path.write_text("[]", encoding="utf-8")
    paths.catalog_path.write_text("[]", encoding="utf-8")

    fallback = build_official_evidence_service(paths, kosis_api_key=None)._official_author_fallback

    assert fallback is not None
    assert "cultivated_area" in fallback._route_contexts
    assert "unknown_key" not in fallback._route_contexts