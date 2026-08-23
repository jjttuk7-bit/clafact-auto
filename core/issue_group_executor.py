"""Adapters that execute only the stages allowed by an issue-group policy."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from core.admission_recovery_v3 import recover_registry_record_v3
from core.claim_parser import StructuredClaimExtractor
from core.issue_group_harness import ClaimIssueRecord
from core.slot_audit import audit_claim_slots
from schemas.claim_registry import ClaimRegistryRecord


_CONTEXT_STAGES = ("CLAIM_SPLIT", "CLAIM_PARSE")


def build_article_contexts(
    records: Iterable[ClaimRegistryRecord],
) -> dict[str, str]:
    """Reconstruct available article context from ordered Registry sentences."""

    grouped: dict[str, list[ClaimRegistryRecord]] = defaultdict(list)
    for record in records:
        grouped[record.article_id].append(record)
    contexts: dict[str, str] = {}
    for article_id, article_records in grouped.items():
        seen: set[str] = set()
        sentences: list[str] = []
        for record in sorted(article_records, key=_sentence_order):
            sentence = record.claim.source_sentence.strip()
            if sentence and sentence not in seen:
                seen.add(sentence)
                sentences.append(sentence)
        if sentences:
            contexts[article_id] = "\n".join(sentences)
    return contexts


class ContextGroupExecutor:
    """Run Claim split, 12-slot parsing, and re-admission without KOSIS."""

    def __init__(
        self,
        records: Iterable[ClaimRegistryRecord],
        *,
        extractor: StructuredClaimExtractor,
    ) -> None:
        source_records = list(records)
        self._records = {record.claim.claim_id: record for record in source_records}
        self._contexts = build_article_contexts(source_records)
        self._extractor = extractor

    def __call__(
        self,
        issue: ClaimIssueRecord,
        allowed_stages: tuple[str, ...],
    ) -> dict[str, Any]:
        if allowed_stages != _CONTEXT_STAGES:
            raise ValueError("CONTEXT_EXECUTOR_STAGE_POLICY_MISMATCH")
        record = self._records.get(issue.claim_id)
        if record is None:
            raise ValueError(f"SOURCE_REGISTRY_CLAIM_NOT_FOUND:{issue.claim_id}")
        recovery = recover_registry_record_v3(
            record,
            extractor=self._extractor,
            official_service=_AdmissionOnlyResolver(),
            article_context=self._contexts.get(record.article_id),
        )
        children = []
        for entry in recovery.entries:
            audit = audit_claim_slots(entry.record.claim)
            children.append(
                {
                    "claim_id": entry.record.claim.claim_id,
                    "admission_route": entry.admission_route,
                    "twelve_slot_complete": audit.eligible_for_official_search,
                    "slot_audit": audit.model_dump(mode="json"),
                    "claim": entry.record.claim.model_dump(mode="json"),
                    "recovery_audit": entry.record.slot_enrichment,
                }
            )
        admitted = bool(children) and all(
            child["admission_route"] == "KOSIS_PIPELINE_ELIGIBLE"
            and child["twelve_slot_complete"]
            for child in children
        )
        return {
            "claim_id": issue.claim_id,
            "status": "PASS" if admitted else "HUMAN_REVIEW",
            "reason_code": (
                "KOSIS_PIPELINE_ELIGIBLE"
                if admitted
                else _remaining_reason(children)
            ),
            "stop_stage": "CLAIM_PARSE",
            "executed_stages": list(_CONTEXT_STAGES),
            "official_lookup_attempted": False,
            "official_evidence": False,
            "recovery_action": recovery.recovery_action,
            "child_count": len(children),
            "children": children,
        }


class _AdmissionOnlyResolver:
    """Non-network sink used because the CONTEXT policy ends before KOSIS."""

    def resolve(self, claim: object, *, article_date: object) -> None:
        return None


def normalize_context_result(result: dict[str, Any]) -> dict[str, Any]:
    """Recompute parent admission status from saved child results only."""

    normalized = dict(result)
    children = [
        child
        for child in normalized.get("children") or []
        if isinstance(child, dict)
    ]
    admitted = bool(children) and all(
        child.get("admission_route") == "KOSIS_PIPELINE_ELIGIBLE"
        and bool(child.get("twelve_slot_complete"))
        for child in children
    )
    if admitted:
        normalized.update(status="PASS", reason_code="KOSIS_PIPELINE_ELIGIBLE")
    elif children:
        normalized.update(status="HUMAN_REVIEW", reason_code=_remaining_reason(children))
    return normalized


def _remaining_reason(children: list[dict[str, Any]]) -> str:
    routes = {
        str(child.get("admission_route") or "")
        for child in children
        if child.get("admission_route")
    }
    if len(routes) > 1:
        return "PARTIAL_CHILD_ADMISSION"
    return next(iter(routes), "NO_RECOVERED_CHILD")


def _sentence_order(record: ClaimRegistryRecord) -> tuple[int, str]:
    sentence_id = record.sentence_id.strip()
    try:
        return int(sentence_id), sentence_id
    except ValueError:
        return 1_000_000, sentence_id
