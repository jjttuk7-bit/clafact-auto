"""Snapshot-first repository for official KOSIS table metadata."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from threading import Lock, RLock
from typing import Any

from core.kosis_discovery_snapshot import DiscoverySnapshot
from core.kosis_openapi_transport import get_meta

MetadataRow = dict[str, Any]
MetadataFetcher = Callable[..., Mapping[str, Any] | Iterable[Mapping[str, Any]]]


@dataclass(frozen=True, slots=True)
class MetadataSnapshotSource:
    path: Path
    version: str | None = None
    content_sha256: str | None = None


class KosisMetadataRepository:
    """Reuse versioned official metadata before making a bounded live request.

    Credentials are deliberately excluded from the coordinate cache key. KOSIS
    metadata is public table structure; the key only authorizes transport.
    """

    def __init__(
        self,
        snapshot_paths: Iterable[Path],
        *,
        live_fetcher: MetadataFetcher = get_meta,
    ) -> None:
        self._snapshot_paths = tuple(Path(path) for path in snapshot_paths)
        self._snapshot_sources = tuple(
            MetadataSnapshotSource(path) for path in self._snapshot_paths
        )
        self._live_fetcher = live_fetcher
        self._snapshots: tuple[DiscoverySnapshot, ...] | None = None
        self._cache: dict[tuple[str, str, str], list[MetadataRow]] = {}
        self._lock = RLock()
        self._coordinate_locks: dict[tuple[str, str, str], Lock] = {}

    @classmethod
    def from_manifests(
        cls,
        manifest_paths: Iterable[Path],
        *,
        live_fetcher: MetadataFetcher = get_meta,
    ) -> "KosisMetadataRepository":
        repository = cls([], live_fetcher=live_fetcher)
        sources: list[MetadataSnapshotSource] = []
        for manifest_path in manifest_paths:
            path = Path(manifest_path)
            payload = json.loads(path.read_text(encoding="utf-8"))
            version = str(payload.get("metadata_snapshot_version", "")).strip()
            content_hash = str(payload.get("content_sha256", "")).strip().casefold()
            relative_path = str(payload.get("snapshot_path", "")).strip()
            if not version or version.casefold() == "unversioned":
                raise RuntimeError("KOSIS_METADATA_SNAPSHOT_VERSION_REQUIRED")
            if not relative_path or len(content_hash) != 64:
                raise RuntimeError("KOSIS_METADATA_SNAPSHOT_MANIFEST_INVALID")
            sources.append(MetadataSnapshotSource(
                path=(path.parent / relative_path).resolve(),
                version=version,
                content_sha256=content_hash,
            ))
        repository._snapshot_sources = tuple(sources)
        repository._snapshot_paths = tuple(source.path for source in sources)
        return repository

    def __call__(
        self,
        api_key: str,
        org_id: str,
        table_id: str,
        *,
        meta_type: str = "ITM",
        **kwargs: Any,
    ) -> list[MetadataRow]:
        coordinate = (
            org_id.strip(),
            table_id.strip(),
            meta_type.strip().upper(),
        )
        with self._lock:
            cached = self._cache.get(coordinate)
            if cached is not None:
                return [dict(row) for row in cached]
            coordinate_lock = self._coordinate_locks.setdefault(coordinate, Lock())

        with coordinate_lock:
            with self._lock:
                cached = self._cache.get(coordinate)
                if cached is not None:
                    return [dict(row) for row in cached]
                frozen = self._from_snapshots(*coordinate)
                if frozen is not None:
                    self._cache[coordinate] = frozen
                    return [dict(row) for row in frozen]

            result = self._live_fetcher(
                api_key,
                coordinate[0],
                coordinate[1],
                meta_type=coordinate[2],
                **kwargs,
            )
            rows = _materialize_rows(result)
            _validate_metadata_rows(rows, table_id=coordinate[1], meta_type=coordinate[2])
            with self._lock:
                self._cache[coordinate] = rows
            return [dict(row) for row in rows]

    def _from_snapshots(
        self, org_id: str, table_id: str, meta_type: str
    ) -> list[MetadataRow] | None:
        for snapshot in self._loaded_snapshots():
            rows = snapshot.metadata_for(org_id, table_id, meta_type=meta_type)
            if rows is not None:
                return [dict(row) for row in rows]
        return None

    def _loaded_snapshots(self) -> tuple[DiscoverySnapshot, ...]:
        if self._snapshots is None:
            loaded: list[DiscoverySnapshot] = []
            for source in self._snapshot_sources:
                if not source.path.is_file():
                    continue
                if source.content_sha256 is not None:
                    actual = sha256(source.path.read_bytes()).hexdigest()
                    if actual != source.content_sha256:
                        raise RuntimeError("KOSIS_METADATA_SNAPSHOT_HASH_MISMATCH")
                snapshot = DiscoverySnapshot.load(source.path)
                if (
                    source.version is not None
                    and snapshot.dataset_version != source.version
                ):
                    raise RuntimeError("KOSIS_METADATA_SNAPSHOT_VERSION_MISMATCH")
                loaded.append(snapshot)
            self._snapshots = tuple(loaded)
        return self._snapshots


def _materialize_rows(
    result: Mapping[str, Any] | Iterable[Mapping[str, Any]],
) -> list[MetadataRow]:
    if isinstance(result, Mapping):
        return [dict(result)]
    return [dict(row) for row in result]


def _validate_metadata_rows(
    rows: list[MetadataRow], *, table_id: str, meta_type: str
) -> None:
    for row in rows:
        if "err" in row or "error" in row or "errMsg" in row:
            raise RuntimeError("KOSIS_METADATA_API_ERROR")
    if meta_type == "ITM" and any(
        not str(row.get("ITM_ID", "")).strip()
        or str(row.get("TBL_ID", "")).strip() != table_id
        for row in rows
    ):
        raise RuntimeError("KOSIS_METADATA_INVALID_RESPONSE")
    if meta_type == "PRD" and any(
        not str(row.get("PRD_SE", "")).strip() for row in rows
    ):
        raise RuntimeError("KOSIS_METADATA_INVALID_RESPONSE")
