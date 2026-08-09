"""Adapter boundary for the existing CLAFACT review console."""
from dataclasses import dataclass
from typing import Protocol
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
    return ReviewPayload(verdict.claim_id, verdict.route_status, verdict.reason_code, len(verdict.evidence_cells))
