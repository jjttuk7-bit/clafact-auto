"""Resolve a selected KOSIS table to an auditable evidence coordinate."""

from __future__ import annotations

from core.unit_normalizer import compatible_units
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.evidence import EvidenceCellSchema


def resolve_evidence_cell(claim: ClaimSchema, candidate: KosisCandidateSchema) -> EvidenceCellSchema:
    """Confirm only when every KOSIS dimension is explicitly resolvable."""
    indicator = _normalize(claim.indicator)
    matches = [
        (item_id, item_name)
        for item_id, item_name in zip(candidate.core_item_ids, candidate.core_item_names)
        if _normalize(item_name) == indicator or _normalize(item_name) in indicator
    ]
    status = "CONFIRMED" if len(matches) == 1 and claim.time and claim.unit else "AMBIGUOUS" if len(matches) > 1 else "UNRESOLVED"
    item_id = matches[0][0] if len(matches) == 1 else "UNRESOLVED"
    dimensions, coordinate_resolved = _resolve_dimensions(claim, candidate)
    if not coordinate_resolved:
        status = "UNRESOLVED"
    period = (claim.time or "UNRESOLVED").replace("년", "")
    unit = next((value for value in candidate.unit_names if claim.unit and compatible_units(claim.unit, value)), None)
    if unit is None:
        status = "UNRESOLVED"
    frequency = candidate.frequency or claim.frequency or "UNRESOLVED"
    first_dimension = next(iter(dimensions.items()), (None, None))
    return EvidenceCellSchema(
        org_id=candidate.org_id,
        tbl_id=candidate.tbl_id,
        itm_id=item_id,
        obj_id=first_dimension[0],
        member_code=first_dimension[1],
        dimension_members=dimensions,
        prd_se=frequency,
        prd_de=period,
        unit=unit,
        canonical_key=_key(candidate.org_id, candidate.tbl_id, item_id, first_dimension[0], first_dimension[1], frequency, period, dimensions),
        status=status,
    )


def _resolve_dimensions(claim: ClaimSchema, candidate: KosisCandidateSchema) -> tuple[dict[str, str], bool]:
    if not candidate.dimension_ids:
        return {}, True
    target = _normalize(" ".join(filter(None, [claim.region, claim.population, claim.dimension, claim.indicator])))
    selected: dict[str, str] = {}
    for dimension_id in candidate.dimension_ids:
        members = candidate.dimension_members.get(dimension_id, [])
        if len(members) == 1:
            selected[dimension_id] = members[0]
            continue
        matches = [member for member in members if _normalize(member) and _normalize(member) in target]
        if len(matches) != 1:
            return {}, False
        selected[dimension_id] = matches[0]
    return selected, True


def _normalize(value: str | None) -> str:
    return (value or "").replace(" ", "").replace("-", "")


def _key(org: str, table: str, item: str, obj: str | None, member: str | None, prd_se: str, prd_de: str, dimensions: dict[str, str]) -> str:
    base = f"ORG={org}|TBL={table}|ITM={item}|OBJ={obj}|MEMBER={member}|PRD_SE={prd_se}|PRD_DE={prd_de}"
    if len(dimensions) <= 1:
        return base
    encoded = ",".join(f"{key}:{value}" for key, value in dimensions.items())
    return f"{base}|DIMS={encoded}"
