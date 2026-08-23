"""Public Hard Guard with deterministic Claim-side vocabulary normalization."""
from core.claim_candidate_aliases import normalize_claim_for_candidate
from core.hard_guard_impl import apply_hard_guard as _apply

def apply_hard_guard(claim, candidate):
    return _apply(normalize_claim_for_candidate(claim, candidate), candidate)
