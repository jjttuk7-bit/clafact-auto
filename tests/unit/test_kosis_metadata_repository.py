from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
from time import monotonic, sleep

import pytest

from core.kosis_discovery_snapshot import DiscoverySnapshot
from core.kosis_metadata_repository import KosisMetadataRepository


def _canonical_hash(path: Path) -> str:
    return sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()

def _snapshot(path: Path) -> None:
    snapshot = DiscoverySnapshot.empty("official-metadata-v1")
    snapshot.record_metadata(
        "360",
        "DT_EXPORT",
        [
            {
                "ORG_ID": "360",
                "TBL_ID": "DT_EXPORT",
                "OBJ_ID": "ITEM",
                "OBJ_NM": "항목",
                "ITM_ID": "T1",
                "ITM_NM": "수출액",
                "UNIT_NM": "천달러",
            },
            {
                "ORG_ID": "360",
                "TBL_ID": "DT_EXPORT",
                "OBJ_ID": "C1",
                "OBJ_NM": "품목별",
                "ITM_ID": "781",
                "ITM_NM": "승용자동차 및 기타의 차량",
            },
        ],
    )
    snapshot.record_metadata(
        "360",
        "DT_EXPORT",
        [{"PRD_SE": "분기", "STRT_PRD_DE": "2000 1/4", "END_PRD_DE": "2026 2/4"}],
        meta_type="PRD",
    )
    snapshot.write(path)


def test_repository_reads_official_snapshot_before_live_transport(tmp_path: Path) -> None:
    path = tmp_path / "official.json"
    _snapshot(path)
    calls: list[str] = []

    def live(*_args, **kwargs):
        calls.append(str(kwargs.get("meta_type")))
        return []

    repository = KosisMetadataRepository([path], live_fetcher=live)

    rows = repository("secret", "360", "DT_EXPORT", meta_type="ITM")
    period_rows = repository("secret", "360", "DT_EXPORT", meta_type="PRD")

    assert rows[1]["ITM_ID"] == "781"
    assert period_rows[0]["PRD_SE"] == "분기"
    assert calls == []


def test_repository_finds_snapshot_table_identity_for_concept_member_code(tmp_path: Path) -> None:
    path = tmp_path / "official.json"
    _snapshot(path)

    repository = KosisMetadataRepository([path])

    assert repository.table_identities_for_member_code("781") == [("360", "DT_EXPORT")]
    assert repository.table_identities_for_member_code("missing") == []

def test_repository_caches_one_live_response_per_official_coordinate() -> None:
    calls: list[tuple[str, str, str]] = []

    def live(api_key, org_id, table_id, *, meta_type, **_kwargs):
        assert api_key == "secret"
        calls.append((org_id, table_id, meta_type))
        return [{"TBL_ID": table_id, "ITM_ID": "T"}]

    repository = KosisMetadataRepository([], live_fetcher=live)

    first = repository("secret", "101", "DT_NEW", meta_type="ITM", retries=1)
    second = repository("different-secret", "101", "DT_NEW", meta_type="ITM", retries=3)

    assert first == second
    assert calls == [("101", "DT_NEW", "ITM")]


def test_repository_keeps_metadata_types_in_separate_cache_entries() -> None:
    calls: list[str] = []

    def live(_api_key, _org_id, table_id, *, meta_type, **_kwargs):
        calls.append(meta_type)
        if meta_type == "ITM":
            return [{"TYPE": meta_type, "TBL_ID": table_id, "ITM_ID": "T"}]
        return [{"TYPE": meta_type, "PRD_SE": "년"}]

    repository = KosisMetadataRepository([], live_fetcher=live)

    assert repository("secret", "101", "DT", meta_type="ITM")[0]["TYPE"] == "ITM"
    assert repository("secret", "101", "DT", meta_type="PRD")[0]["TYPE"] == "PRD"
    assert calls == ["ITM", "PRD"]


