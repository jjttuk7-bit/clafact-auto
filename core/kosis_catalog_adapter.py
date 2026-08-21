"""Read-only adapter boundary for KOSIS table metadata."""

from collections.abc import Callable, Iterable
from dataclasses import replace
import re
from typing import Mapping
from core import kosis_catalog_adapter_v2_impl as _impl
from core.kosis_catalog_adapter_v2_impl import KosisCatalogAdapter, OfficialTableStructure, hydrate_candidate
from schemas.candidate import KosisCandidateSchema

__all__ = ["KosisCatalogAdapter", "OfficialTableStructure", "normalize_item_metadata", "hydrate_candidate", "hydrate_candidates_from_official_metadata"]


def normalize_item_metadata(rows: Iterable[Mapping[str, object]], *, table_id: str) -> OfficialTableStructure:
    materialized = list(rows)
    structure = _impl.normalize_item_metadata(materialized, table_id=table_id)
    units = list(structure.unit_names)
    item_units = dict(structure.item_units)
    for row in materialized:
        if str(row.get("OBJ_ID", "")) != "ITEM" or str(row.get("UNIT_NM", "")).strip():
            continue
        name = str(row.get("ITM_NM", "")).strip()
        match = re.search(r"\(\s*(%|％|명|천명|만명|건|개|호|가구|원|천원|만원|ha|㏊|헥타르)\s*\)\s*$", name, re.IGNORECASE)
        if match:
            unit = match.group(1).replace("％", "%")
            item_id = str(row.get("ITM_ID", "")).strip()
            item_units[item_id] = unit
            if unit not in units:
                units.append(unit)
    return replace(structure, unit_names=units, item_units=item_units)


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
