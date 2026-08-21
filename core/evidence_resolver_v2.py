"""Metadata-driven aliases for recurring KOSIS coordinate axes."""

from __future__ import annotations

import re

from core.evidence_resolver import resolve_evidence_cell as _base_resolve
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema


def resolve_evidence_cell_v2(claim: ClaimSchema, candidate: KosisCandidateSchema):
    return _base_resolve(enrich_claim_for_official_axes(claim, candidate), candidate)


def enrich_claim_for_official_axes(claim: ClaimSchema, candidate: KosisCandidateSchema) -> ClaimSchema:
    """Map indicator aliases to otherwise unnamed KOSIS kind/item axes."""
    dimensions = dict(claim.dimension or {})
    existing = {_key(value) for value in dimensions.values()}
    indicator = _key(claim.indicator or "")
    for index, axis_id in enumerate(candidate.dimension_ids):
        axis_name = candidate.dimension_names[index] if index < len(candidate.dimension_names) else axis_id
        members = candidate.dimension_members.get(axis_id, [])
        if any(_key(member) in existing for member in members):
            continue
        selected = _select_member(indicator, members)
        if selected is not None:
            dimensions[axis_name] = selected
            existing.add(_key(selected))
    return claim if dimensions == (claim.dimension or {}) else claim.model_copy(update={"dimension": dimensions})


def _select_member(indicator: str, members: list[str]) -> str | None:
    exact = [member for member in members if _key(member) and (_key(member) in indicator or indicator in _key(member))]
    if len(exact) == 1:
        return exact[0]
    aliases = (
        (("출생아",), ("출생아수", "출생")),
        (("사망자",), ("사망자수", "사망")),
        (("합계출산",), ("합계출산율",)),
        (("외식",), ("외식",)),
        (("소비자물가",), ("총지수", "전체")),
        (("산업생산", "전산업생산"), ("전산업", "전체")),
    )
    for indicator_terms, member_terms in aliases:
        if any(term in indicator for term in indicator_terms):
            matches = [member for member in members if any(_key(term) in _key(member) for term in member_terms)]
            if len(matches) == 1:
                return matches[0]
    return None


def _key(value: str) -> str:
    return re.sub(r"[\s_~\-]+", "", value).casefold()


def install() -> None:
    """Install the resolver at the verifier seam used by all official services."""
    import core.dynamic_kosis_verifier as verifier
    verifier.resolve_evidence_cell = resolve_evidence_cell_v2
