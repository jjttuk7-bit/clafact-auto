"""Compact live 94-Claim results without losing audit-critical evidence."""

from __future__ import annotations

from typing import Any, Mapping


def compact_coordinate_result(row: Mapping[str, Any]) -> dict[str, Any]:
    resolution = row.get("official_resolution")
    resolution = resolution if isinstance(resolution, Mapping) else {}
    candidates = resolution.get("candidates") or []
    candidate_refs = [
        {
            "org_id": item.get("org_id"),
            "tbl_id": item.get("tbl_id"),
            "tbl_name": item.get("tbl_name"),
            "source_name": item.get("source_name"),
            "frequency": item.get("frequency"),
            "unit_names": item.get("unit_names") or [],
            "metadata_status": item.get("metadata_status"),
        }
        for item in candidates
        if isinstance(item, Mapping)
    ]
    compact_resolution = None
    if resolution:
        compact_resolution = {
            "candidate_count": len(candidate_refs),
            "candidate_refs": candidate_refs,
            "catalog_diagnostics": resolution.get("catalog_diagnostics") or {},
            "concept": resolution.get("concept"),
            "official_author_evidence": resolution.get("official_author_evidence"),
            "verdict": resolution.get("verdict"),
        }
    return {
        "article_id": row.get("article_id"),
        "sentence_id": row.get("sentence_id"),
        "parent_claim_id": row.get("parent_claim_id"),
        "claim_id": row.get("claim_id"),
        "source_sentence": row.get("source_sentence"),
        "claim": row.get("claim"),
        "recovery_action": row.get("recovery_action"),
        "admission_route": row.get("admission_route"),
        "terminal_status": row.get("terminal_status"),
        "reason_code": row.get("reason_code"),
        "diagnostic_id": row.get("diagnostic_id"),
        "lineage_record": row.get("lineage_record"),
        "slot_audit": row.get("slot_audit"),
        "stage_results": row.get("stage_results") or [],
        "official_resolution": compact_resolution,
    }
