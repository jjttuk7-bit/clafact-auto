"""Reproducible Goldset routing and HOLD-reason reporting."""

from __future__ import annotations

from collections import Counter
from typing import Any


def classify_hold_reason(reason: str | None) -> str:
    """Map curated non-comparability reasons to operational HOLD categories."""
    text = reason or ""
    if "스냅샷" in text or "사후 개정" in text:
        return "ARTICLE_TIME_OFFICIAL_VALUE_UNAVAILABLE"
    if "표·좌표" in text or "표 미확보" in text:
        return "EVIDENCE_CELL_UNRESOLVED"
    if "메타데이터" in text:
        return "INPUT_METADATA_INSUFFICIENT"
    if "API" in text or "파생값" in text or "KOSIS 재현 조건" in text:
        return "KOSIS_API_OR_MEMBER_CODE_UNLINKED"
    return "KOSIS_SCOPE_OR_EVIDENCE_UNAVAILABLE"


def summarize_goldset(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Return one audited route row per Goldset record without inventing evidence."""
    results: list[dict[str, str]] = []
    counts: Counter[str] = Counter()
    for record in records:
        route = "AUTO" if record.get("KOSIS_재현_상태") == "KOSIS 재현 가능" else "HOLD"
        counts[route] += 1
        result = {
            "claim_id": str(record["claim_id"]),
            "route_status": route,
            "verdict": "MATCH" if route == "AUTO" else "UNDETERMINED",
            "hold_category": "" if route == "AUTO" else classify_hold_reason(record.get("판정불가_유형")),
            "gold_table_id": str(record.get("gold_table_id") or ""),
        }
        results.append(result)
    return {
        "summary": {"total": len(records), "AUTO": counts["AUTO"], "HOLD": counts["HOLD"], "HUMAN_REVIEW": 0},
        "results": results,
    }
