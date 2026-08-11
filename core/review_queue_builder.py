"""Derive typed, action-oriented review queues from E2E result rows."""

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

from schemas.claim_registry import ClaimRegistryRecord
from schemas.review_queue import ReviewQueueRecord


_QUEUE_RULES: tuple[tuple[str, str, str, str], ...] = (
    ("PARSE_", "parse", "CLAIM_ANALYST", "Resolve the 12-slot parsing ambiguity from the source sentence."),
    ("CONCEPT_", "concept", "SEMANTIC_STANDARD_CURATOR", "Add an evidence-backed semantic standard mapping."),
    ("NO_HARD_GUARD_", "catalog", "KOSIS_CATALOG_CURATOR", "Confirm a compatible official KOSIS table and its metadata."),
    ("NO_EVIDENCE_", "evidence", "EVIDENCE_RESOLVER", "Resolve an official KOSIS item and dimension coordinate."),
    ("EVIDENCE_", "evidence", "EVIDENCE_RESOLVER", "Resolve the official KOSIS evidence cell and dimensions."),
    ("PUBLICATION_", "publication_policy", "KOSIS_PUBLICATION_POLICY_REVIEWER", "Confirm publication timing and source snapshot policy."),
)
_RETRYABLE_KOSIS_CODES = {"429", "500", "502", "503", "504", "TIMEOUT", "NETWORK"}


def build_review_queues(
    results: Iterable[Mapping[str, Any]], records_by_claim_id: Mapping[str, ClaimRegistryRecord]
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Group actionable result rows by reason without altering source results."""
    queues: dict[str, list[dict[str, Any]]] = defaultdict(list)
    route_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()

    for result in results:
        route_status = str(result.get("route_status", ""))
        if route_status not in {"HOLD", "HUMAN_REVIEW"}:
            continue
        claim_id = str(result.get("claim_id", ""))
        record = records_by_claim_id.get(claim_id)
        if record is None:
            continue
        reason_code = str(result.get("reason_code") or "REVIEW_REASON_UNSPECIFIED")
        queue_type, owner_role, next_action = _review_action(reason_code)
        queue_record = ReviewQueueRecord(
            queue_type=queue_type,
            owner_role=owner_role,
            next_action=next_action,
            route_status=route_status,
            reason_code=reason_code,
            claim_id=claim_id,
            article_id=record.article_id,
            sentence_id=record.sentence_id,
            source_ref=record.source_ref,
            source_sentence=record.claim.source_sentence,
            slots=_slots(record),
            candidate_metadata=dict(result.get("candidate_metadata") or {}),
        )
        queues[queue_type].append(queue_record.model_dump(mode="json"))
        route_counts[route_status] += 1
        reason_counts[reason_code] += 1

    ordered_queues = {name: queues[name] for name in sorted(queues)}
    return ordered_queues, {
        "total_actionable": sum(route_counts.values()),
        "route_counts": dict(sorted(route_counts.items())),
        "reason_counts": dict(sorted(reason_counts.items())),
        "queue_counts": {name: len(rows) for name, rows in ordered_queues.items()},
    }


def _review_action(reason_code: str) -> tuple[str, str, str]:
    for prefix, queue_type, owner_role, next_action in _QUEUE_RULES:
        if reason_code.startswith(prefix):
            return queue_type, owner_role, next_action
    if reason_code.startswith("KOSIS_VALUE_TRANSPORT_") or _is_retryable_api_error(reason_code):
        return "retry", "KOSIS_TRANSPORT_OPERATOR", "Retry the official KOSIS request with the recorded coordinate."
    return "verification", "VERIFICATION_REVIEWER", "Review the verification trace and determine the next safe action."


def _is_retryable_api_error(reason_code: str) -> bool:
    return reason_code.startswith("KOSIS_VALUE_API_ERROR_") and reason_code.rsplit("_", 1)[-1] in _RETRYABLE_KOSIS_CODES


def _slots(record: ClaimRegistryRecord) -> dict[str, Any]:
    return record.claim.model_dump(
        include={
            "indicator", "value", "unit", "time", "frequency", "region", "population", "dimension", "comparison", "calculation", "condition", "source_hint", "parse_status", "parse_reason"
        },
        mode="json",
    )
