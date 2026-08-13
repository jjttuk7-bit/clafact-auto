"""Refresh KOSIS metadata under an overall wall-clock budget."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from time import monotonic

from core.kosis_catalog_adapter import hydrate_candidate, normalize_item_metadata
from core.kosis_openapi_transport import get_meta
from schemas.candidate import KosisCandidateSchema


def refresh_item_metadata(
    candidates: Iterable[KosisCandidateSchema],
    api_key: str | None,
    *,
    metadata_fetcher: Callable[..., Iterable[Mapping[str, object]]] = get_meta,
    allow_without_api_key: bool = False,
    max_candidates: int | None = None,
    retries: int = 2,
    timeout_seconds: int = 20,
    time_budget_seconds: float | None = None,
    clock: Callable[[], float] = monotonic,
) -> list[KosisCandidateSchema]:
    """Reconfirm candidates with KOSIS ITM/PRD metadata until time expires."""
    materialized = list(candidates)
    if not api_key and not allow_without_api_key:
        return materialized
    limit = len(materialized) if max_candidates is None else max(0, max_candidates)
    deadline = (
        clock() + max(0.0, time_budget_seconds)
        if time_budget_seconds is not None else None
    )
    refreshed: list[KosisCandidateSchema] = []
    fetcher_key = api_key or ""
    for index, candidate in enumerate(materialized[:limit]):
        if deadline is not None and clock() >= deadline:
            refreshed.extend(materialized[index:])
            refreshed.extend(materialized[limit:])
            return refreshed
        hydrated = _with_item_metadata(
            candidate, fetcher_key, metadata_fetcher, retries, timeout_seconds
        )
        if hydrated.metadata_status not in {"OFFICIAL_ITEM_METADATA_READY", "OFFICIAL_METADATA_READY"}:
            refreshed.append(hydrated)
            continue
        if deadline is not None and clock() >= deadline:
            refreshed.append(hydrated)
            refreshed.extend(materialized[index + 1:])
            return refreshed
        refreshed.append(_with_period_metadata_from_api(
            hydrated, fetcher_key, metadata_fetcher, retries, timeout_seconds
        ))
    refreshed.extend(materialized[limit:])
    return refreshed


def _with_item_metadata(
    candidate: KosisCandidateSchema, api_key: str,
    metadata_fetcher: Callable[..., Iterable[Mapping[str, object]]],
    retries: int, timeout_seconds: int,
) -> KosisCandidateSchema:
    try:
        rows = metadata_fetcher(api_key, candidate.org_id, candidate.tbl_id,
            meta_type="ITM", retries=retries, timeout_seconds=timeout_seconds)
        return hydrate_candidate(candidate, normalize_item_metadata(
            rows, table_id=candidate.tbl_id
        ))
    except (RuntimeError, TypeError, ValueError):
        return candidate if candidate.metadata_status == "OFFICIAL_METADATA_READY" else candidate.model_copy(
            update={"metadata_status": "OFFICIAL_ITEM_METADATA_UNAVAILABLE"}
        )


def _with_period_metadata_from_api(
    candidate: KosisCandidateSchema, api_key: str,
    metadata_fetcher: Callable[..., Iterable[Mapping[str, object]]],
    retries: int, timeout_seconds: int,
) -> KosisCandidateSchema:
    try:
        rows = metadata_fetcher(api_key, candidate.org_id, candidate.tbl_id,
            meta_type="PRD", retries=retries, timeout_seconds=timeout_seconds)
        return _with_period_metadata(candidate, rows)
    except (RuntimeError, TypeError, ValueError):
        return candidate.model_copy(update={
            "metadata_status": "OFFICIAL_PERIOD_METADATA_UNAVAILABLE"
        })


def _with_period_metadata(
    candidate: KosisCandidateSchema, rows: Iterable[Mapping[str, object]]
) -> KosisCandidateSchema:
    materialized_rows = list(rows)
    frequencies = list(dict.fromkeys(
        frequency for row in materialized_rows
        if (frequency := _period_frequency(row)) is not None
    ))
    starts = [str(row.get("STRT_PRD_DE", "")).strip() for row in materialized_rows if str(row.get("STRT_PRD_DE", "")).strip()]
    ends = [str(row.get("END_PRD_DE", "")).strip() for row in materialized_rows if str(row.get("END_PRD_DE", "")).strip()]
    if not frequencies:
        return candidate.model_copy(update={
            "metadata_status": "OFFICIAL_PERIOD_METADATA_UNAVAILABLE"
        }) if candidate.metadata_status == "OFFICIAL_ITEM_METADATA_READY" else candidate
    return candidate.model_copy(update={
        "frequency": "|".join(frequencies),
        "start_period": min(starts) if starts else candidate.start_period,
        "end_period": max(ends) if ends else candidate.end_period,
        "metadata_status": "OFFICIAL_METADATA_READY",
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