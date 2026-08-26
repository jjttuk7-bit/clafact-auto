"""Exact source-span grounding for preclassified numeric targets."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Mapping

from core.source_numeric_inventory import inventory_numeric_mentions
from core.source_numeric_role_classifier import classify_numeric_roles
from schemas.claim_registry import ClaimRegistryRecord


_UNSELECTED_REASON = {
    "TARGET_BLOCKED_BY_CONTEXT_ROLE": "TARGET_CONTEXT_ROLE_CONFLICT",
    "NO_TARGET_MATCH": "TARGET_NOT_FOUND_IN_SOURCE",
    "AMBIGUOUS_TARGET_MATCH": "TARGET_AMBIGUOUS_IN_SOURCE",
}
_PREVERIFICATION_REASONS = frozenset(_UNSELECTED_REASON.values())


@dataclass(frozen=True, slots=True)
class SourceTargetGrounding:
    claim_id: str
    status: str
    reason_code: str
    expression: str
    mention_id: str
    role: str
    start: int | None
    end: int | None
    slot_enrichment_patch: dict[str, object]


def build_target_grounding(row: Mapping[str, str]) -> SourceTargetGrounding:
    """Revalidate one role-classified row and build its Registry patch."""

    claim_id = str(row.get("Claim번호") or "").strip()
    source = str(row.get("원문") or "")
    source_status = str(row.get("대상연결상태") or "").strip()
    if not claim_id or not source:
        raise ValueError("TARGET_LINK_REQUIRED_SOURCE_MISSING")
    if source_status != "TARGET_SELECTED":
        reason = _UNSELECTED_REASON.get(source_status)
        if reason is None:
            raise ValueError(f"TARGET_LINK_UNKNOWN_STATUS:{source_status}")
        patch: dict[str, object] = {
            "target_link_status": reason,
            "target_link_reason_code": reason,
            "target_link_version": "1.0",
        }
        return SourceTargetGrounding(
            claim_id, reason, reason, "", "", "", None, None, patch
        )

    expression = str(row.get("자동대상표현") or "").strip()
    role = str(row.get("자동대상역할") or "").strip()
    mentions = json.loads(str(row.get("원문수치목록JSON") or "[]"))
    assignments = json.loads(str(row.get("숫자역할목록JSON") or "[]"))
    eligible = [item for item in assignments if item.get("auto_target_eligible") is True]
    if len(eligible) != 1 or not expression:
        raise ValueError(f"TARGET_LINK_SELECTED_COUNT_INVALID:{claim_id}")
    assignment = eligible[0]
    if assignment.get("expression") != expression or assignment.get("role") != role:
        raise ValueError(f"TARGET_LINK_ASSIGNMENT_MISMATCH:{claim_id}")
    mention_id = str(assignment.get("mention_id") or "")
    matches = [item for item in mentions if str(item.get("mention_id") or "") == mention_id]
    if len(matches) != 1:
        raise ValueError(f"TARGET_LINK_MENTION_NOT_UNIQUE:{claim_id}")
    mention = matches[0]
    start = int(mention["start"])
    end = int(mention["end"])
    if mention.get("expression") != expression or source[start:end] != expression:
        raise ValueError(f"TARGET_LINK_SOURCE_SPAN_MISMATCH:{claim_id}")
    patch = {
        "target_link_status": "SOURCE_GROUNDED",
        "target_link_reason_code": "SOURCE_TARGET_EXACT_MATCH",
        "target_link_version": "1.0",
        "target_numeric_expression": expression,
        "target_numeric_mention_id": mention_id,
        "target_numeric_role": role,
        "target_numeric_start": start,
        "target_numeric_end": end,
    }
    return SourceTargetGrounding(
        claim_id,
        "SOURCE_GROUNDED",
        "SOURCE_TARGET_EXACT_MATCH",
        expression,
        mention_id,
        role,
        start,
        end,
        patch,
    )


def merge_target_grounding(
    record: ClaimRegistryRecord,
    grounding: SourceTargetGrounding,
) -> ClaimRegistryRecord:
    """Merge a verified grounding patch without discarding prior audit data."""

    if record.claim.claim_id != grounding.claim_id:
        raise ValueError("TARGET_LINK_CLAIM_ID_MISMATCH")
    enrichment = dict(record.slot_enrichment or {})
    enrichment.update(grounding.slot_enrichment_patch)
    return record.model_copy(update={"slot_enrichment": enrichment})


def merge_target_grounding_patch(
    record: ClaimRegistryRecord,
    patch_row: Mapping[str, object],
) -> ClaimRegistryRecord:
    """Apply one persisted patch only to its exact Claim and source sentence."""

    if str(patch_row.get("claim_id") or "") != record.claim.claim_id:
        raise ValueError("TARGET_LINK_PATCH_CLAIM_ID_MISMATCH")
    expected_hash = hashlib.sha256(
        record.claim.source_sentence.encode("utf-8")
    ).hexdigest().upper()
    if str(patch_row.get("source_sentence_sha256") or "").upper() != expected_hash:
        raise ValueError("TARGET_LINK_PATCH_SOURCE_HASH_MISMATCH")
    raw_patch = patch_row.get("slot_enrichment_patch")
    if not isinstance(raw_patch, Mapping):
        raise ValueError("TARGET_LINK_PATCH_PAYLOAD_MISSING")
    enrichment = dict(record.slot_enrichment or {})
    enrichment.update({str(key): value for key, value in raw_patch.items()})
    merged = record.model_copy(update={"slot_enrichment": enrichment})
    if (
        enrichment.get("target_link_status") == "SOURCE_GROUNDED"
        and trusted_target_expression(merged) is None
    ):
        raise ValueError("TARGET_LINK_PATCH_SPAN_INVALID")
    return merged


def trusted_target_expression(record: ClaimRegistryRecord) -> str | None:
    """Return only a span-verified target from the new grounding contract."""

    enrichment = record.slot_enrichment or {}
    if enrichment.get("target_link_status") != "SOURCE_GROUNDED":
        return None
    expression = str(enrichment.get("target_numeric_expression") or "")
    try:
        start = int(enrichment["target_numeric_start"])
        end = int(enrichment["target_numeric_end"])
    except (KeyError, TypeError, ValueError):
        return None
    if not expression or record.claim.source_sentence[start:end] != expression:
        return None
    return expression


def target_link_preverification_reason(record: ClaimRegistryRecord) -> str | None:
    """Return a non-KOSIS reason for an explicitly ungrounded enriched record."""

    enrichment = record.slot_enrichment or {}
    status = str(enrichment.get("target_link_status") or "")
    return status if status in _PREVERIFICATION_REASONS else None


def repair_exact_target_grounding(record: ClaimRegistryRecord) -> ClaimRegistryRecord:
    """Repair a stale no-match only when one source number exactly matches the Claim."""

    enrichment = dict(record.slot_enrichment or {})
    if enrichment.get("target_link_status") != "TARGET_NOT_FOUND_IN_SOURCE":
        return record
    claim = record.claim
    mentions = inventory_numeric_mentions(claim.source_sentence)
    classified = classify_numeric_roles(
        source_sentence=claim.source_sentence,
        mentions=mentions,
        claim_value=claim.value,
        claim_unit=claim.unit or "",
        indicator=claim.indicator,
    )
    selected = [
        assignment
        for assignment in classified.assignments
        if assignment.auto_target_eligible and assignment.role == "대상값"
    ]
    if classified.target_status != "TARGET_SELECTED" or len(selected) != 1:
        return record
    assignment = selected[0]
    matching = [mention for mention in mentions if mention.mention_id == assignment.mention_id]
    if len(matching) != 1:
        return record
    mention = matching[0]
    enrichment.update({
        "target_link_status": "SOURCE_GROUNDED",
        "target_link_reason_code": "SOURCE_TARGET_EXACT_MATCH_REPAIRED",
        "target_link_version": "1.1",
        "target_numeric_expression": mention.expression,
        "target_numeric_mention_id": mention.mention_id,
        "target_numeric_role": assignment.role,
        "target_numeric_start": mention.start,
        "target_numeric_end": mention.end,
    })
    return record.model_copy(update={"slot_enrichment": enrichment})
