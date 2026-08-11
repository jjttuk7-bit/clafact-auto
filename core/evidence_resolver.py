"""Resolve a selected KOSIS table to an auditable evidence coordinate."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from core.member_code_mapper import resolve_member_code
from core.unit_normalizer import compatible_units
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.evidence import EvidenceCellSchema

_DATA_ROOT = Path(__file__).resolve().parents[1] / "data" / "kosis_catalog"


def resolve_evidence_cell(claim: ClaimSchema, candidate: KosisCandidateSchema) -> EvidenceCellSchema:
    """Confirm an evidence cell only from catalog metadata or registered official coordinates."""
    dimensions, coordinate_resolved = _resolve_dimensions(claim, candidate)
    if not coordinate_resolved:
        registered_dimensions = _registered_dimensions(candidate.tbl_id, candidate.dimension_ids)
        if registered_dimensions is not None:
            dimensions, coordinate_resolved = registered_dimensions, True
    indicator = _normalize(claim.indicator)
    matches = [
        (item_id, item_name)
        for item_id, item_name in zip(candidate.core_item_ids, candidate.core_item_names)
        if _normalize(item_name) == indicator or _normalize(item_name) in indicator
    ]
    registered_item_id = _registered_item_id(candidate.tbl_id, dimensions) if coordinate_resolved else None
    status = "CONFIRMED" if (len(matches) == 1 or registered_item_id is not None) and claim.time and claim.unit else "AMBIGUOUS" if len(matches) > 1 else "UNRESOLVED"
    item_id = matches[0][0] if len(matches) == 1 else registered_item_id or "UNRESOLVED"
    if not coordinate_resolved:
        status = "UNRESOLVED"
    unit = next((value for value in candidate.unit_names if claim.unit and compatible_units(claim.unit, value)), None)
    if unit is None:
        status = "UNRESOLVED"
    frequency = _resolve_frequency(claim.frequency, candidate.frequency)
    period = _period_key(claim.time)
    dimension_codes = _resolve_dimension_codes(candidate.tbl_id, dimensions, candidate.dimension_member_codes)
    if set(dimension_codes) != set(dimensions):
        status = "UNRESOLVED"
    registered = _registered_coordinate(candidate.tbl_id, item_id, dimensions)
    first_dimension = next(iter(dimensions.items()), (None, None))
    obj_id, member_code = (registered if registered else first_dimension)
    canonical_key = _key(
        candidate.org_id,
        candidate.tbl_id,
        item_id,
        obj_id,
        member_code,
        frequency,
        period,
        dimensions,
        include_dimensions=registered is None,
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


@lru_cache(maxsize=1)
def _member_code_registry() -> dict[str, dict[str, dict[str, str]]]:
    source = _DATA_ROOT / "member_codes_goldset.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    grouped: dict[str, dict[str, dict[str, str]]] = {}
    for row in payload:
        grouped.setdefault(row["tbl_id"], {}).setdefault(row["dimension_id"], {})[row["member_name"]] = row["member_code"]
    return grouped


def _resolve_dimension_codes(
    table_id: str,
    dimensions: dict[str, str],
    candidate_codes: dict[str, dict[str, str]],
) -> dict[str, str]:
    mapping = dict(_member_code_registry().get(table_id, {}))
    mapping.update(candidate_codes)
    return {
        dimension_id: code
        for dimension_id, member_name in dimensions.items()
        if (code := resolve_member_code(mapping, dimension_id, member_name)) is not None
    }


@lru_cache(maxsize=1)
def _coordinate_registry() -> tuple[dict[str, object], ...]:
    source = _DATA_ROOT / "evidence_coordinates_goldset.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    return tuple(row for row in payload if isinstance(row, dict))


def _registered_dimensions(table_id: str, dimension_ids: list[str]) -> dict[str, str] | None:
    """Use dimensions only when one registered official profile matches the table shape."""
    profiles = {
        tuple(sorted((str(key), str(value)) for key, value in row.get("dimension_members", {}).items()))
        for row in _coordinate_registry()
        if row.get("tbl_id") == table_id
        and isinstance(row.get("dimension_members"), dict)
        and set(row["dimension_members"]) == set(dimension_ids)
    }
    if len(profiles) != 1:
        return None
    return dict(next(iter(profiles)))

def _registered_item_id(table_id: str, dimensions: dict[str, str]) -> str | None:
    """Use an item only when one explicit official coordinate exactly matches dimensions."""
    item_ids = {
        row.get("itm_id")
        for row in _coordinate_registry()
        if row.get("tbl_id") == table_id
        and row.get("dimension_members") == dimensions
        and isinstance(row.get("itm_id"), str)
    }
    return next(iter(item_ids)) if len(item_ids) == 1 else None

def _registered_coordinate(table_id: str, item_id: str, dimensions: dict[str, str]) -> tuple[str, str] | None:
    for row in _coordinate_registry():
        if row.get("tbl_id") == table_id and row.get("itm_id") == item_id and row.get("dimension_members") == dimensions:
            obj_id, member_code = row.get("obj_id"), row.get("member_code")
            if isinstance(obj_id, str) and isinstance(member_code, str):
                return obj_id, member_code
    return None


def _normalize(value: str | None) -> str:
    return (value or "").replace(" ", "").replace("-", "")


def _key(org: str, table: str, item: str, obj: str | None, member: str | None, prd_se: str, prd_de: str, dimensions: dict[str, str], *, include_dimensions: bool) -> str:
    base = f"ORG={org}|TBL={table}|ITM={item}|OBJ={obj}|MEMBER={member}|PRD_SE={prd_se}|PRD_DE={prd_de}"
    if not include_dimensions or len(dimensions) <= 1:
        return base
    encoded = ",".join(f"{key}:{value}" for key, value in dimensions.items())
    return f"{base}|DIMS={encoded}"
