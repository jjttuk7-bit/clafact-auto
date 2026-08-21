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
        "all_claims_terminal": all(status in {"AUTO", "HOLD"} for status, _ in terminal),
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
