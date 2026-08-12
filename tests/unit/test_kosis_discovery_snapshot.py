from pathlib import Path

from core.kosis_discovery_snapshot import DiscoverySnapshot, SnapshotCatalogSearch
from schemas.candidate import KosisCandidateSchema


def _candidate() -> KosisCandidateSchema:
    return KosisCandidateSchema(
        org_id="101", tbl_id="DT_EMP", tbl_name="취업자 수", metadata_status="LIVE_SEARCH_UNRESOLVED"
    )


def test_snapshot_reuses_frozen_catalog_and_metadata_without_network(tmp_path: Path) -> None:
    snapshot = DiscoverySnapshot.empty("gold-v1")
    calls: list[str] = []

    class LiveSearch:
        def search(self, query: str) -> list[KosisCandidateSchema]:
            calls.append(query)
            return [_candidate()]

    collector = SnapshotCatalogSearch(snapshot, LiveSearch(), refresh=True)
    assert collector.search("취업자 수") == [_candidate()]
    snapshot.record_metadata("101", "DT_EMP", [{"ITM_ID": "T30", "ITM_NM": "취업자"}])
    path = tmp_path / "kosis_discovery_snapshot.json"
    snapshot.write(path)

    frozen = DiscoverySnapshot.load(path)
    offline = SnapshotCatalogSearch(frozen, None, refresh=False)
    assert offline.search("취업자 수") == [_candidate()]
    assert frozen.metadata_for("101", "DT_EMP") == [{"ITM_ID": "T30", "ITM_NM": "취업자"}]
    assert calls == ["취업자 수"]
    assert frozen.content_hash == snapshot.content_hash


def test_snapshot_reuses_frozen_official_value_rows_without_network() -> None:
    from core.kosis_discovery_snapshot import SnapshotValueLookup
    from schemas.evidence import EvidenceCellSchema

    snapshot = DiscoverySnapshot.empty("gold-v1")
    cell = EvidenceCellSchema(org_id="101", tbl_id="DT_EMP", itm_id="T30", prd_se="M", prd_de="202412", canonical_key="DT_EMP|T30|202412", status="CONFIRMED")
    snapshot.record_value_rows(cell.canonical_key, [{"TBL_ID": "DT_EMP", "ITM_ID": "T30", "PRD_DE": "202412", "DT": "28041"}])

    lookup = SnapshotValueLookup(snapshot, None, refresh=False)
    assert lookup(cell) == [{"TBL_ID": "DT_EMP", "ITM_ID": "T30", "PRD_DE": "202412", "DT": "28041"}]



def test_snapshot_refresh_replaces_existing_catalog_result() -> None:
    snapshot = DiscoverySnapshot.empty("gold-v1")
    snapshot.record_candidates("취업자 수", [_candidate()])
    replacement = _candidate().model_copy(update={"tbl_id": "DT_NEW"})

    class LiveSearch:
        def search(self, _query: str) -> list[KosisCandidateSchema]:
            return [replacement]

    refreshed = SnapshotCatalogSearch(snapshot, LiveSearch(), refresh=True)
    assert refreshed.search("취업자 수") == [replacement]
    assert snapshot.candidates_for("취업자 수") == [replacement]


def test_snapshot_refresh_reuses_first_live_result_for_a_repeated_query() -> None:
    """A transient empty response must not erase a batch's earlier discovery."""
    snapshot = DiscoverySnapshot.empty("gold-v1")
    calls = 0

    class LiveSearch:
        def search(self, _query: str) -> list[KosisCandidateSchema]:
            nonlocal calls
            calls += 1
            return [_candidate()] if calls == 1 else []

    refreshed = SnapshotCatalogSearch(snapshot, LiveSearch(), refresh=True)
    assert refreshed.search("취업자 수") == [_candidate()]
    assert refreshed.search("취업자 수") == [_candidate()]
    assert calls == 1


def test_snapshot_keeps_item_and_period_metadata_separate() -> None:
    snapshot = DiscoverySnapshot.empty("gold-v1")
    snapshot.record_metadata("101", "DT", [{"ITM_ID": "T"}], meta_type="ITM")
    snapshot.record_metadata("101", "DT", [{"PRD_SE": "월"}], meta_type="PRD")

    assert snapshot.metadata_for("101", "DT", meta_type="ITM") == [{"ITM_ID": "T"}]
    assert snapshot.metadata_for("101", "DT", meta_type="PRD") == [{"PRD_SE": "월"}]
