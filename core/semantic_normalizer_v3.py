"""Semantic Standard v3 with safe observed-indicator registration."""

from __future__ import annotations

from hashlib import sha256
import re
from typing import Iterable

from core.data_loader import SemanticStandardRecord
from core.semantic_normalizer import normalize_concept
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema


_GENERIC_RATE = re.compile(r"^(?:증가율|감소율|증감률|변동률|상승률|하락률)$")


def normalize_concept_v3(claim: ClaimSchema, concepts: Iterable[SemanticStandardRecord]) -> StandardConceptSchema:
    """Resolve standards first, then register only an explicit observed indicator."""
    concept_list = list(concepts)
    resolved = normalize_concept(claim, concept_list)
    if resolved.status == "MATCHED":
        return resolved
    indicator = (claim.indicator or "").strip()
    if indicator and _GENERIC_RATE.fullmatch(indicator.replace(" ", "")):
        labels = _unique_source_labels(claim.source_sentence, concept_list)
        if len(labels) == 1:
            return normalize_concept(claim.model_copy(update={"indicator": labels[0]}), concept_list)
    if not indicator:
        return resolved
    digest = sha256(_key(indicator).encode("utf-8")).hexdigest()[:16]
    return StandardConceptSchema(
        concept_id=f"OBSERVED:{digest}", canonical_name=indicator,
        standard_key=f"observed_indicator_{digest}", matched_alias=indicator,
        kosis_search_terms=[indicator], status="MATCHED",
    )


def _unique_source_labels(source: str, concepts: list[SemanticStandardRecord]) -> list[str]:
    normalized_source = _key(source)
    matches = []
    for concept in concepts:
        labels = [concept.canonical_name, *concept.aliases]
        present = [label for label in labels if _key(label) and _key(label) in normalized_source]
        if present:
            matches.append(max(present, key=lambda label: len(_key(label))))
    if not matches:
        return []
    longest = max(len(_key(label)) for label in matches)
    return list(dict.fromkeys(label for label in matches if len(_key(label)) == longest))


def _key(value: str) -> str:
    return re.sub(r"[\s_~\-]+", "", value).casefold()
