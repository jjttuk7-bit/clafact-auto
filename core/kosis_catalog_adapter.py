"""Read-only adapter boundary for KOSIS table metadata."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, Mapping

from schemas.candidate import KosisCandidateSchema


@dataclass(frozen=True, slots=True)
class OfficialTableStructure:
    table_id: str
    item_codes: dict[str, str]
    dimension_ids: dict[str, str]
    unit_names: list[str]


class KosisCatalogAdapter:
    def __init__(self, request: Callable[[str], dict[str, Any]]) -> None:
        self.request = request

    def fetch_table_metadata(self, table_id: str) -> dict[str, Any]:
        payload = self.request(table_id)
        if str(payload.get("TBL_ID", "")) != table_id:
            raise ValueError("KOSIS metadata response does not match requested table")
        return payload


def normalize_item_metadata(rows: Iterable[Mapping[str, object]], *, table_id: str) -> OfficialTableStructure:
    """Normalize only official ITM metadata; never infer unavailable member codes."""
    item_codes: dict[str, str] = {}
    dimension_ids: dict[str, str] = {}
    unit_names: list[str] = []
    for row in rows:
        if str(row.get("TBL_ID", "")) != table_id:
            raise ValueError("KOSIS item metadata response does not match requested table")
        item_name, item_id = str(row.get("ITM_NM", "")).strip(), str(row.get("ITM_ID", "")).strip()
        dimension_name, dimension_id = str(row.get("OBJ_NM", "")).strip(), str(row.get("OBJ_ID", "")).strip()
        if item_name and item_id:
            item_codes[item_name] = item_id
        if dimension_name and dimension_id:
            dimension_ids[dimension_name] = dimension_id
        unit = str(row.get("UNIT_NM", "")).strip()
        if unit and unit not in unit_names:
            unit_names.append(unit)
    return OfficialTableStructure(table_id, item_codes, dimension_ids, unit_names)

def hydrate_candidate(
    candidate: KosisCandidateSchema,
    official_structure: OfficialTableStructure,
) -> KosisCandidateSchema:
    """Apply verified KOSIS ITM metadata without inventing dimension members."""
    if candidate.tbl_id != official_structure.table_id:
        raise ValueError("Official KOSIS metadata table does not match candidate")

    return candidate.model_copy(
        update={
            "core_item_ids": list(official_structure.item_codes.values()),
            "core_item_names": list(official_structure.item_codes),
            "dimension_ids": list(official_structure.dimension_ids.values()),
            "dimension_names": list(official_structure.dimension_ids),
            "unit_names": list(official_structure.unit_names),
            "metadata_status": "OFFICIAL_ITEM_METADATA_READY",
        }
    )