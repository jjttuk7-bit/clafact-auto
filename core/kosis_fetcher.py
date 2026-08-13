"""Official KOSIS value access through immutable snapshots or explicit API rows."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal

from core.snapshot_asof import filter_rows_as_of
from schemas.evidence import EvidenceCellSchema

ValueStatus = Literal["SUCCESS", "NO_DATA", "INVALID_RESPONSE", "AS_OF_UNAVAILABLE", "FETCH_FAILED"]


@dataclass(frozen=True, slots=True)
class KosisValue:
    value: float | None
    status: ValueStatus
    snapshot_hash: str
    source: Literal["SNAPSHOT", "API", "NONE"] = "SNAPSHOT"


def fetch_kosis_value(cell: EvidenceCellSchema, snapshot_path: Path) -> KosisValue:
    """Read an official value from a legacy flat snapshot; never synthesize one."""
    raw = snapshot_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    try:
        payload = json.loads(raw)
        value = payload.get(cell.canonical_key)
    except (json.JSONDecodeError, AttributeError):
        return KosisValue(None, "INVALID_RESPONSE", digest)
    if value is None:
        return KosisValue(None, "NO_DATA", digest)
    if not isinstance(value, (int, float)):
        return KosisValue(None, "INVALID_RESPONSE", digest)
    return KosisValue(float(value), "SUCCESS", digest)


class OfficialValueFetcher:
    """Prefer auditable local snapshots, then use an injected read-only KOSIS API adapter."""

    def __init__(self, snapshot_paths: Iterable[Path], api_lookup: Callable[[EvidenceCellSchema], list[dict[str, Any]]] | None = None, *, prefer_api: bool = False) -> None:
        self._snapshot_paths = list(snapshot_paths)
        self._api_lookup = api_lookup
        self._prefer_api = prefer_api

    def fetch(self, cell: EvidenceCellSchema, *, article_date: date | None = None) -> KosisValue:
        as_of_unavailable = False
        fetch_failed = False
        if self._prefer_api:
            api_result = self._fetch_api(cell, article_date)
            if api_result is not None and api_result.status == "SUCCESS":
                return api_result
            as_of_unavailable = bool(api_result and api_result.status == "AS_OF_UNAVAILABLE")
            fetch_failed = bool(api_result and api_result.status == "FETCH_FAILED")
        for path in self._snapshot_paths:
            result = self._fetch_snapshot(cell, path, article_date)
            if result.status == "SUCCESS":
                return result
            as_of_unavailable = as_of_unavailable or result.status == "AS_OF_UNAVAILABLE"
            fetch_failed = fetch_failed or result.status == "FETCH_FAILED"
        if not self._prefer_api:
            api_result = self._fetch_api(cell, article_date)
            if api_result is not None and api_result.status in {"SUCCESS", "AS_OF_UNAVAILABLE"}:
                return api_result
            fetch_failed = fetch_failed or bool(
                api_result and api_result.status == "FETCH_FAILED"
            )
        status: ValueStatus = (
            "AS_OF_UNAVAILABLE" if as_of_unavailable
            else "FETCH_FAILED" if fetch_failed
            else "NO_DATA"
        )
        return KosisValue(None, status, "", "NONE")

    def _fetch_api(self, cell: EvidenceCellSchema, article_date: date | None) -> KosisValue | None:
        if self._api_lookup is None:
            return None
        try:
            rows = self._api_lookup(cell)
        except Exception:
            return KosisValue(None, "FETCH_FAILED", "", "NONE")
        digest = hashlib.sha256(
            json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return self._extract_rows(cell, rows, article_date, source="API", digest=digest)

    def _fetch_snapshot(self, cell: EvidenceCellSchema, path: Path, article_date: date | None) -> KosisValue:
        try:
            raw = path.read_bytes()
        except OSError:
            return KosisValue(None, "FETCH_FAILED", "", "NONE")
        digest = hashlib.sha256(raw).hexdigest()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return KosisValue(None, "INVALID_RESPONSE", digest)
        if isinstance(payload, dict) and cell.canonical_key in payload:
            return fetch_kosis_value(cell, path)
        if not isinstance(payload, dict):
            return KosisValue(None, "INVALID_RESPONSE", digest)
        records = payload.get("records", payload.get("response"))
        if not isinstance(records, list):
            return KosisValue(None, "NO_DATA", digest)
        if payload.get("tbl_id") and payload.get("tbl_id") != cell.tbl_id:
            return KosisValue(None, "NO_DATA", digest)
        if payload.get("item_id") and payload.get("item_id") != cell.itm_id:
            return KosisValue(None, "NO_DATA", digest)
        published_at = payload.get("source_published_at")
        inherited_records = [
            {
                **row,
                **(
                    {"source_published_at": published_at}
                    if published_at and "source_published_at" not in row
                    else {}
                ),
            }
            for row in records
            if isinstance(row, dict)
        ]
        return self._extract_rows(cell, inherited_records, article_date, source="SNAPSHOT", digest=digest)

    def _extract_rows(self, cell: EvidenceCellSchema, rows: list[dict[str, Any]], article_date: date | None, *, source: Literal["SNAPSHOT", "API"], digest: str) -> KosisValue:
        matching = [row for row in rows if _matches_cell(row, cell, allow_missing_codes=source == "API")]
        if not matching:
            return KosisValue(None, "NO_DATA", digest, source)
        usable = filter_rows_as_of(matching, article_date) if article_date else matching
        if article_date and not usable:
            return KosisValue(None, "AS_OF_UNAVAILABLE", digest, source)
        value = usable[0].get("value", usable[0].get("DT"))
        try:
            return KosisValue(float(value), "SUCCESS", digest, source)
        except (TypeError, ValueError):
            return KosisValue(None, "INVALID_RESPONSE", digest, source)


def _matches_cell(row: dict[str, Any], cell: EvidenceCellSchema, *, allow_missing_codes: bool = False) -> bool:
    table = row.get("tbl_id", row.get("TBL_ID"))
    item = row.get("item_id", row.get("ITM_ID"))
    period = str(row.get("period", row.get("PRD_DE", ""))).replace("-", "")
    expected_period = cell.prd_de.replace("-", "")
    codes = row.get("dimension_codes")
    if not isinstance(codes, dict):
        codes = {key: row.get(key) for key in cell.dimension_codes}
    has_returned_codes = any(value is not None for value in codes.values())
    codes_match = (
        not cell.dimension_codes
        or (allow_missing_codes and not has_returned_codes)
        or all(codes.get(key) == value for key, value in cell.dimension_codes.items())
    )
    return (table in (None, cell.tbl_id) and item in (None, cell.itm_id) and period == expected_period and codes_match)


