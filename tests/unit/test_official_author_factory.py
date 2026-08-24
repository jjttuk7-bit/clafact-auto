from pathlib import Path

from core.official_author_fallback_service import OfficialAuthorFallbackService
from core.official_engine_factory import OfficialEnginePaths
from core import official_engine_factory_v3 as factory
from schemas.official_author import OfficialAuthorProfile


class _Base:
    _catalog_resolver = staticmethod(lambda *_args: [])
    _official_fetcher = object()

    def resolve(self, *_args, **_kwargs):
        raise AssertionError("not used")


def test_v3_factory_wraps_canonical_service_when_author_profiles_are_enabled(
    monkeypatch, tmp_path: Path
) -> None:
    profile = OfficialAuthorProfile(
        profile_id="food", author_name="농림축산식품부",
        indicator_terms=["라면"], trusted_hosts=["mafra.go.kr"], documents=[],
    )
    monkeypatch.setattr(factory, "build_official_evidence_service", lambda *_args, **_kwargs: _Base())
    monkeypatch.setattr(factory, "load_semantic_standard_v2", lambda *_args: [])
    monkeypatch.setattr(factory, "load_official_author_profiles", lambda _path: [profile])

    service = factory.build_official_evidence_service_v3(
        OfficialEnginePaths(tmp_path / "standard.json", tmp_path / "catalog.json", []),
        semantic_overlay_path=tmp_path / "semantic.json",
        catalog_overlay_path=tmp_path / "catalog-overlay.json",
        official_author_profiles_path=tmp_path / "authors.json",
        kosis_api_key="key",
    )

    assert isinstance(service, OfficialAuthorFallbackService)
