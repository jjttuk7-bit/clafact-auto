"""Build immutable admissibility decisions from Registry and already-recorded parse results."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from core.claim_admissibility import classify_admissibility
from schemas.claim_registry import ClaimRegistryRecord


def build_admissibility_records(
    records: Iterable[ClaimRegistryRecord], results_by_claim_id: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Return exactly one classification for each original non-AUTO Claim."""
    output: list[dict[str, Any]] = []
    for record in records:
        if record.claim.parse_status == "AUTO_OK":
            continue
        result = results_by_claim_id.get(record.claim.claim_id, {})
        decision = classify_admissibility(
            result.get("reason_code"), str(result.get("route_status") or "HOLD")
        )
        output.append({
            "claim_id": record.claim.claim_id,
            "article_id": record.article_id,
            "sentence_id": record.sentence_id,
            "source_ref": record.source_ref,
            "admissibility_route": decision.route,
            "admissibility_reason_code": decision.reason_code,
            "reparse_route_status": result.get("route_status", "HOLD"),
            "reparse_reason": result.get("reason_code"),
            "source_sentence": record.claim.source_sentence,
            "slots": record.claim.model_dump(
                include={
                    "indicator", "value", "unit", "time", "frequency", "region", "population",
                    "dimension", "comparison", "calculation", "condition", "source_hint", "parse_status", "parse_reason",
                },
                mode="json",
            ),
        })
    return output
