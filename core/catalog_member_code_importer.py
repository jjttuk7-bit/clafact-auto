"""Importer for externally exported KOSIS member-code metadata."""

from __future__ import annotations

import json
from pathlib import Path

from core.member_code_mapper import build_member_code_map


def import_member_codes(source: Path) -> dict[str, dict[str, dict[str, str]]]:
    """Read a JSON list of table/dimension/member records without inferring missing codes."""
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("KOSIS_MEMBER_EXPORT_INVALID")
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in payload:
        if not isinstance(row, dict) or not isinstance(row.get("tbl_id"), str):
            raise ValueError("KOSIS_MEMBER_EXPORT_INVALID")
        grouped.setdefault(row["tbl_id"], []).append(row)
    return {table_id: build_member_code_map(rows) for table_id, rows in grouped.items()}
