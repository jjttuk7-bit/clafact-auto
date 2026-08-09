"""Refresh candidate item metadata from KOSIS before Hard Guard and matching."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping

from core.kosis_catalog_adapter import hydrate_candidates_from_official_metadata
from core.kosis_openapi_transport import get_meta
from schemas.candidate import KosisCandidateSchema

MetadataFetcher = Callable[[str, str, str], Iterable[Mapping[str, object]]]


def refresh_item_metadata(
    candidates: Iterable[KosisCandidateSchema],
    api_key: str | None,
    *,
    metadata_fetcher: Callable[..., Iterable[Mapping[str, object]]] = get_meta,
) -> list[KosisCandidateSchema]:
    """Use verified ITM metadata when configured; preserve candidates otherwise."""
    materialized = list(candidates)
    if not api_key:
        return materialized
    return hydrate_candidates_from_official_metadata(
        materialized,
        lambda org_id, table_id: metadata_fetcher(
            api_key,
            org_id,
            table_id,
            meta_type="ITM",
        ),
    )