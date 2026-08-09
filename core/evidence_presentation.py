"""Human-readable KOSIS evidence presentation derived from evidence coordinates."""

from __future__ import annotations

from collections.abc import Sequence
from itertools import zip_longest
from urllib.parse import urlencode

from schemas.evidence import EvidenceCellSchema


def build_kosis_table_url(cell: EvidenceCellSchema) -> str:
    """Return a direct KOSIS table URL without embedding credentials."""
    query = urlencode({"orgId": cell.org_id, "tblId": cell.tbl_id, "conn_path": "I2"})
    return f"https://kosis.kr/statHtml/statHtml.do?{query}"


def build_evidence_rows(
    cells: Sequence[EvidenceCellSchema],
    values: Sequence[float],
) -> list[dict[str, str | float | None]]:
    """Pair resolved Evidence Cells with fetched official values for UI rendering."""
    rows: list[dict[str, str | float | None]] = []
    for cell, value in zip_longest(cells, values):
        if cell is None:
            continue
        rows.append(
            {
                "표 ID": cell.tbl_id,
                "항목": cell.itm_id,
                "기간": _display_period(cell.prd_de),
                "KOSIS 공식값": value,
                "단위": cell.unit,
                "좌표": _display_coordinate(cell),
                "KOSIS 원문": build_kosis_table_url(cell),
            }
        )
    return rows


def _display_period(period: str) -> str:
    return f"{period[:4]}-{period[4:6]}" if len(period) == 6 and period.isdigit() else period


def _display_coordinate(cell: EvidenceCellSchema) -> str:
    codes = " | ".join(f"{name}={value}" for name, value in cell.dimension_codes.items())
    return f"ITM={cell.itm_id}" + (f" | {codes}" if codes else "")
