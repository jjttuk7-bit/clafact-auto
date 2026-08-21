"""Read-only adapter boundary for KOSIS table metadata."""

from collections.abc import Callable, Iterable
from typing import Mapping
from core.kosis_catalog_adapter_impl import KosisCatalogAdapter, OfficialTableStructure, hydrate_candidate
from schemas.candidate import KosisCandidateSchema

__all__ = ["KosisCatalogAdapter", "OfficialTableStructure", "normalize_item_metadata", "hydrate_candidate", "hydrate_candidates_from_official_metadata"]


def normalize_item_metadata(rows: Iterable[Mapping[str, object]], *, table_id: str) -> OfficialTableStructure:
    item_codes = {}
    dimension_ids = {}
    dimension_members = {}
    dimension_member_codes = {}
    unit_names = []
    item_units = {}
    for row in rows:
        if str(row.get("TBL_ID", "")) != table_id:
            raise ValueError("KOSIS item metadata response does not match requested table")
        name = str(row.get("ITM_NM", "")).strip()
        item_id = str(row.get("ITM_ID", "")).strip()
        axis_name = str(row.get("OBJ_NM", "")).strip()
        axis_id = str(row.get("OBJ_ID", "")).strip()
        unit = str(row.get("UNIT_NM", "")).strip()
        is_axis_member = axis_id != "ITEM" and bool(str(row.get("OBJ_ID_SN", "")).strip())
        is_measurement = axis_id == "ITEM" or (bool(unit) and not is_axis_member)
        if is_measurement and name and item_id:
            item_codes[name] = item_id
            if unit:
                item_units[item_id] = unit
        if axis_name and axis_id and axis_id != "ITEM":
            dimension_ids[axis_name] = axis_id
        if not is_measurement and axis_id and name and item_id:
            dimension_members.setdefault(axis_id, []).append(name)
            dimension_member_codes.setdefault(axis_id, {})[name] = item_id
        if unit and unit not in unit_names:
            unit_names.append(unit)
    if not item_codes:
        raise ValueError("KOSIS item metadata does not contain a measurement item")
    return OfficialTableStructure(table_id, item_codes, dimension_ids, unit_names, dimension_members, dimension_member_codes, item_units)


def hydrate_candidates_from_official_metadata(
    candidates: Iterable[KosisCandidateSchema],
    fetch_item_metadata: Callable[[str, str], Iterable[Mapping[str, object]]],
) -> list[KosisCandidateSchema]:
    hydrated = []
    for candidate in candidates:
        try:
            hydrated.append(hydrate_candidate(candidate, normalize_item_metadata(fetch_item_metadata(candidate.org_id, candidate.tbl_id), table_id=candidate.tbl_id)))
        except (RuntimeError, TypeError, ValueError):
            hydrated.append(candidate if candidate.metadata_status == "OFFICIAL_METADATA_READY" else candidate.model_copy(update={"metadata_status": "OFFICIAL_ITEM_METADATA_UNAVAILABLE"}))
    return hydrated
