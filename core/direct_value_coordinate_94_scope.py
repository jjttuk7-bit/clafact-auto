"""Freeze the 94 direct-value Claims stopped at the coordinate guard boundary."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Iterable, Mapping


TARGET_FAILURE_STAGE = "필수 조건 검사"


@dataclass(frozen=True, slots=True)
class DirectValueCoordinate94Record:
    claim_id: str
    source_sentence: str
    source_sentence_sha256: str
    before_failure_stage: str
    before_reason: str
    indicator: str
    unit: str
    frequency: str
    region: str
    population: str


@dataclass(frozen=True, slots=True)
class DirectValueCoordinate94Scope:
    records: tuple[DirectValueCoordinate94Record, ...]
    failure_reason_counts: dict[str, int]
    manifest_sha256: str

    def to_dict(self) -> dict[str, object]:
        return {
            "records": [asdict(record) for record in self.records],
            "failure_reason_counts": self.failure_reason_counts,
            "manifest_sha256": self.manifest_sha256,
        }


def build_coordinate_94_scope(
    rows: Iterable[Mapping[str, object]],
    *,
    expected_count: int = 94,
    source_fallbacks: Mapping[str, str] | None = None,
) -> DirectValueCoordinate94Scope:
    selected: list[DirectValueCoordinate94Record] = []
    seen: set[str] = set()
    fallback = source_fallbacks or {}
    for row in rows:
        if _text(row.get("최종실패단계")) != TARGET_FAILURE_STAGE:
            continue
        claim_id = _text(row.get("Claim번호"))
        if not claim_id or claim_id in seen:
            raise ValueError(f"DIRECT_VALUE_COORDINATE_94_CLAIM_NOT_UNIQUE:{claim_id}")
        seen.add(claim_id)
        source = _text(row.get("원문")) or _text(fallback.get(claim_id))
        if not source:
            raise ValueError(f"DIRECT_VALUE_COORDINATE_94_SOURCE_MISSING:{claim_id}")
        selected.append(DirectValueCoordinate94Record(
            claim_id=claim_id,
            source_sentence=source,
            source_sentence_sha256=sha256(source.encode("utf-8")).hexdigest(),
            before_failure_stage=TARGET_FAILURE_STAGE,
            before_reason=_text(row.get("최종사유")),
            indicator=_text(row.get("검색지표")),
            unit=_text(row.get("단위")),
            frequency=_text(row.get("주기")),
            region=_text(row.get("지역")),
            population=_text(row.get("대상집단")),
        ))
    selected.sort(key=lambda record: record.claim_id)
    if len(selected) != expected_count:
        raise ValueError(
            f"DIRECT_VALUE_COORDINATE_94_SCOPE_COUNT_MISMATCH:{len(selected)}:{expected_count}"
        )
    payload = [asdict(record) for record in selected]
    digest = sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return DirectValueCoordinate94Scope(
        records=tuple(selected),
        failure_reason_counts=dict(sorted(Counter(record.before_reason for record in selected).items())),
        manifest_sha256=digest,
    )


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


__all__ = [
    "DirectValueCoordinate94Record",
    "DirectValueCoordinate94Scope",
    "TARGET_FAILURE_STAGE",
    "build_coordinate_94_scope",
]

