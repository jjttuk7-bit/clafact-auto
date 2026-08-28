"""Freeze the unresolved type-8 direct-value scope for coordinate evaluation."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Iterable, Mapping


_DONE_COLUMNS = (
    "공식판정완료", "개선후공식판정완료", "복구48공식판정완료", "지표구체화18공식판정완료",
)


@dataclass(frozen=True, slots=True)
class CoordinateSpecScopeRecord:
    claim_id: str
    parent_claim_id: str
    article_id: str
    split_set: str
    current_reason: str
    source_sentence: str
    source_sentence_sha256: str


@dataclass(frozen=True, slots=True)
class CoordinateSpecScope:
    records: tuple[CoordinateSpecScopeRecord, ...]
    reason_counts: dict[str, int]
    split_counts: dict[str, int]
    manifest_sha256: str

    def to_dict(self, *, include_final_blind_source: bool = False) -> dict[str, object]:
        records = []
        for item in self.records:
            row = asdict(item)
            if item.split_set == "FINAL_BLIND" and not include_final_blind_source:
                row["source_sentence"] = None
            records.append(row)
        return {
            "records": records,
            "reason_counts": self.reason_counts,
            "split_counts": self.split_counts,
            "manifest_sha256": self.manifest_sha256,
        }


def build_coordinate_spec_scope(
    rows: Iterable[Mapping[str, object]], *, expected_count: int = 176,
) -> CoordinateSpecScope:
    selected: list[CoordinateSpecScopeRecord] = []
    seen: set[str] = set()
    for row in rows:
        if any(_text(row.get(column)) == "Y" for column in _DONE_COLUMNS):
            continue
        decision = _text(row.get("지표구체화18결과")) or _text(row.get("Claim구조재판정결과"))
        if decision.startswith(("EXCLUDE_", "MOVE_")):
            continue
        claim_id = _text(row.get("자식Claim번호")) or _text(row.get("원본부모Claim번호"))
        parent_id = _text(row.get("원본부모Claim번호")) or claim_id
        if not claim_id or claim_id in seen:
            raise ValueError(f"DIRECT_VALUE_176_CLAIM_NOT_UNIQUE:{claim_id}")
        seen.add(claim_id)
        source = _text(row.get("원문"))
        split_set = _text(row.get("사용집합")) or "UNASSIGNED"
        reason = (
            _text(row.get("지표구체화18최종사유"))
            if _text(row.get("지표구체화18재처리")) == "Y"
            else _text(row.get("복구48최종사유"))
        ) or _text(row.get("개선후사유")) or _text(row.get("최종사유코드"))
        selected.append(CoordinateSpecScopeRecord(
            claim_id=claim_id,
            parent_claim_id=parent_id,
            article_id=_text(row.get("기사그룹ID")) or parent_id.split("_", 1)[0],
            split_set=split_set,
            current_reason=reason,
            source_sentence=source,
            source_sentence_sha256=sha256(source.encode("utf-8")).hexdigest(),
        ))
    selected.sort(key=lambda item: item.claim_id)
    if len(selected) != expected_count:
        raise ValueError(f"DIRECT_VALUE_176_SCOPE_COUNT_MISMATCH:{len(selected)}:{expected_count}")
    payload = [asdict(item) for item in selected]
    digest = sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    return CoordinateSpecScope(
        records=tuple(selected),
        reason_counts=dict(sorted(Counter(item.current_reason for item in selected).items())),
        split_counts=dict(sorted(Counter(item.split_set for item in selected).items())),
        manifest_sha256=digest,
    )


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()
