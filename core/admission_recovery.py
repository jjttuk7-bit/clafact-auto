"""Recover admissible registry Claims through the shared official-evidence engine."""

from __future__ import annotations

from core.context_prompt import build_context_prompt as _context_prompt
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal, Protocol

from core.claim_admissibility import classify_admissibility
from core.claim_parser import StructuredClaimExtractor, parse_claim
from core.claim_splitter import split_complex_claim
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


AdmissionRoute = Literal[
    "KOSIS_PIPELINE_ELIGIBLE",
    "MULTI_CLAIM_SPLIT_REQUIRED",
    "CONTEXT_REQUIRED",
    "STRUCTURAL_HOLD",
]
RecoveryAction = Literal["DIRECT", "MULTI_CLAIM_SPLIT", "CONTEXT_REPARSE", "NO_RECOVERY"]


class OfficialEvidenceResolver(Protocol):
    def resolve(self, claim: ClaimSchema, *, article_date: date) -> Any: ...


@dataclass(frozen=True, slots=True)
class RecoveryEntry:
    parent_claim_id: str
    record: ClaimRegistryRecord
    admission_route: AdmissionRoute
    official_resolution: Any | None


@dataclass(frozen=True, slots=True)
class RecoveryResult:
    recovery_action: RecoveryAction
    entries: list[RecoveryEntry]


def recover_registry_record(
    record: ClaimRegistryRecord,
    *,
    extractor: StructuredClaimExtractor,
    official_service: OfficialEvidenceResolver,
    article_context: str | None = None,
) -> RecoveryResult:
    """Create derived Claims and re-admit only parser-confirmed children.

    The returned records retain the source identity and parent id in slot-enrichment
    audit metadata.  Every eligible child calls the same official service as an
    incoming Claim; no result is synthesized by this recovery layer.
    """
    action, sources = _recovery_sources(record.claim, article_context)
    if not sources:
        return RecoveryResult(action, [_entry_for_unrecovered(record)])
    if action == "DIRECT":
        return RecoveryResult(action, [
            _recover_claim(record, record.claim, action=action, official_service=official_service)
        ])

    entries = [
        _recover_source(
            record,
            source,
            action=action,
            extractor=extractor,
            official_service=official_service,
        )
        for source in sources
    ]
    return RecoveryResult(action, entries)


def _recovery_sources(claim: ClaimSchema, article_context: str | None) -> tuple[RecoveryAction, list[str]]:
    clauses = split_complex_claim(claim.source_sentence)
    if len(clauses) > 1:
        return "MULTI_CLAIM_SPLIT", clauses
    decision = classify_admissibility(claim.parse_reason, "AUTO" if claim.parse_status == "AUTO_OK" else "HOLD")
    if decision.route == "CONTEXT_REQUIRED" and article_context and article_context.strip():
        return "CONTEXT_REPARSE", [_context_prompt(claim, article_context)]
    if claim.parse_status == "AUTO_OK":
        return "DIRECT", [claim.source_sentence]
    return "NO_RECOVERY", []


def _recover_source(
    parent: ClaimRegistryRecord,
    source: str,
    *,
    action: RecoveryAction,
    extractor: StructuredClaimExtractor,
    official_service: OfficialEvidenceResolver,
) -> RecoveryEntry:
    parsed = parse_claim(source, extractor, article_published_at=parent.article_published_at)
    if action == "CONTEXT_REPARSE":
        parsed = parsed.model_copy(update={
            "claim_id": parent.claim.claim_id,
            "source_sentence": parent.claim.source_sentence,
        })
    return _recover_claim(parent, parsed, action=action, official_service=official_service)


def _recover_claim(
    parent: ClaimRegistryRecord,
    claim: ClaimSchema,
    *,
    action: RecoveryAction,
    official_service: OfficialEvidenceResolver,
) -> RecoveryEntry:
    route = _admission_route(claim)
    derived = _derived_record(parent, claim, action=action, admission_route=route)
    resolution = (
        official_service.resolve(claim, article_date=parent.article_published_at)
        if route == "KOSIS_PIPELINE_ELIGIBLE" and parent.article_published_at is not None
        else None
    )
    return RecoveryEntry(parent.claim.claim_id, derived, route, resolution)


def _admission_route(claim: ClaimSchema) -> AdmissionRoute:
    decision = classify_admissibility(
        claim.parse_reason,
        "AUTO" if claim.parse_status == "AUTO_OK" else "HOLD",
    )
    if decision.route == "VERIFIABLE":
        return "KOSIS_PIPELINE_ELIGIBLE"
    if decision.route == "CONTEXT_REQUIRED":
        return "CONTEXT_REQUIRED"
    return "STRUCTURAL_HOLD"


def _derived_record(
    parent: ClaimRegistryRecord,
    claim: ClaimSchema,
    *,
    action: RecoveryAction,
    admission_route: AdmissionRoute,
) -> ClaimRegistryRecord:
    return parent.model_copy(update={
        "source_ref": "admission_recovery_v1",
        "claim": claim,
        "slot_enrichment": {
            "stage": "ADMISSION_RECOVERY",
            "parent_claim_id": parent.claim.claim_id,
            "recovery_action": action,
            "admission_route": admission_route,
            "source_ref": parent.source_ref,
        },
    })


def _entry_for_unrecovered(record: ClaimRegistryRecord) -> RecoveryEntry:
    return RecoveryEntry(
        parent_claim_id=record.claim.claim_id,
        record=record,
        admission_route=_admission_route(record.claim),
        official_resolution=None,
    )
