"""Read-only adapter boundary for KOSIS table metadata."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, Mapping

from schemas.candidate import KosisCandidateSchema


@dataclass(frozen=True, slots=True)
class OfficialTableStructure:
    table_id: str
    item_codes: dict[str, str]
    dimension_ids: dict[str, str]
    unit_names: list[str]
    dimension_members: dict[str, list[str]] = field(default_factory=dict)
    dimension_member_codes: dict[str, dict[str, str]] = field(default_factory=dict)
    item_units: dict[str, str] = field(default_factory=dict)


class KosisCatalogAdapter:
    def __init__(self, request: Callable[[str], dict[str, Any]]) -> None:
        self.request = request

    def fetch_table_metadata(self, table_id: str) -> dict[str, Any]:
        payload = self.request(table_id)
        if str(payload.get("TBL_ID", "")) != table_id:
            raise ValueError("KOSIS metadata response does not match requested table")
        return payload


def normalize_item_metadata(rows: Iterable[Mapping[str, object]], *, table_id: str) -> OfficialTableStructure:
    """Normalize KOSIS ITM metadata into items, axes, and official member codes."""
    item_codes: dict[str, str] = {}
    dimension_ids: dict[str, str] = {}
    dimension_members: dict[str, list[str]] = {}
    dimension_member_codes: dict[str, dict[str, str]] = {}
    unit_names: list[str] = []
    item_units: dict[str, str] = {}
    for row in rows:
        if str(row.get("TBL_ID", "")) != table_id:
            raise ValueError("KOSIS item metadata response does not match requested table")
        item_name, item_id = str(row.get("ITM_NM", "")).strip(), str(row.get("ITM_ID", "")).strip()
        dimension_name, dimension_id = str(row.get("OBJ_NM", "")).strip(), str(row.get("OBJ_ID", "")).strip()
        unit = str(row.get("UNIT_NM", "")).strip()
        is_measurement_item = dimension_id == "ITEM" or bool(unit)
        if is_measurement_item and item_name and item_id:
            item_codes[item_name] = item_id
            if unit:
                item_units[item_id] = unit
        if dimension_name and dimension_id and dimension_id != "ITEM":
            dimension_ids[dimension_name] = dimension_id
        if not is_measurement_item and dimension_id and item_name and item_id:
            dimension_members.setdefault(dimension_id, []).append(item_name)
            dimension_member_codes.setdefault(dimension_id, {})[item_name] = item_id
        if unit and unit not in unit_names:
            unit_names.append(unit)
    if not item_codes:
        raise ValueError("KOSIS item metadata does not contain a measurement item")
    return OfficialTableStructure(
        table_id, item_codes, dimension_ids, unit_names, dimension_members,
        dimension_member_codes, item_units,
    )


def hydrate_candidate(candidate: KosisCandidateSchema, official_structure: OfficialTableStructure) -> KosisCandidateSchema:
    """Apply verified KOSIS metadata without inferring unavailable coordinates."""
    if candidate.tbl_id != official_structure.table_id:
        raise ValueError("Official KOSIS metadata table does not match candidate")
    return candidate.model_copy(
        update={
            "core_item_ids": list(official_structure.item_codes.values()),
            "core_item_names": list(official_structure.item_codes),
            "dimension_ids": list(official_structure.dimension_ids.values()),
            "dimension_names": list(official_structure.dimension_ids),
            "dimension_members": official_structure.dimension_members,
            "dimension_member_codes": official_structure.dimension_member_codes,
            "unit_names": list(official_structure.unit_names),
            "item_units": dict(official_structure.item_units),
            "metadata_status": "OFFICIAL_ITEM_METADATA_READY",
        }
    )


def hydrate_candidates_from_official_metadata(
    candidates: Iterable[KosisCandidateSchema],
    fetch_item_metadata: Callable[[str, str], Iterable[Mapping[str, object]]],
) -> list[KosisCandidateSchema]:
    """Refresh KOSIS metadata; leave a candidate unchanged on fetch failure."""
    hydrated: list[KosisCandidateSchema] = []
    for candidate in candidates:
        try:
            structure = normalize_item_metadata(fetch_item_metadata(candidate.org_id, candidate.tbl_id), table_id=candidate.tbl_id)
            hydrated.append(hydrate_candidate(candidate, structure))
        except (RuntimeError, TypeError, ValueError):
            hydrated.append(
                candidate
                if candidate.metadata_status == "OFFICIAL_METADATA_READY"
                else candidate.model_copy(
                    update={"metadata_status": "OFFICIAL_ITEM_METADATA_UNAVAILABLE"}
                )
            )
    return hydrated
