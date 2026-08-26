"""Source-grounded repair for an indicator contradicted by its own sentence."""

from __future__ import annotations

import re

from core.targeted_claim_splitter import discover_numeric_mentions
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema


def align_claim_indicator_to_concept(
    claim: ClaimSchema, concept: StandardConceptSchema
) -> ClaimSchema:
    """Use a mapped concept only when its alias is explicit and old text is absent."""
    if concept.status != "MATCHED" or not concept.matched_alias:
        return claim
    if len(discover_numeric_mentions(claim.source_sentence)) != 1:
        return claim
    source = _key(claim.source_sentence)
    current = _key(claim.indicator or "")
    matched = _key(concept.matched_alias)
    if not matched or matched not in source:
        return claim
    if current and current in source:
        return claim
    return claim.model_copy(update={"indicator": concept.canonical_name})


def _key(value: str) -> str:
    return re.sub(r"[\s_~\-·/'‘’\"]+", "", value).casefold()
