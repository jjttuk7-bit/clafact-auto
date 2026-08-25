"""Adapter boundary for the existing CLAFACT review console."""
from dataclasses import dataclass
from typing import Protocol
from core.official_source_presentation import build_official_source_presentation
from schemas.verdict import VerdictSchema

@dataclass(frozen=True, slots=True)
class ReviewPayload:
    claim_id: str
    route_status: str
    reason_code: str
    evidence_count: int

class ReviewConsoleAdapter(Protocol):
    def submit(self, payload: ReviewPayload) -> str: ...

def build_review_payload(verdict: VerdictSchema) -> ReviewPayload:
    presentation = build_official_source_presentation(verdict)
    return ReviewPayload(
        verdict.claim_id, verdict.route_status, verdict.reason_code, presentation.evidence_count
    )
