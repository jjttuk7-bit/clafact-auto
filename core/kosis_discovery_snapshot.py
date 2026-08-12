"""Versioned, credential-free KOSIS Catalog and metadata snapshots."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Callable, Protocol

from schemas.evidence import EvidenceCellSchema

from schemas.candidate import KosisCandidateSchema


class CatalogSearch(Protocol):
    def search(self, query: str) -> list[KosisCandidateSchema]: ...


@dataclass
class DiscoverySnapshot:
    dataset_version: str
    catalog_results: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    metadata: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    value_rows: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    @classmethod
    def empty(cls, dataset_version: str) -> "DiscoverySnapshot":
        return cls(dataset_version=dataset_version)

    @classmethod
    def load(cls, path: Path) -> "DiscoverySnapshot":
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            dataset_version=str(payload["dataset_version"]),
            catalog_results=dict(payload.get("catalog_results") or {}),
            metadata=dict(payload.get("metadata") or {}),
            value_rows=dict(payload.get("value_rows") or {}),
        )

    @property
    def content_hash(self) -> str:
        return sha256(self._canonical_json().encode("utf-8")).hexdigest()

    def candidates_for(self, query: str) -> list[KosisCandidateSchema] | None:
        payload = self.catalog_results.get(_query_key(query))
        if payload is None:
            return None
        return [KosisCandidateSchema.model_validate(row) for row in payload]

    def record_candidates(self, query: str, candidates: list[KosisCandidateSchema]) -> None:
        self.catalog_results[_query_key(query)] = [
            candidate.model_dump(mode="json") for candidate in candidates
        ]

    def metadata_for(
        self, org_id: str, table_id: str, *, meta_type: str = "ITM"
    ) -> list[dict[str, Any]] | None:
        typed_key = _metadata_key(org_id, table_id, meta_type)
        payload = self.metadata.get(typed_key)
        if payload is None and meta_type == "ITM":
            payload = self.metadata.get(_table_key(org_id, table_id))
        return None if payload is None else list(payload)

    def record_metadata(
        self, org_id: str, table_id: str, rows: list[dict[str, Any]], *, meta_type: str = "ITM"
    ) -> None:
        self.metadata[_metadata_key(org_id, table_id, meta_type)] = rows

    def value_rows_for(self, canonical_key: str) -> list[dict[str, Any]] | None:
        rows = self.value_rows.get(canonical_key)
        return None if rows is None else list(rows)

    def record_value_rows(self, canonical_key: str, rows: list[dict[str, Any]]) -> None:
        self.value_rows[canonical_key] = rows

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self._canonical_json() + "\n", encoding="utf-8")

    def _canonical_json(self) -> str:
        return json.dumps(
            {
                "dataset_version": self.dataset_version,
                "catalog_results": self.catalog_results,
                "metadata": self.metadata,
                "value_rows": self.value_rows,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )


class SnapshotCatalogSearch:
    """Read frozen candidates first; only an explicit refresh may call KOSIS."""

    def __init__(
        self,
        snapshot: DiscoverySnapshot,
        live_search: CatalogSearch | None,
        *,
        refresh: bool,
    ) -> None:
        self._snapshot = snapshot
        self._live_search = live_search
        self._refresh = refresh
        self._refreshed_queries: set[str] = set()

    def search(self, query: str) -> list[KosisCandidateSchema]:
        if self._refresh and self._live_search is not None:
            query_key = _query_key(query)
            if query_key in self._refreshed_queries:
                return self._snapshot.candidates_for(query) or []
            candidates = self._live_search.search(query)
            self._snapshot.record_candidates(query, candidates)
            self._refreshed_queries.add(query_key)
            return candidates
        frozen = self._snapshot.candidates_for(query)
        if frozen is not None:
            return frozen
        return []


def _query_key(query: str) -> str:
    return " ".join(query.split()).casefold()


def _table_key(org_id: str, table_id: str) -> str:
    return f"{org_id.strip()}|{table_id.strip()}"


def _metadata_key(org_id: str, table_id: str, meta_type: str) -> str:
    return f"{_table_key(org_id, table_id)}|{meta_type.strip().upper()}"


class SnapshotValueLookup:
    """Read frozen official rows first; only explicit refresh may call KOSIS."""

    def __init__(
        self,
        snapshot: DiscoverySnapshot,
        live_lookup: Callable[[EvidenceCellSchema], list[dict[str, Any]]] | None,
        *,
        refresh: bool,
    ) -> None:
        self._snapshot = snapshot
        self._live_lookup = live_lookup
        self._refresh = refresh

    def __call__(self, cell: EvidenceCellSchema) -> list[dict[str, Any]]:
        frozen = self._snapshot.value_rows_for(cell.canonical_key)
        if frozen is not None:
            return frozen
        if not self._refresh or self._live_lookup is None:
            return []
        rows = self._live_lookup(cell)
        self._snapshot.record_value_rows(cell.canonical_key, rows)
        return rows
