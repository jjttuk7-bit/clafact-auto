"""Freeze the direct-value Claim structure/classification recheck scope."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Iterable, Mapping

from core.direct_value_generalization_split import (
    FINAL_BLIND,
    INTERMEDIATE_VALIDATION,
    RULE_DISCOVERY,
)


_VALID_SPLITS = {RULE_DISCOVERY, INTERMEDIATE_VALIDATION, FINAL_BLIND}
_CLAIM_STRUCTURE_REASONS = {
    "INDICATOR_REFINEMENT_REQUIRED",
    "CLAIM_PARSE_UNCERTAIN",
    "TARGET_VALUE_NOT_IN_SOURCE_SENTENCE",
    "TARGET_NOT_FOUND_IN_SOURCE",
    "NON_OBSERVED_FORECAST",
    "INDICATOR_UNIT_MEASURE_MISMATCH",
    "TARGET_AMBIGUOUS_IN_SOURCE",
    "NON_STATISTICAL_PRIVATE_TRANSACTION",
    "MISSING_REQUIRED_SLOTS:time",
    "INDICATOR_MEASURE_FAMILY_AMBIGUOUS",
    "DIRECT_VALUE_CHANGE_TARGET_MISCLASSIFIED",
    "NON_STATISTICAL_POLICY_THRESHOLD",
    "RELATIVE_TIME_UNRESOLVED",
    "MISSING_REQUIRED_SLOTS:value",
    "CONTEXT_TARGET_UNRESOLVED",
    "CALCULATION_EVIDENCE_PLAN_UNRESOLVED",
}
_MACHINE_REASON = re.compile(r"^[A-Z][A-Z0-9_]*(?::[A-Za-z0-9_,.-]+)?$")


@dataclass(frozen=True, slots=True)
class ReclassificationScopeRecord:
    claim_id: str
    parent_claim_id: str
    split_set: str
    reason_code: str
    source_sentence: str
    source_sentence_sha256: str


@dataclass(frozen=True, slots=True)
class ReclassificationScope:
    records: tuple[ReclassificationScopeRecord, ...]
    manifest_sha256: str

    @property
    def reason_counts(self) -> dict[str, int]:
        return dict(sorted(Counter(item.reason_code for item in self.records).items()))

    @property
    def split_counts(self) -> dict[str, int]:
        return dict(sorted(Counter(item.split_set for item in self.records).items()))

    def to_audit_dict(self, *, include_final_blind_source: bool = False) -> dict[str, object]:
        records: list[dict[str, object]] = []
        for item in self.records:
            row = asdict(item)
            if item.split_set == FINAL_BLIND and not include_final_blind_source:
                row["source_sentence"] = None
            records.append(row)
        return {
            "count": len(self.records),
            "split_counts": self.split_counts,
            "reason_counts": self.reason_counts,
            "manifest_sha256": self.manifest_sha256,
            "records": records,
        }


def _is_claim_structure_reason(reason: str) -> bool:
    if reason in _CLAIM_STRUCTURE_REASONS:
        return True
    return bool(reason) and _MACHINE_REASON.fullmatch(reason) is None


def build_reclassification_scope(
    rows: Iterable[Mapping[str, object]],
    *,
    expected_count: int | None = None,
) -> ReclassificationScope:
    records: list[ReclassificationScopeRecord] = []
    seen: set[str] = set()
    for row in rows:
        reason = str(row.get("개선후사유") or "").strip()
        if not _is_claim_structure_reason(reason):
            continue
        parent_id = str(row.get("원본부모Claim번호") or "").strip()
        claim_id = str(row.get("자식Claim번호") or parent_id).strip()
        if not claim_id or not parent_id:
            raise ValueError("DIRECT_VALUE_RECLASSIFICATION_CLAIM_ID_MISSING")
        if claim_id in seen:
            raise ValueError(f"DIRECT_VALUE_RECLASSIFICATION_CLAIM_NOT_UNIQUE:{claim_id}")
        seen.add(claim_id)
        split = str(row.get("사용집합") or "").strip()
        if split not in _VALID_SPLITS:
            raise ValueError(f"DIRECT_VALUE_RECLASSIFICATION_SPLIT_INVALID:{claim_id}:{split}")
        source = str(row.get("원문") or "").strip()
        records.append(
            ReclassificationScopeRecord(
                claim_id=claim_id,
                parent_claim_id=parent_id,
                split_set=split,
                reason_code=reason,
                source_sentence=source,
                source_sentence_sha256=sha256(source.encode("utf-8")).hexdigest(),
            )
        )
    records.sort(key=lambda item: item.claim_id)
    if expected_count is not None and len(records) != expected_count:
        raise ValueError(
            f"DIRECT_VALUE_RECLASSIFICATION_COUNT_MISMATCH:{len(records)}:{expected_count}"
        )
    payload = [asdict(item) for item in records]
    digest = sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return ReclassificationScope(tuple(records), digest)


__all__ = [
    "FINAL_BLIND",
    "INTERMEDIATE_VALIDATION",
    "RULE_DISCOVERY",
    "ReclassificationScope",
    "ReclassificationScopeRecord",
    "build_reclassification_scope",
]