def test_repository_does_not_serialize_different_live_coordinates() -> None:
    def live(_api_key, _org_id, table_id, **_kwargs):
        sleep(0.2)
        return [{"TBL_ID": table_id, "ITM_ID": "T"}]

    repository = KosisMetadataRepository([], live_fetcher=live)
    started = monotonic()
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(
            lambda table_id: repository("secret", "101", table_id),
            ("DT_A", "DT_B"),
        ))

    assert monotonic() - started < 0.35
    assert [result[0]["TBL_ID"] for result in results] == ["DT_A", "DT_B"]


def test_repository_never_caches_kosis_error_payload() -> None:
    calls = 0

    def live(_api_key, _org_id, table_id, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"err": "10", "errMsg": "temporary"}
        return [{"TBL_ID": table_id, "ITM_ID": "T"}]

    repository = KosisMetadataRepository([], live_fetcher=live)

    with pytest.raises(RuntimeError, match="KOSIS_METADATA_API_ERROR"):
        repository("secret", "101", "DT")
    assert repository("secret", "101", "DT") == [{"TBL_ID": "DT", "ITM_ID": "T"}]
    assert calls == 2


def test_repository_rejects_manifest_hash_mismatch(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "official.json"
    _snapshot(snapshot_path)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({
        "metadata_snapshot_version": "official-metadata-v1",
        "snapshot_path": snapshot_path.name,
        "content_sha256": "0" * 64,
    }), encoding="utf-8")

    repository = KosisMetadataRepository.from_manifests([manifest_path])

    with pytest.raises(RuntimeError, match="KOSIS_METADATA_SNAPSHOT_HASH_MISMATCH"):
        repository("secret", "360", "DT_EXPORT")


def test_repository_accepts_versioned_hash_verified_manifest(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "official.json"
    _snapshot(snapshot_path)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({
        "metadata_snapshot_version": "official-metadata-v1",
        "snapshot_path": snapshot_path.name,
        "content_sha256": _canonical_hash(snapshot_path),
    }), encoding="utf-8")

    repository = KosisMetadataRepository.from_manifests([manifest_path])

    assert repository("secret", "360", "DT_EXPORT")[1]["ITM_ID"] == "781"


def test_repository_accepts_canonical_lf_hash_for_crlf_checkout(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "official.json"
    _snapshot(snapshot_path)
    canonical = snapshot_path.read_bytes().replace(b"\r\n", b"\n").rstrip(b"\n") + b"\n"
    snapshot_path.write_bytes(canonical.replace(b"\n", b"\r\n"))
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({
        "metadata_snapshot_version": "official-metadata-v1",
        "snapshot_path": snapshot_path.name,
        "content_sha256": sha256(canonical).hexdigest(),
    }), encoding="utf-8")

    repository = KosisMetadataRepository.from_manifests([manifest_path])

    assert repository("secret", "360", "DT_EXPORT")[1]["ITM_ID"] == "781"

def test_repository_rejects_snapshot_internal_version_mismatch(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "official.json"
    _snapshot(snapshot_path)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({
        "metadata_snapshot_version": "different-version",
        "snapshot_path": snapshot_path.name,
        "content_sha256": _canonical_hash(snapshot_path),
    }), encoding="utf-8")

    repository = KosisMetadataRepository.from_manifests([manifest_path])

    with pytest.raises(RuntimeError, match="KOSIS_METADATA_SNAPSHOT_VERSION_MISMATCH"):
        repository("secret", "360", "DT_EXPORT")

def test_repository_finds_official_table_identity_by_member_code(tmp_path: Path) -> None:
    from core.kosis_metadata_repository import KosisMetadataRepository

    snapshot_path = tmp_path / "metadata.json"
    snapshot_path.write_text(
        json.dumps({
            "dataset_version": "v1", "metadata": {
                "101|DT_CPI|ITM": [
                    {"TBL_ID": "DT_CPI", "OBJ_ID": "I", "ITM_ID": "A02A01701", "ITM_NM": "배추"}
                ]
            }
        }),
        encoding="utf-8",
    )

    repository = KosisMetadataRepository([snapshot_path])

    assert repository.table_identities_for_member_code("A02A01701") == [("101", "DT_CPI")]
