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
    allow_without_api_key: bool = False,
    max_candidates: int | None = 8,
    retries: int = 2,
    timeout_seconds: int = 20,
) -> list[KosisCandidateSchema]:
    """Hydrate at most the ranked candidate budget; preserve the remaining identities."""
    materialized = list(candidates)
    refresh_count = len(materialized) if max_candidates is None else max(0, max_candidates)
    refreshable = materialized[:refresh_count]
    preserved = materialized[refresh_count:]
    if not api_key and not allow_without_api_key:
        return materialized
    fetcher_key = api_key or ""
    hydrated = hydrate_candidates_from_official_metadata(
        refreshable,
        lambda org_id, table_id: metadata_fetcher(
            fetcher_key,
            org_id,
            table_id,
            meta_type="ITM",
            retries=retries,
            timeout_seconds=timeout_seconds,
        ),
    )
    refreshed: list[KosisCandidateSchema] = []
    for candidate in hydrated:
        if candidate.metadata_status not in {
            "OFFICIAL_ITEM_METADATA_READY",
            "OFFICIAL_METADATA_READY",
        }:
            refreshed.append(candidate)
            continue
        try:
            period_rows = list(metadata_fetcher(
                fetcher_key, candidate.org_id, candidate.tbl_id,
                meta_type="PRD", retries=retries, timeout_seconds=timeout_seconds,
            ))
            refreshed.append(_with_period_metadata(candidate, period_rows))
        except (RuntimeError, TypeError, ValueError):
            refreshed.append(candidate)
    return [*refreshed, *preserved]


def _with_period_metadata(
    candidate: KosisCandidateSchema, rows: Iterable[Mapping[str, object]]
) -> KosisCandidateSchema:
    materialized_rows = list(rows)
    frequencies = list(dict.fromkeys(
        frequency
        for row in materialized_rows
        if (frequency := _period_frequency(row)) is not None
    ))
    starts = [str(row.get("STRT_PRD_DE", "")).strip() for row in materialized_rows if str(row.get("STRT_PRD_DE", "")).strip()]
    ends = [str(row.get("END_PRD_DE", "")).strip() for row in materialized_rows if str(row.get("END_PRD_DE", "")).strip()]
    return candidate.model_copy(update={
        "frequency": "|".join(frequencies) or candidate.frequency,
        "start_period": min(starts) if starts else candidate.start_period,
        "end_period": max(ends) if ends else candidate.end_period,
        "metadata_status": (
            "OFFICIAL_METADATA_READY"
            if frequencies and candidate.metadata_status == "OFFICIAL_ITEM_METADATA_READY"
            else candidate.metadata_status
        ),
    })


def _period_frequency(row: Mapping[str, object]) -> str | None:
    label = str(row.get("PRD_SE", "")).strip()
    if label in {"월", "분기", "년"}:
        return label
    sample = str(row.get("STRT_PRD_DE") or row.get("END_PRD_DE") or "").strip()
    if "." in sample:
        return "월"
    if "/" in sample:
        return "분기"
    return "년" if sample.isdigit() and len(sample) == 4 else None
