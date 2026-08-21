from pathlib import Path

from core.official_engine_factory import OfficialEnginePaths, build_official_evidence_service
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema


def test_factory_bounds_each_live_catalog_request_to_fraction_of_claim_budget(
    tmp_path: Path, monkeypatch
) -> None:
    import core.official_engine_factory as factory

    paths = OfficialEnginePaths(tmp_path / "concepts.json", tmp_path / "catalog.json", [])
    paths.standard_path.write_text("[]", encoding="utf-8")
    paths.catalog_path.write_text("[]", encoding="utf-8")
    captured: dict[str, object] = {}

    class _Catalog:
        attempted_queries = 0
        failed_queries = 0
        empty_queries = 0

        def __init__(self, _api_key: str, **kwargs: object) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(factory, "KosisLiveCatalogSearch", _Catalog)
    monkeypatch.setattr(factory, "discover_catalog_candidates", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(factory, "refresh_item_metadata_for_claim", lambda candidates, *_args, **_kwargs: list(candidates))

    service = build_official_evidence_service(paths, kosis_api_key="key", live_time_budget_seconds=8)
    service._catalog_resolver(
        ClaimSchema(claim_id="claim", source_sentence="문장", indicator="고용률", parse_status="AUTO_OK"),
        StandardConceptSchema(concept_id="employment", canonical_name="고용률", standard_key="employment", status="MATCHED"),
    )

    assert captured == {"max_attempts": 1, "timeout_seconds": 2.0}
