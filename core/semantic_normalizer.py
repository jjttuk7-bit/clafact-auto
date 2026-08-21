"""Deterministic mapping from claim indicators to semantic standards."""

from __future__ import annotations

import re
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Iterable

from core.claim_dimensions import dimension_member_values
from core.data_loader import SemanticStandardRecord
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema


def normalize_concept(
    claim: ClaimSchema,
    concepts: Iterable[SemanticStandardRecord],
    *,
    similarity_threshold: float = 0.86,
) -> StandardConceptSchema:
    """Map an indicator without selecting ties or below-threshold candidates."""
    concept_list = list(concepts)
    indicator = claim.indicator
    if not indicator:
        return _unresolved()

    source_matches = _source_context_matches(claim, concept_list)
    if len(source_matches) == 1:
        return _matched(*source_matches[0])
    if len(source_matches) > 1:
        return _unresolved()

    for contextual_label in _contextual_labels(claim):
        contextual_matches = _label_matches(
            contextual_label, concept_list, normalize=True
        )
        if len(contextual_matches) == 1:
            return _matched(*contextual_matches[0])
        if len(contextual_matches) > 1:
            return _unresolved()

    exact_matches = _label_matches(indicator, concept_list, normalize=False)
    if len(exact_matches) == 1:
        return _matched(*exact_matches[0])
    if len(exact_matches) > 1:
        return _unresolved()

    normalized_matches = _label_matches(indicator, concept_list, normalize=True)
    if len(normalized_matches) == 1:
        return _matched(*normalized_matches[0])
    if len(normalized_matches) > 1:
        return _unresolved()

    scored = _similarity_matches(indicator, concept_list)
    if not scored or scored[0][0] < similarity_threshold:
        return _unresolved()
    best_score = scored[0][0]
    best_matches = [match for score, *match in scored if score == best_score]
    if len(best_matches) != 1:
        return _unresolved()
    return _matched(*best_matches[0])



def _source_context_matches(
    claim: ClaimSchema, concepts: list[SemanticStandardRecord]
) -> list[tuple[SemanticStandardRecord, str]]:
    """Use a unique, more-specific source indicator only for a generic parsed slot."""
    indicator = _normalize_text(claim.indicator or "")
    source = _normalize_text(claim.source_sentence)
    if not indicator or not source:
        return []
    matches: list[tuple[SemanticStandardRecord, str]] = []
    for concept in concepts:
        for label in (concept.canonical_name, *concept.aliases):
            normalized_label = _normalize_text(label)
            if (
                len(normalized_label) > len(indicator)
                and indicator in normalized_label
                and normalized_label in source
            ):
                matches.append((concept, label))
    if not matches:
        return []
    longest = max(len(_normalize_text(label)) for _, label in matches)
    return _unique_by_concept([
        (concept, label) for concept, label in matches
        if len(_normalize_text(label)) == longest
    ])
def _contextual_labels(claim: ClaimSchema) -> list[str]:
    indicator = (claim.indicator or "").strip()
    if not indicator:
        return []
    labels: list[str] = []
    for member in dimension_member_values(claim.dimension):
        member = member.strip()
        if not member:
            continue
        if _normalize_text(member) in _normalize_text(indicator):
            labels.append(indicator)
        else:
            labels.append(f"{member} {indicator}")
    return list(dict.fromkeys(labels))

def _label_matches(
    indicator: str,
    concepts: list[SemanticStandardRecord],
    *,
    normalize: bool,
) -> list[tuple[SemanticStandardRecord, str]]:
    key = _normalize_text(indicator) if normalize else indicator
    matched: list[tuple[SemanticStandardRecord, str]] = []
    for concept in concepts:
        for label in (concept.canonical_name, *concept.aliases):
            comparison = _normalize_text(label) if normalize else label
            if key == comparison:
                matched.append((concept, label))
    return _unique_by_concept(matched)


def _similarity_matches(
    indicator: str, concepts: list[SemanticStandardRecord]
) -> list[tuple[float, SemanticStandardRecord, str]]:
    grouped: dict[str, tuple[float, SemanticStandardRecord, str]] = {}
    normalized_indicator = _normalize_text(indicator)
    for concept in concepts:
        for label in (concept.canonical_name, *concept.aliases):
            score = SequenceMatcher(None, normalized_indicator, _normalize_text(label)).ratio()
            current = grouped.get(concept.concept_id)
            if current is None or score > current[0]:
                grouped[concept.concept_id] = (score, concept, label)
    return sorted(grouped.values(), key=lambda item: item[0], reverse=True)


def _unique_by_concept(
    matches: list[tuple[SemanticStandardRecord, str]]
) -> list[tuple[SemanticStandardRecord, str]]:
    unique: dict[str, tuple[SemanticStandardRecord, str]] = {}
    for concept, label in matches:
        unique.setdefault(concept.concept_id, (concept, label))
    return list(unique.values())


def _normalize_text(value: str) -> str:
    return re.sub(r"[\s_-]+", "", value).casefold()


def _matched(concept: SemanticStandardRecord, label: str) -> StandardConceptSchema:
    return StandardConceptSchema(
        concept_id=concept.concept_id,
        canonical_name=concept.canonical_name,
        standard_key=concept.standard_key,
        matched_alias=label,
        kosis_search_terms=list(concept.kosis_search_terms),
        status="MATCHED",
    )


def _unresolved() -> StandardConceptSchema:
    return StandardConceptSchema(
        concept_id="UNRESOLVED",
        canonical_name="UNRESOLVED",
        standard_key="unresolved",
        status="UNRESOLVED",
    )
