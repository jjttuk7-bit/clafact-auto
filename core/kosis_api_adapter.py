"""Adapter from a complete EvidenceCell coordinate to the KOSIS value API."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from core.kosis_value_transport import get_parameter_data
from schemas.evidence import EvidenceCellSchema

_FREQUENCY = {"월": "M", "monthly": "M", "month": "M", "년": "Y", "year": "Y", "yearly": "Y", "annual": "Y", "분기": "Q"}


class KosisApiLookup:
    """Read one coordinate or a period range through the official Parameter API."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def __call__(self, cell: EvidenceCellSchema) -> list[dict[str, Any]]:
        return self.fetch_many([cell])

    def fetch_many(self, cells: Sequence[EvidenceCellSchema]) -> list[dict[str, Any]]:
        if not cells:
            return []
        first = cells[0]
        coordinate = (
            first.org_id, first.tbl_id, first.itm_id, first.prd_se,
            tuple(_ordered_codes(first)),
        )
        if not coordinate[-1]:
            raise ValueError("KOSIS_COORDINATE_CODES_REQUIRED")
        if any(
            (
                cell.org_id, cell.tbl_id, cell.itm_id, cell.prd_se,
                tuple(_ordered_codes(cell)),
            ) != coordinate
            for cell in cells[1:]
        ):
            raise ValueError("KOSIS_RANGE_COORDINATE_MISMATCH")
        periods = sorted(cell.prd_de.replace("-", "") for cell in cells)
        period_type = _FREQUENCY.get(first.prd_se.casefold(), first.prd_se)
        return get_parameter_data(
            self._api_key, first.org_id, first.tbl_id, first.itm_id,
            period_type, periods[0], periods[-1], list(coordinate[-1]),
        )


def build_kosis_api_lookup(api_key: str) -> KosisApiLookup:
    """Return a read-only lookup that rejects incomplete C1~C8 coordinates."""
    return KosisApiLookup(api_key)


def _ordered_codes(cell: EvidenceCellSchema) -> list[str]:
    codes: list[str] = []
    for index in range(1, 9):
        code = cell.dimension_codes.get(f"C{index}")
        if code is None:
            break
        codes.append(code)
    if codes:
        return codes
    return list(cell.dimension_codes.values())
