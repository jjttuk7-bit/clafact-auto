"""Bounded routing from numeric candidates to official verification."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from core.claim_admission_router import route_claim_admission
from core.claim_splitter import split_complex_claim
from schemas.claim import ClaimSchema
from schemas.claim_admission import AdmissionDecision, AdmissionEvent, AdmissionRouteResult


OfficialResolver = Callable[[ClaimSchema], Mapping[str, Any]]
ContextReparser = Callable[[ClaimSchema], ClaimSchema]
ChildParser = Callable[[ClaimSchema, str, str], ClaimSchema]
AdmissionRouter = Callable[[ClaimSchema], AdmissionDecision]


@dataclass(frozen=True)
class ClaimAdmissionExecution:
    """One admitted or safely routed Claim with its optional official output."""

    claim: ClaimSchema
    result: AdmissionRouteResult
    official_result: Mapping[str, Any] | None


class ClaimAdmissionPipeline:
    """Re-admit bounded context/split derivatives before calling official KOSIS code."""

    def __init__(
        self,
        *,
        official_resolver: OfficialResolver,
        context_reparser: ContextReparser | None = None,
        child_parser: ChildParser | None = None,
        admission_router: AdmissionRouter = route_claim_admission,
    ) -> None:
        self._official_resolver = official_resolver
        self._context_reparser = context_reparser
        self._child_parser = child_parser
        self._admission_router = admission_router

    def process(self, claim: ClaimSchema) -> list[ClaimAdmissionExecution]:
        """Process a source candidate with at most one context and split generation."""
        return self._process(claim, context_attempted=False, split_attempted=False, events=[])

    def _process(
        self,
        claim: ClaimSchema,
        *,
        context_attempted: bool,
        split_attempted: bool,
        events: list[AdmissionEvent],
    ) -> list[ClaimAdmissionExecution]:
        decision = self._admission_router(claim)
        admitted_events = [*events, _event("CLAIM_ADMISSION", claim, decision)]
        if decision.label == "KOSIS_PIPELINE_ELIGIBLE":
            official_result = self._official_resolver(claim)
            return [ClaimAdmissionExecution(
                claim=claim,
                result=AdmissionRouteResult(
                    claim_id=claim.claim_id,
                    route_status="OFFICIAL_VERIFICATION_STARTED",
                    decision=decision,
                    events=[*admitted_events, _event("OFFICIAL_VERIFICATION", claim, decision)],
                ),
                official_result=official_result,
            )]
        if decision.label == "CONTEXT_REQUIRED" and not context_attempted and self._context_reparser:
            reparsed = self._context_reparser(claim)
            return self._process(
                reparsed,
                context_attempted=True,
                split_attempted=split_attempted,
                events=[*admitted_events, _event("CLAIM_CONTEXT_REPARSE", claim, decision)],
            )
        if decision.label == "MULTI_CLAIM_SPLIT_REQUIRED" and not split_attempted and self._child_parser:
            parts = split_complex_claim(claim.source_sentence)
            if len(parts) > 1:
                executions: list[ClaimAdmissionExecution] = []
                for index, part in enumerate(parts, start=1):
                    child = self._child_parser(claim, part, f"{claim.claim_id}__split_{index}")
                    executions.extend(self._process(
                        child,
                        context_attempted=context_attempted,
                        split_attempted=True,
                        events=[*admitted_events, _event("CLAIM_SPLIT", claim, decision, detail=part)],
                    ))
                return executions
        return [ClaimAdmissionExecution(
            claim=claim,
            result=AdmissionRouteResult(
                claim_id=claim.claim_id,
                route_status="ADMISSION_ROUTED",
                decision=decision,
                events=admitted_events,
            ),
            official_result=None,
        )]


def _event(
    stage: str, claim: ClaimSchema, decision: AdmissionDecision, *, detail: str | None = None
) -> AdmissionEvent:
    return AdmissionEvent(
        stage=stage,
        claim_id=claim.claim_id,
        label=decision.label,
        reason_code=decision.reason_code,
        detail=detail,
    )

