"""Read-only live KOSIS table search for unresolved catalog candidates."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from core.kosis_openapi_transport import _decode_kosis_payload

from schemas.candidate import KosisCandidateSchema

KOSIS_SEARCH_URL = "https://kosis.kr/openapi/statisticsSearch.do"


class KosisLiveCatalogSearch:
    """Query KOSIS integrated search without treating incomplete metadata as evidence."""

    def __init__(
        self,
        api_key: str | None,
        *,
        opener: Callable[..., Any] = urlopen,
        endpoint: str = KOSIS_SEARCH_URL,
    ) -> None:
        self._api_key = api_key
        self._opener = opener
        self._endpoint = endpoint

    def search(self, query: str, *, result_count: int = 20) -> list[KosisCandidateSchema]:
        """Return official table identities; selection metadata remains intentionally unresolved."""
        normalized_query = query.strip()
        if not self._api_key or not normalized_query or result_count <= 0:
            return []
        params = urlencode(
            {
                "method": "getList",
                "apiKey": self._api_key,
                "searchNm": normalized_query,
                "resultCount": min(result_count, 100),
                "format": "json",
            }
        )
        request = Request(f"{self._endpoint}?{params}", headers={"Accept": "application/json", "User-Agent": "CLAFACT-AUTO/0.1"})
        for _attempt in range(2):
            try:
                with self._opener(request, timeout=10) as response:
                    payload = _decode_kosis_payload(response.read())
            except (OSError, UnicodeDecodeError, RuntimeError):
                continue
            rows = payload if isinstance(payload, list) else payload.get("data", []) if isinstance(payload, dict) else []
            if not isinstance(rows, list):
                continue
            candidates = [
                candidate
                for row in rows
                if isinstance(row, dict)
                if (candidate := _candidate_from_row(row)) is not None
            ]
            if candidates:
                return candidates
        return []


def _candidate_from_row(row: dict[str, Any]) -> KosisCandidateSchema | None:
    org_id = str(row.get("ORG_ID", "")).strip()
    table_id = str(row.get("TBL_ID", "")).strip()
    table_name = str(row.get("TBL_NM") or row.get("TBL_NM_META") or "").strip()
    if not org_id or not table_id or not table_name:
        return None
    return KosisCandidateSchema(
        org_id=org_id,
        tbl_id=table_id,
        tbl_name=table_name,
        start_period=_optional_text(row.get("STRT_PRD_DE")),
        end_period=_optional_text(row.get("END_PRD_DE")),
        source_stat_id=_optional_text(row.get("STAT_ID")),
        source_name=_optional_text(row.get("ORG_NM")),
        metadata_status="LIVE_SEARCH_UNRESOLVED",
    )


def _optional_text(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None
