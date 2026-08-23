"""Adapters that execute only the stages allowed by an issue-group policy."""

from __future__ import annotations

import csv
from collections import defaultdict
import json
from pathlib import Path
from typing import Any, Iterable

from core.admission_recovery_v3 import recover_registry_record_v3
from core.claim_disposition import classify_claim_disposition
from core.claim_parser import StructuredClaimExtractor
from core.issue_group_harness import ClaimIssueRecord
from core.slot_audit import audit_claim_slots
from schemas.claim import ClaimSchema
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
            disposition = classify_claim_disposition(entry.record.claim)
            children.append(
                {
                    "claim_id": entry.record.claim.claim_id,
                    "admission_route": entry.admission_route,
                    "twelve_slot_complete": audit.eligible_for_official_search,
                    "slot_audit": audit.model_dump(mode="json"),
                    "claim": entry.record.claim.model_dump(mode="json"),
                    "recovery_audit": entry.record.slot_enrichment,
                    "disposition": disposition.disposition,
                    "disposition_reason": disposition.reason_code,
                    "next_route": disposition.next_route,
                }
            )
        admitted = bool(children) and all(
            child["admission_route"] == "KOSIS_PIPELINE_ELIGIBLE"
            and child["twelve_slot_complete"]
            for child in children
        )
        return normalize_context_result({
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
        })


class _AdmissionOnlyResolver:
    """Non-network sink used because the CONTEXT policy ends before KOSIS."""

    def resolve(self, claim: object, *, article_date: object) -> None:
        return None


def _legacy_normalize_context_result(result: dict[str, Any]) -> dict[str, Any]:
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


_SLOT_LABELS = (
    ("indicator", "지표"),
    ("value", "수치"),
    ("unit", "단위"),
    ("time", "시점"),
    ("frequency", "주기"),
    ("region", "지역"),
    ("population", "대상"),
    ("dimension", "차원"),
    ("comparison", "비교"),
    ("calculation", "계산"),
    ("condition", "조건"),
    ("source_hint", "작성기관힌트"),
)


def write_context_child_csv(
    results: list[dict[str, Any]],
    path: Path,
) -> None:
    """Write one auditable row per recovered child and all twelve slots."""

    headers = [
        "부모Claim번호",
        "자식Claim번호",
        "재입장경로",
        "12개항목완성",
        "남은문제",
        "재분류결과",
        "재분류사유",
        "다음경로",
    ]
    for _, label in _SLOT_LABELS:
        headers.extend((label, f"{label}상태"))
    rows: list[dict[str, object]] = []
    for result in results:
        parent_id = str(result.get("claim_id") or "")
        for child in result.get("children") or []:
            if not isinstance(child, dict):
                continue
            claim = child.get("claim") if isinstance(child.get("claim"), dict) else {}
            audit = (
                child.get("slot_audit")
                if isinstance(child.get("slot_audit"), dict)
                else {}
            )
            statuses = {
                str(entry.get("slot") or ""): str(entry.get("status") or "")
                for entry in audit.get("entries") or []
                if isinstance(entry, dict)
            }
            row: dict[str, object] = {
                "부모Claim번호": parent_id,
                "자식Claim번호": str(child.get("claim_id") or ""),
                "재입장경로": str(child.get("admission_route") or ""),
                "12개항목완성": "예" if child.get("twelve_slot_complete") else "아니오",
                "남은문제": " | ".join(
                    str(reason) for reason in audit.get("reason_codes") or []
                ),
                "재분류결과": str(child.get("disposition") or ""),
                "재분류사유": str(child.get("disposition_reason") or ""),
                "다음경로": str(child.get("next_route") or ""),
            }
            for slot, label in _SLOT_LABELS:
                row[label] = _csv_value(claim.get(slot))
                row[f"{label}상태"] = statuses.get(slot, "")
            rows.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def _csv_value(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return "" if value is None else value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def normalize_context_result(result: dict[str, Any]) -> dict[str, Any]:
    """Recompute parent status from official, excluded, and unresolved children."""

    normalized = dict(result)
    children = [
        _with_disposition(child)
        for child in normalized.get("children") or []
        if isinstance(child, dict)
    ]
    normalized["children"] = children
    official = [child for child in children if _official_ready(child)]
    excluded = [child for child in children if _safely_excluded(child)]
    unresolved = [
        child for child in children
        if child not in official and child not in excluded
    ]
    reasons = sorted({
        str(child.get("disposition_reason") or "")
        for child in excluded
        if child.get("disposition_reason")
    })
    if children and not unresolved and official:
        mixed = bool(excluded)
        normalized.update(
            status="PASS",
            reason_code=(
                "CHILDREN_READY_WITH_RECLASSIFICATION"
                if mixed else "KOSIS_PIPELINE_ELIGIBLE"
            ),
            reclassification_result=(
                "PARTIAL_RECLASSIFICATION" if mixed else ""
            ),
            reclassification_reason=" | ".join(reasons),
            next_route="OFFICIAL_SEARCH",
        )
    elif children and not unresolved and excluded:
        normalized.update(
            status="RECLASSIFIED",
            reason_code="PRE_VERIFICATION_RECLASSIFIED",
            reclassification_result="ALL_RECLASSIFIED",
            reclassification_reason=" | ".join(reasons),
            next_route="PRE_VERIFICATION_EXCLUDE",
        )
    elif children:
        normalized.update(
            status="HUMAN_REVIEW",
            reason_code=_remaining_reason(children),
            reclassification_result=(
                "PARTIAL_RECLASSIFICATION" if excluded else ""
            ),
            reclassification_reason=" | ".join(reasons),
            next_route="CONTEXT_REVIEW",
        )
    return normalized


def _with_disposition(child: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(child)
    if normalized.get("disposition"):
        return normalized
    claim = normalized.get("claim")
    if isinstance(claim, dict):
        decision = classify_claim_disposition(ClaimSchema.model_validate(claim))
        normalized.update(
            disposition=decision.disposition,
            disposition_reason=decision.reason_code,
            next_route=decision.next_route,
        )
    elif (
        normalized.get("admission_route") == "KOSIS_PIPELINE_ELIGIBLE"
        and bool(normalized.get("twelve_slot_complete"))
    ):
        normalized.update(
            disposition="OFFICIAL_VERIFICATION_TARGET",
            disposition_reason="TWELVE_SLOT_COMPLETE",
            next_route="OFFICIAL_SEARCH",
        )
    else:
        normalized.update(
            disposition="SOURCE_CONTEXT_INSUFFICIENT",
            disposition_reason="SOURCE_CONTEXT_INSUFFICIENT",
            next_route="CONTEXT_REVIEW",
        )
    return normalized


def _official_ready(child: dict[str, Any]) -> bool:
    return (
        child.get("disposition") == "OFFICIAL_VERIFICATION_TARGET"
        and child.get("admission_route") == "KOSIS_PIPELINE_ELIGIBLE"
        and bool(child.get("twelve_slot_complete"))
    )


def _safely_excluded(child: dict[str, Any]) -> bool:
    return (
        child.get("disposition")
        in {"FORECAST_OR_POLICY", "NO_VERIFIABLE_NUMERIC_ASSERTION"}
        and child.get("next_route") == "PRE_VERIFICATION_EXCLUDE"
    )
