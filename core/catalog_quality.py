"""Read-only quality inspection for the normalized KOSIS semantic catalog."""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

_MOJIBAKE = re.compile(r"[ìëê][\x80-\xbf]")


@dataclass(frozen=True, slots=True)
class CatalogQualityReport:
    total_records: int
    ready_records: int
    encoding_suspect_table_ids: list[str]
    duplicate_table_ids: list[str]
    missing_core_item_table_ids: list[str]
    invalid_dimension_json_table_ids: list[str]


def inspect_catalog_records(records: Iterable[Mapping[str, object]]) -> CatalogQualityReport:
    """Report catalog issues without mutating source metadata."""
    rows = list(records)
    table_ids = [str(row.get("TBL_ID", "")).strip() for row in rows]
    duplicates = sorted(table_id for table_id, count in Counter(table_ids).items() if table_id and count > 1)
    encoding_suspects: set[str] = set()
    missing_core_items: set[str] = set()
    invalid_dimensions: set[str] = set()
    ready_ids: set[str] = set()
    for row, table_id in zip(rows, table_ids, strict=True):
        metadata_text = " ".join(str(row.get(field, "")) for field in ("TBL_NM_META", "TBL_NM_INPUT", "CORE_ITEM_NAMES", "DIMENSION_NAMES", "SOURCE_JOSA_NM"))
        if _MOJIBAKE.search(metadata_text):
            encoding_suspects.add(table_id)
        if not str(row.get("CORE_ITEM_IDS", "")).strip() or not str(row.get("CORE_ITEM_NAMES", "")).strip():
            missing_core_items.add(table_id)
        if not _valid_dimension_json(row.get("DIMENSION_MEMBERS_JSON", {})):
            invalid_dimensions.add(table_id)
        if (
            table_id
            and str(row.get("semantic_core_status", "")).startswith("STRUCTURAL_READY")
            and table_id not in encoding_suspects
            and table_id not in missing_core_items
            and table_id not in invalid_dimensions
        ):
            ready_ids.add(table_id)
    return CatalogQualityReport(
        total_records=len(rows),
        ready_records=len(ready_ids),
        encoding_suspect_table_ids=sorted(table_id for table_id in encoding_suspects if table_id),
        duplicate_table_ids=duplicates,
        missing_core_item_table_ids=sorted(table_id for table_id in missing_core_items if table_id),
        invalid_dimension_json_table_ids=sorted(table_id for table_id in invalid_dimensions if table_id),
    )


def _valid_dimension_json(value: object) -> bool:
    if value in (None, ""):
        return True
    try:
        decoded = json.loads(value) if isinstance(value, str) else value
    except json.JSONDecodeError:
        return False
    return isinstance(decoded, dict)