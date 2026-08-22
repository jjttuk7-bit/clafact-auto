"""Deterministic serialization and stage reporting for canonical Registry runs."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import fields, is_dataclass
from typing import Any

from core.unified_claim_pipeline import PipelineEntry
from schemas.claim_registry import ClaimRegistryRecord


def serialize_pipeline_entry(
    record: ClaimRegistryRecord,
    entry: PipelineEntry,
) -> dict[str, Any]:
    return {
        "article_id": record.article_id,
        "sentence_id": record.sentence_id,
        "parent_claim_id": entry.parent_claim_id,
        "claim_id": entry.claim.claim_id,
        "source_sentence": entry.claim.source_sentence,
        "claim": entry.claim.model_dump(mode="json"),
        "recovery_action": entry.recovery_action,
        "admission_route": entry.admission_route,
        "terminal_status": entry.terminal_status,
        "reason_code": entry.reason_code,
        "diagnostic_id": entry.diagnostic_id,
        "official_resolution": _serialize(entry.official_resolution),
    }


def build_run_report(
    rows: list[dict[str, Any]],
    *,
    input_count: int,
    registry_errors: list[Any],
) -> dict[str, Any]:
    parent_ids = {
        str(row.get("parent_claim_id"))
        for row in rows
        if row.get("parent_claim_id")
    }
    coverage_complete = len(parent_ids) == input_count if parent_ids else len(rows) >= input_count > 0
    terminal = [_terminal(row) for row in rows]
    stage_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        for event in _events(row):
            stage = str(event.get("stage") or "UNKNOWN")
            status = str(event.get("status") or "UNKNOWN")
            stage_counts[stage][status] += 1
    return {
        "input_registry_records": input_count,
        "derived_claims": len(rows),
        "recovery_action_counts": _count(rows, "recovery_action"),
        "admission_route_counts": _count(rows, "admission_route"),
        "terminal_route_counts": dict(sorted(Counter(status for status, _ in terminal).items())),
        "terminal_reason_counts": dict(sorted(Counter(reason for _, reason in terminal if reason).items())),
        "official_resolution_count": sum(row.get("official_resolution") is not None for row in rows),
        "operational_failure_count": sum(bool(row.get("diagnostic_id")) for row in rows),
        "stage_status_counts": {
            stage: dict(sorted(counts.items()))
            for stage, counts in sorted(stage_counts.items())
        },
        "official_api_counts": _official_api_counts(rows, stage_counts),
        "input_coverage_complete": coverage_complete,
        "all_claims_terminal": coverage_complete and all(status in {"AUTO", "HOLD"} for status, _ in terminal),
        "registry_load_errors": [_serialize(error) for error in registry_errors],
    }


def _terminal(row: dict[str, Any]) -> tuple[str, str | None]:
    resolution = row.get("official_resolution")
    if isinstance(resolution, dict) and isinstance(resolution.get("verdict"), dict):
        verdict = resolution["verdict"]
        return str(verdict.get("route_status") or "HOLD"), verdict.get("reason_code")
    return str(row.get("terminal_status") or "HOLD"), row.get("reason_code") or row.get("admission_route")


def _events(row: dict[str, Any]) -> list[dict[str, Any]]:
    resolution = row.get("official_resolution")
    verdict = resolution.get("verdict") if isinstance(resolution, dict) else None
    trace = verdict.get("execution_trace") if isinstance(verdict, dict) else None
    events = trace.get("events") if isinstance(trace, dict) else None
    return [event for event in events or [] if isinstance(event, dict)]


def _count(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "UNKNOWN") for row in rows).items()))


def _official_api_counts(rows: list[dict[str, Any]], stage_counts: dict[str, Counter[str]]) -> dict[str, int]:
    diagnostics: Counter[str] = Counter()
    provenance_claims = provenance_cells = verified_publications = 0
    observed = {
        "attempted_queries", "failed_queries", "empty_queries",
        "metadata_itm_attempted", "metadata_itm_succeeded", "metadata_itm_failed",
        "metadata_prd_attempted", "metadata_prd_succeeded", "metadata_prd_failed",
    }
    for row in rows:
        resolution = row.get("official_resolution")
        if not isinstance(resolution, dict):
            continue
        catalog = resolution.get("catalog_diagnostics")
        if isinstance(catalog, dict):
            for key, value in catalog.items():
                if key in observed and isinstance(value, (int, float)):
                    diagnostics[key] += int(value)
        verdict = resolution.get("verdict")
        provenance = verdict.get("official_value_provenance") if isinstance(verdict, dict) else None
        api_cells = [item for item in provenance or [] if isinstance(item, dict) and item.get("source") == "API"]
        if api_cells:
            provenance_claims += 1
            provenance_cells += len(api_cells)
            if all(isinstance(item.get("publication"), dict) and item["publication"].get("status") == "VERIFIED" for item in api_cells):
                verified_publications += 1
    attempted = diagnostics["attempted_queries"]
    failed = diagnostics["failed_queries"]
    empty = diagnostics["empty_queries"]
    fetch = stage_counts.get("OFFICIAL_VALUE_FETCH", Counter())
    result = {
        "catalog_query_attempted": attempted,
        "catalog_query_failed": failed,
        "catalog_query_empty": empty,
        "catalog_query_succeeded_nonempty": max(0, attempted - failed - empty),
        "official_value_fetch_pass": fetch["PASS"],
        "official_value_fetch_hold": fetch["HOLD"],
        "api_provenance_claims": provenance_claims,
        "api_provenance_cells": provenance_cells,
        "verified_publication_claims": verified_publications,
    }
    for phase in ("itm", "prd"):
        for status in ("attempted", "succeeded", "failed"):
            key = f"metadata_{phase}_{status}"
            result[key] = diagnostics[key]
    return result


def _serialize(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if is_dataclass(value):
        return {field.name: _serialize(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(item) for item in value]
    return str(value)
