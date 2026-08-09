"""Adapter from a complete EvidenceCell coordinate to the KOSIS value API."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from core.kosis_value_transport import get_parameter_data
from schemas.evidence import EvidenceCellSchema

_FREQUENCY = {"월": "M", "monthly": "M", "month": "M", "년": "Y", "year": "Y", "yearly": "Y", "annual": "Y", "분기": "Q"}


def build_kosis_api_lookup(api_key: str) -> Callable[[EvidenceCellSchema], list[dict[str, Any]]]:
    """Return a read-only lookup that rejects incomplete C1~C8 coordinates."""
    def lookup(cell: EvidenceCellSchema) -> list[dict[str, Any]]:
        object_codes = _ordered_codes(cell)
        if not object_codes:
            raise ValueError("KOSIS_COORDINATE_CODES_REQUIRED")
        period_type = _FREQUENCY.get(cell.prd_se.casefold(), cell.prd_se)
        period = cell.prd_de.replace("-", "")
        return get_parameter_data(api_key, cell.org_id, cell.tbl_id, cell.itm_id, period_type, period, period, object_codes)
    return lookup


def _ordered_codes(cell: EvidenceCellSchema) -> list[str]:
    codes: list[str] = []
    for index in range(1, 9):
        code = cell.dimension_codes.get(f"C{index}")
        if code is None:
            break
        codes.append(code)
    return codes
