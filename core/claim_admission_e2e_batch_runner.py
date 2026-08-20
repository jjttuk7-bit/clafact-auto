"""Batch bridge from Claim Admission to the shared official evidence engine."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any

from core.claim_admission_pipeline import ClaimAdmissionPipeline
from core.claim_admission_router import route_claim_admission
from core.official_e2e_batch_runner import OfficialEvidenceResolver, run_official_e2e_batch
from schemas.claim import ClaimSchema
from schemas.claim_admission import AdmissionDecision
from schemas.claim_registry import ClaimRegistryRecord


ContextReparser = Callable[[ClaimRegistryRecord, ClaimSchema], ClaimSchema]
ChildParser = Callable[[ClaimRegistryRecord, ClaimSchema, str, str], ClaimSchema]
AdmissionRouter = Callable[[ClaimSchema], AdmissionDecision]
ContextualAdmissionRouter = Callable[[ClaimRegistryRecord, ClaimSchema], AdmissionDecision]


def run_claim_admission_e2e_batch(
    records: Iterable[ClaimRegistryRecord],
    service: OfficialEvidenceResolver,
    *,
    context_reparser: ContextReparser | None = None,
    child_parser: ChildParser | None = None,
    admission_router: AdmissionRouter | None = None,
    contextual_admission_router: ContextualAdmissionRouter | None = None,
) -> list[dict[str, Any]]:
    """Route Registry records before calling the existing official batch runner.

    Admission-only outcomes are recorded as `ADMISSION_ROUTED`; they are deliberately
    not fabricated as official `HOLD` results.  The nested official runner owns all
    `AUTO` and `HOLD` outcomes after an official query attempt.
    """
    rows: list[dict[str, Any]] = []
    for source_record in records:
        pipeline = ClaimAdmissionPipeline(
            official_resolver=lambda claim: _run_official(source_record, claim, service),
            context_reparser=(
                lambda claim: context_reparser(source_record, claim)
                if context_reparser else None
            ),
            admission_router=(
                (lambda claim: contextual_admission_router(source_record, claim))
                if contextual_admission_router else admission_router or route_claim_admission
            ),
            child_parser=(
                lambda parent, text, child_id: child_parser(source_record, parent, text, child_id)
                if child_parser else None
            ),
        )
        for execution in pipeline.process(source_record.claim):
            row = _base_row(source_record, execution.claim)
            row["admission_label"] = execution.result.decision.label
            row["admission_reason_code"] = execution.result.decision.reason_code
            row["admission_events"] = [event.model_dump(mode="json") for event in execution.result.events]
            if execution.official_result is None:
                row.update({
                    "route_status": "ADMISSION_ROUTED",
                    "reason_code": execution.result.decision.reason_code,
                    "verdict": "UNDETERMINED",
                    "official_result": None,
                })
            else:
                official = dict(execution.official_result)
                row.update({
                    "route_status": official["route_status"],
                    "reason_code": official["reason_code"],
                    "verdict": official["verdict"],
                    "official_result": official,
                })
            rows.append(row)
    return rows


def _run_official(
    source_record: ClaimRegistryRecord, claim: ClaimSchema, service: OfficialEvidenceResolver
) -> Mapping[str, Any]:
    derived = source_record.model_copy(update={"claim": claim})
    return run_official_e2e_batch([derived], service)[0]


def _base_row(record: ClaimRegistryRecord, claim: ClaimSchema) -> dict[str, Any]:
    return {
        "article_id": record.article_id,
        "sentence_id": record.sentence_id,
        "source_claim_id": record.claim.claim_id,
        "claim_id": claim.claim_id,
        "source_sentence": claim.source_sentence,
        "article_published_at": record.article_published_at.isoformat()
        if record.article_published_at else None,
    }

