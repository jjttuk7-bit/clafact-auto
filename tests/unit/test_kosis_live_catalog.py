from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

from core.hard_guard import apply_hard_guard
from core.kosis_live_catalog import KosisLiveCatalogSearch
from schemas.claim import ClaimSchema


class _Response:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_: object) -> None:
        return None


def test_live_catalog_search_maps_official_table_result() -> None:
    seen: list[str] = []

    def opener(request: object, *, timeout: float) -> _Response:
        seen.append(request.full_url)  # type: ignore[attr-defined]
        return _Response([{"ORG_ID": "101", "TBL_ID": "DT_1J22042", "TBL_NM": "소비자물가지수"}])

    candidates = KosisLiveCatalogSearch("secret", opener=opener).search("소비자 물가")

    assert [(item.org_id, item.tbl_id, item.tbl_name) for item in candidates] == [("101", "DT_1J22042", "소비자물가지수")]
    assert candidates[0].metadata_status == "LIVE_SEARCH_UNRESOLVED"
    params = parse_qs(urlparse(seen[0]).query)
    assert params["method"] == ["getList"]
    assert params["searchNm"] == ["소비자 물가"]
    assert params["apiKey"] == ["secret"]


def test_live_catalog_search_returns_empty_for_missing_key() -> None:
    assert KosisLiveCatalogSearch(None).search("소비자물가") == []


def test_hard_guard_rejects_live_candidate_without_coordinate_metadata() -> None:
    candidate = KosisLiveCatalogSearch("secret", opener=lambda *_, **__: _Response([{"ORG_ID": "101", "TBL_ID": "DT_X", "TBL_NM": "소비자물가지수"}])).search("소비자물가")[0]
    claim = ClaimSchema(claim_id="c1", source_sentence="소비자 물가는 2.4% 올랐다.", indicator="소비자 물가", value=2.4, unit="%", parse_status="AUTO_OK")

    guard = apply_hard_guard(claim, candidate)

    assert guard.passed is False
    assert guard.reject_codes == ["METADATA_INCOMPLETE"]


def test_live_catalog_search_parses_kosis_legacy_unquoted_json() -> None:
    class LegacyResponse:
        def read(self) -> bytes:
            return '[{ORG_ID:"122",ORG_NM:"산업통상자원부",TBL_ID:"DT_TRADE",TBL_NM:"수출액"}]'.encode("utf-8")

        def __enter__(self) -> "LegacyResponse":
            return self

        def __exit__(self, *_: object) -> None:
            return None

    candidates = KosisLiveCatalogSearch(
        "secret", opener=lambda *_, **__: LegacyResponse()
    ).search("수출액")

    assert [(item.org_id, item.tbl_id, item.tbl_name) for item in candidates] == [
        ("122", "DT_TRADE", "수출액")
    ]
