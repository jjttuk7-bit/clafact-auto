"""KOSIS-first service with a fail-closed official-author document fallback."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date
from typing import Protocol

from core.official_author_profiles import match_official_author_profile
from core.official_evidence_service import OfficialEvidenceResolution
from core.operational_error import OperationalStageError
from core.verdict_engine import make_verdict
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema
from schemas.official_author import OfficialAuthorEvidence, OfficialAuthorProfile
from schemas.pipeline_trace import PipelineTraceSchema
from schemas.verdict import (
    OfficialPublicationProvenanceSchema,
    OfficialValueProvenanceSchema,
)


class _CanonicalService(Protocol):
    def resolve(self, claim: ClaimSchema, *, article_date: date) -> OfficialEvidenceResolution: ...


class _DocumentFetcher(Protocol):
    def fetch(
        self, claim: ClaimSchema, profile: OfficialAuthorProfile, *, article_date: date
    ) -> OfficialAuthorEvidence: ...


class OfficialAuthorFallbackService:
    """Run fallback only after the canonical Catalog operation actually fails."""

    def __init__(
        self,
        *,
        canonical_service: _CanonicalService,
        concept_mapper: Callable[[ClaimSchema], StandardConceptSchema],
        profiles: Sequence[OfficialAuthorProfile],
        document_fetcher: _DocumentFetcher,
    ) -> None:
        self._canonical_service = canonical_service
        self._concept_mapper = concept_mapper
        self._profiles = list(profiles)
        self._document_fetcher = document_fetcher

    def resolve(self, claim: ClaimSchema, *, article_date: date) -> OfficialEvidenceResolution:
        try:
            return self._canonical_service.resolve(claim, article_date=article_date)
        except OperationalStageError as error:
            if error.stage != "KOSIS_CATALOG":
                raise
            concept = self._concept_mapper(claim)
            profile = match_official_author_profile(claim, self._profiles)
            if profile is None:
                raise
        evidence = self._document_fetcher.fetch(claim, profile, article_date=article_date)
        verdict = _verdict_from_official_author(claim, evidence)
        return OfficialEvidenceResolution(
            concept=concept,
            candidates=[],
            verdict=verdict,
            catalog_diagnostics={
                "kosis_catalog_unavailable": 1,
                "official_author_fallback_attempted": 1,
            },
            official_author_evidence=evidence,
        )


def _verdict_from_official_author(claim: ClaimSchema, evidence: OfficialAuthorEvidence):
    trace = (
        PipelineTraceSchema(
            claim_id=claim.claim_id,
            preprocess_version="1.0",
            claim_schema_version="1.0",
        )
        .pass_stage("CLAIM_PARSE")
        .pass_stage("SEMANTIC_MAPPING")
        .hold("CATALOG_SEARCH", "KOSIS_CATALOG_UNAVAILABLE")
        .pass_stage("OFFICIAL_AUTHOR_SEARCH", output_ref=evidence.profile_id or None)
    )
    provenance = _provenance(evidence)
    if evidence.status == "VERIFIED" and evidence.official_value is not None:
        calculated = _calculated_value(claim, evidence.official_value)
        trace = trace.pass_stage("OFFICIAL_AUTHOR_FETCH", output_ref=evidence.content_hash or None)
        trace = trace.pass_stage("CALCULATION").pass_stage("VERDICT")
        verdict = make_verdict(
            claim.claim_id,
            claim.value,
            [evidence.official_value],
            calculated,
            tolerance=_claim_tolerance(claim),
            trace=trace.model_copy(update={"route_status": "AUTO"}),
        )
        return verdict.model_copy(update={"official_value_provenance": provenance})
    reason = evidence.reason_code or "OFFICIAL_AUTHOR_EVIDENCE_UNAVAILABLE"
    trace = trace.hold("OFFICIAL_AUTHOR_FETCH", reason)
    verdict = make_verdict(
        claim.claim_id,
        claim.value,
        [evidence.official_value] if evidence.official_value is not None else [],
        None,
        trace=trace,
    )
    return verdict.model_copy(update={
        "reason_code": reason,
        "explanation": "Official-author evidence could not safely support an automatic verdict.",
        "official_value_provenance": provenance,
    })


def _provenance(evidence: OfficialAuthorEvidence) -> list[OfficialValueProvenanceSchema]:
    if not evidence.source_url or not evidence.content_hash:
        return []
    publication = OfficialPublicationProvenanceSchema(
        status="VERIFIED" if evidence.status == "VERIFIED" else "UNRESOLVED",
        published_at=evidence.published_at,
        source_url=evidence.source_url,
        retrieved_at=evidence.retrieved_at,
        reference_period=evidence.reference_period,
        content_hash=evidence.content_hash,
    )
    return [OfficialValueProvenanceSchema(
        evidence_key=f"OFFICIAL_AUTHOR:{evidence.profile_id}:{evidence.reference_period or ''}",
        source="OFFICIAL_DOCUMENT",
        source_url=evidence.source_url,
        retrieved_at=evidence.retrieved_at,
        content_hash=evidence.content_hash,
        publication=publication,
    )]


def _calculated_value(claim: ClaimSchema, official_value: float) -> float:
    if claim.calculation == "THRESHOLD" and claim.value is not None:
        condition = claim.condition if isinstance(claim.condition, dict) else {}
        operator = str(condition.get("operator") or "GTE").upper()
        satisfied = official_value >= claim.value if operator == "GTE" else official_value > claim.value
        return claim.value if satisfied else official_value
    return official_value


def _claim_tolerance(claim: ClaimSchema) -> float:
    if claim.value is None:
        return 0.0
    if claim.unit in {"%", "%p", "%포인트", "퍼센트"}:
        return 0.05
    return max(abs(claim.value) * 1e-9, 1e-9)
