from __future__ import annotations

from dataclasses import dataclass

from core.official_author_registry import (
    OfficialAuthorSourceRegistration,
    OfficialAuthorSourceRegistry,
)


@dataclass(frozen=True)
class _ConfiguredAdapter:
    name: str = "configured-adapter"


def _registry() -> tuple[OfficialAuthorSourceRegistry, _ConfiguredAdapter]:
    adapter = _ConfiguredAdapter()
    registry = OfficialAuthorSourceRegistry(
        registrations=(
            OfficialAuthorSourceRegistration(
                source_authority="KOSTAT",
                statistical_domain="AGRICULTURE",
                indicator_search_terms=("벼", "재배면적"),
                adapter=adapter,
            ),
        )
    )
    return registry, adapter


def test_routes_only_when_configured_authority_domain_and_indicator_terms_match() -> None:
    registry, adapter = _registry()

    route = registry.resolve(
        source_authority="KOSTAT",
        statistical_domain="AGRICULTURE",
        indicator_search_terms=("벼", "재배면적", "조사"),
    )

    assert route is not None
    assert route.adapter is adapter
    assert route.source_authority == "KOSTAT"


def test_does_not_route_when_authority_domain_or_indicator_terms_do_not_match() -> None:
    registry, _ = _registry()

    assert registry.resolve(
        source_authority="KOSTAT",
        statistical_domain="AGRICULTURE",
        indicator_search_terms=("고용", "취업자"),
    ) is None
    assert registry.resolve(
        source_authority="KOSTAT",
        statistical_domain="LABOUR",
        indicator_search_terms=("벼", "재배면적"),
    ) is None
    assert registry.resolve(
        source_authority="BOK",
        statistical_domain="AGRICULTURE",
        indicator_search_terms=("벼", "재배면적"),
    ) is None
