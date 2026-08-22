from __future__ import annotations

import json

from core.kosis_live_catalog import KosisLiveCatalogSearch


class _Response:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def test_shared_live_catalog_cache_avoids_duplicate_official_query() -> None:
    calls = 0
    shared_cache: dict[str, object] = {}

    def opener(_request: object, *, timeout: float) -> _Response:
        nonlocal calls
        calls += 1
        return _Response([
            {"ORG_ID": "101", "TBL_ID": "DT_EMP", "TBL_NM": "취업자 수"}
        ])

    primary = KosisLiveCatalogSearch(
        "secret", opener=opener, result_cache=shared_cache
    )
    auxiliary = KosisLiveCatalogSearch(
        "secret", opener=opener, result_cache=shared_cache
    )

    first = primary.search("취업자 수")
    second = auxiliary.search("취업자 수")

    assert [item.tbl_id for item in first] == ["DT_EMP"]
    assert [item.tbl_id for item in second] == ["DT_EMP"]
    assert calls == 1
    assert primary.attempted_queries == 1
    assert auxiliary.attempted_queries == 0
    assert auxiliary.cache_hits == 1
