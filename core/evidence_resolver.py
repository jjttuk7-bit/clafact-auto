"""Resolve a selected KOSIS table to an auditable evidence coordinate."""

from __future__ import annotations

import re

from core.member_code_mapper import resolve_member_code
from core.unit_normalizer import compatible_units
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.evidence import EvidenceCellSchema


def resolve_evidence_cell(claim: ClaimSchema, candidate: KosisCandidateSchema) -> EvidenceCellSchema:
    """Confirm an evidence cell only from catalog metadata or registered official coordinates."""
    dimensions, coordinate_resolved = _resolve_dimensions(claim, candidate)
    indicator_terms = _indicator_terms(claim)
    matches = [
        (item_id, item_name)
        for item_id, item_name in zip(candidate.core_item_ids, candidate.core_item_names)
        if _item_matches_indicator(_normalize(item_name), indicator_terms)
    ]
    status = "CONFIRMED" if len(matches) == 1 and claim.time and claim.unit else "AMBIGUOUS" if len(matches) > 1 else "UNRESOLVED"
    item_id = matches[0][0] if len(matches) == 1 else "UNRESOLVED"
    if not coordinate_resolved:
        status = "UNRESOLVED"
    unit = next((value for value in candidate.unit_names if claim.unit and compatible_units(claim.unit, value)), None)
    if unit is None and claim.calculation in {"GROWTH_RATE", "SHARE", "RATIO", "MULTIPLE"}:
        unit = candidate.unit_names[0] if len(candidate.unit_names) == 1 else None
    if unit is None:
        status = "UNRESOLVED"
    frequency = _resolve_frequency(claim.frequency, candidate.frequency)
    period = _period_key(claim.time)
    dimension_codes = _resolve_dimension_codes(dimensions, candidate.dimension_member_codes)
    if set(dimension_codes) != set(dimensions):
        status = "UNRESOLVED"
    obj_id, member_code = next(iter(dimensions.items()), (None, None))
    canonical_key = _key(
        candidate.org_id,
        candidate.tbl_id,
        item_id,
        obj_id,
        member_code,
        frequency,
        period,
        dimensions,
        include_dimensions=True,
    )
    return EvidenceCellSchema(
        org_id=candidate.org_id,
        tbl_id=candidate.tbl_id,
        itm_id=item_id,
        obj_id=obj_id,
        member_code=member_code,
        dimension_members=dimensions,
        dimension_codes=dimension_codes,
        prd_se=frequency,
        prd_de=period,
        unit=unit,
        canonical_key=canonical_key,
        status=status,
    )


def _resolve_dimensions(claim: ClaimSchema, candidate: KosisCandidateSchema) -> tuple[dict[str, str], bool]:
    if not candidate.dimension_ids:
        return {}, True
    target = _normalize(" ".join(filter(None, [claim.region, claim.population, _dimension_text(claim.dimension), claim.indicator])))
    selected: dict[str, str] = {}
    for dimension_id in candidate.dimension_ids:
        members = candidate.dimension_members.get(dimension_id, [])
        if len(members) == 1:
            selected[dimension_id] = members[0]
            continue
        matches = [member for member in members if _normalize(member) and _normalize(member) in target]
        if len(matches) == 1:
            selected[dimension_id] = matches[0]
            continue
        total_members = [member for member in members if _is_total_member(member)]
        if not matches and len(total_members) == 1:
            selected[dimension_id] = total_members[0]
            continue
        return {}, False
    return selected, True


def _dimension_text(value: dict[str, str] | None) -> str | None:
    """Flatten the structured 12-slot dimension into deterministic search text."""
    if not value:
        return None
    return " ".join(str(item) for item in value.values())

def _is_total_member(member: str) -> bool:
    normalized = _normalize(member)
    return normalized in {"계", "전체", "합계"} or normalized.endswith("계")


def _resolve_frequency(claim_frequency: str | None, candidate_frequency: str | None) -> str:
    """Use the claim frequency when it is explicitly supported by a multi-frequency table."""
    if claim_frequency and candidate_frequency:
        available = {part.strip() for part in candidate_frequency.split("|")}
        if claim_frequency in available:
            return claim_frequency
    return candidate_frequency or claim_frequency or "UNRESOLVED"

def _period_key(value: str | None) -> str:
    if not value:
        return "UNRESOLVED"
    match = re.search(r"(?P<year>\d{4})\s*년?\s*(?P<month>\d{1,2})\s*월", value)
    if match:
        return f"{match.group('year')}-{int(match.group('month')):02d}"
    return value.replace("년", "").strip()


def _resolve_dimension_codes(
    dimensions: dict[str, str],
    candidate_codes: dict[str, dict[str, str]],
) -> dict[str, str]:
    return {
        dimension_id: code
        for dimension_id, member_name in dimensions.items()
        if (code := resolve_member_code(candidate_codes, dimension_id, member_name)) is not None
    }


def _normalize(value: str | None) -> str:
    return (value or "").replace(" ", "").replace("-", "")


def _key(org: str, table: str, item: str, obj: str | None, member: str | None, prd_se: str, prd_de: str, dimensions: dict[str, str], *, include_dimensions: bool) -> str:
    base = f"ORG={org}|TBL={table}|ITM={item}|OBJ={obj}|MEMBER={member}|PRD_SE={prd_se}|PRD_DE={prd_de}"
    if not include_dimensions or len(dimensions) <= 1:
        return base
    encoded = ",".join(f"{key}:{value}" for key, value in dimensions.items())
    return f"{base}|DIMS={encoded}"


def _indicator_terms(claim: ClaimSchema) -> set[str]:
    """Keep the base statistical concept available for derived-rate Claims."""
    indicator = _normalize(claim.indicator)
    terms = {indicator} if indicator else set()
    if claim.calculation not in {"GROWTH_RATE", "SHARE", "RATIO", "MULTIPLE"}:
        return terms
    for suffix in (
        "\uc0c1\uc2b9\ub960", "\ud558\ub77d\ub960", "\uc99d\uac00\uc728", "\uac10\uc18c\uc728",
        "\ub4f1\ub77d\ub960", "\ubcc0\ub3d9\ub960",
    ):
        if indicator.endswith(suffix):
            base = indicator[: -len(suffix)]
            if base:
                terms.add(base)
    return terms


def _item_matches_indicator(item: str, terms: set[str]) -> bool:
    return any(item == term or item in term or term in item for term in terms if term)