"""Bounded routing from numeric candidates to official verification."""

from __future__ import annotations

import re

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from core.claim_admission_router import route_claim_admission
from core.claim_splitter import detect_structural_multi_claim, split_complex_claim
from schemas.claim import ClaimSchema
from schemas.claim_admission import AdmissionDecision, AdmissionEvent, AdmissionRouteResult


OfficialResolver = Callable[[ClaimSchema], Mapping[str, Any]]
ContextReparser = Callable[[ClaimSchema], ClaimSchema]
ChildParser = Callable[[ClaimSchema, str, str], ClaimSchema]
AdmissionRouter = Callable[[ClaimSchema], AdmissionDecision]

_HISTORICAL_REFERENCE_ONLY = re.compile(
    r"(?:지난해|작년|전년)\s*\d{1,2}월\s*\([^)]*\)\s*을?\s*(?:저점|고점|기록).*?(?:오름세|내림세|시사)"
)


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
        return self._process(claim, context_attempted=False, split_depth=0, events=[])

    def _process(
        self,
        claim: ClaimSchema,
        *,
        context_attempted: bool,
        split_depth: int,
        events: list[AdmissionEvent],
    ) -> list[ClaimAdmissionExecution]:
        decision = _structural_split_guard(claim) or _historical_context_guard(claim) or self._admission_router(claim)
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
                split_depth=split_depth,
                events=[*admitted_events, _event("CLAIM_CONTEXT_REPARSE", claim, decision)],
            )
        if decision.label == "MULTI_CLAIM_SPLIT_REQUIRED" and split_depth < 2 and self._child_parser:
            parts = split_complex_claim(claim.source_sentence)
            if len(parts) > 1:
                executions: list[ClaimAdmissionExecution] = []
                for index, part in enumerate(parts, start=1):
                    child = self._child_parser(claim, part, f"{claim.claim_id}__split_{index}")
                    executions.extend(self._process(
                        child,
                        context_attempted=context_attempted,
                        split_depth=split_depth + 1,
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


def _historical_context_guard(claim: ClaimSchema) -> AdmissionDecision | None:
    """Require context when a sentence states only a historical reference and trend."""
    if not _HISTORICAL_REFERENCE_ONLY.search(claim.source_sentence):
        return None
    return AdmissionDecision(
        label="CONTEXT_REQUIRED", reason_code="HISTORICAL_REFERENCE_CONTEXT"
    )

def _structural_split_guard(claim: ClaimSchema) -> AdmissionDecision | None:
    """Block KOSIS admission before an injected model can choose ELIGIBLE."""
    if not detect_structural_multi_claim(claim.source_sentence):
        return None
    return AdmissionDecision(
        label="MULTI_CLAIM_SPLIT_REQUIRED", reason_code="STRUCTURAL_MULTI_CLAIM"
    )

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

