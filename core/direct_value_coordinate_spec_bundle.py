"""Build the complete source-grounded query-spec bundle for direct-value Claims."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Iterable, Mapping

from core.direct_value_coordinate_spec_preparation import prepare_coordinate_spec
from core.direct_value_coordinate_spec_registry import ledger_row_to_registry
from core.direct_value_coordinate_spec_scope import (
    CoordinateSpecScope,
    build_coordinate_spec_scope,
)
from schemas.claim_registry import ClaimRegistryRecord
from schemas.kosis_query_spec import KosisQuerySpecSchema


@dataclass(frozen=True, slots=True)
class DirectValueCoordinateSpecBundle:
    scope: CoordinateSpecScope
    specs: tuple[KosisQuerySpecSchema, ...]
    ready_records: tuple[ClaimRegistryRecord, ...]
    preverification_specs: tuple[KosisQuerySpecSchema, ...]
    readiness_counts: dict[str, int]
    manifest_sha256: str


def build_coordinate_spec_bundle(
    rows: Iterable[Mapping[str, object]],
    *,
    expected_count: int = 176,
) -> DirectValueCoordinateSpecBundle:
    ledger = list(rows)
    scope = build_coordinate_spec_scope(ledger, expected_count=expected_count)
    by_id: dict[str, Mapping[str, object]] = {}
    for row in ledger:
        claim_id = _text(row.get("자식Claim번호")) or _text(row.get("원본부모Claim번호"))
        if claim_id:
            if claim_id in by_id:
                raise ValueError(f"DIRECT_VALUE_LEDGER_CLAIM_NOT_UNIQUE:{claim_id}")
            by_id[claim_id] = row

    specs: list[KosisQuerySpecSchema] = []
    ready: list[ClaimRegistryRecord] = []
    preverification: list[KosisQuerySpecSchema] = []
    for item in scope.records:
        row = by_id.get(item.claim_id)
        if row is None:
            raise ValueError(f"DIRECT_VALUE_176_LEDGER_ROW_MISSING:{item.claim_id}")
        record = ledger_row_to_registry(row)
        if record.claim.source_sentence != item.source_sentence:
            raise ValueError(f"DIRECT_VALUE_176_SOURCE_MISMATCH:{item.claim_id}")
        prepared = prepare_coordinate_spec(record)
        specs.append(prepared.spec)
        if prepared.spec.readiness_status == "COORDINATE_READY":
            ready.append(prepared.record)
        else:
            preverification.append(prepared.spec)

    spec_ids = [spec.claim_id for spec in specs]
    if len(spec_ids) != expected_count or len(set(spec_ids)) != expected_count:
        raise ValueError("DIRECT_VALUE_176_SPEC_COVERAGE_MISMATCH")
    if len(ready) + len(preverification) != expected_count:
        raise ValueError("DIRECT_VALUE_176_READINESS_COVERAGE_MISMATCH")
    readiness_counts = dict(sorted(Counter(spec.readiness_status for spec in specs).items()))
    payload = {
        "scope_manifest_sha256": scope.manifest_sha256,
        "specs": [spec.model_dump(mode="json") for spec in sorted(specs, key=lambda value: value.claim_id)],
        "ready_claim_ids": sorted(record.claim.claim_id for record in ready),
        "readiness_counts": readiness_counts,
    }
    digest = sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return DirectValueCoordinateSpecBundle(
        scope=scope,
        specs=tuple(sorted(specs, key=lambda value: value.claim_id)),
        ready_records=tuple(sorted(ready, key=lambda value: value.claim.claim_id)),
        preverification_specs=tuple(sorted(preverification, key=lambda value: value.claim_id)),
        readiness_counts=readiness_counts,
        manifest_sha256=digest,
    )


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()
