"""Leakage-safe scope for the direct-value coordinate/publication goal."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Iterable, Mapping

from core.direct_value_generalization_split import (
    FINAL_BLIND,
    INTERMEDIATE_VALIDATION,
    RULE_DISCOVERY,
)


COORDINATE_REASONS = frozenset(
    {"NO_HARD_GUARD_CANDIDATE", "NO_EVIDENCE_COORDINATE_CANDIDATE"}
)
PUBLICATION_REASONS = frozenset({"AS_OF_UNAVAILABLE", "PUBLICATION_FETCH_FAILED"})
TARGET_REASONS = COORDINATE_REASONS | PUBLICATION_REASONS


@dataclass(frozen=True, slots=True)
class ScopeRecord:
    claim_id: str
    parent_claim_id: str
    split_set: str
    reason_code: str
    issue_family: str
    source_sentence: str
    source_sentence_sha256: str


@dataclass(frozen=True, slots=True)
class ScopeManifest:
    records: tuple[ScopeRecord, ...]
    reason_counts: dict[str, int]
    split_counts: dict[str, int]
    manifest_sha256: str

    def to_audit_dict(self, *, include_final_blind_source: bool) -> dict[str, object]:
        rows: list[dict[str, object]] = []
        for record in self.records:
            row = asdict(record)
            if record.split_set == FINAL_BLIND and not include_final_blind_source:
                row["source_sentence"] = None
            rows.append(row)
        return {
            "records": rows,
            "reason_counts": dict(self.reason_counts),
            "split_counts": dict(self.split_counts),
            "manifest_sha256": self.manifest_sha256,
        }


def build_scope_manifest(rows: Iterable[Mapping[str, object]]) -> ScopeManifest:
    """Freeze only current coordinate/publication failures without blind leakage."""

    selected: list[ScopeRecord] = []
    seen: set[str] = set()
    for row in rows:
        reason = str(row.get("개선후사유") or "").strip()
        if reason not in TARGET_REASONS:
            continue
        parent_id = str(row.get("원본부모Claim번호") or "").strip()
        claim_id = str(row.get("자식Claim번호") or parent_id).strip()
        if not claim_id or not parent_id:
            raise ValueError("DIRECT_VALUE_SCOPE_CLAIM_ID_MISSING")
        if claim_id in seen:
            raise ValueError(f"DIRECT_VALUE_SCOPE_CLAIM_NOT_UNIQUE:{claim_id}")
        seen.add(claim_id)
        split_set = str(row.get("사용집합") or "").strip()
        if split_set not in {RULE_DISCOVERY, INTERMEDIATE_VALIDATION, FINAL_BLIND}:
            raise ValueError(f"DIRECT_VALUE_SCOPE_SET_INVALID:{claim_id}:{split_set}")
        source = str(row.get("원문") or "")
        selected.append(
            ScopeRecord(
                claim_id=claim_id,
                parent_claim_id=parent_id,
                split_set=split_set,
                reason_code=reason,
                issue_family="COORDINATE" if reason in COORDINATE_REASONS else "PUBLICATION",
                source_sentence=source,
                source_sentence_sha256=sha256(source.encode("utf-8")).hexdigest(),
            )
        )
    selected.sort(key=lambda item: item.claim_id)
    signature = sha256(
        "\n".join(
            "|".join(
                (
                    item.claim_id,
                    item.parent_claim_id,
                    item.split_set,
                    item.reason_code,
                    item.source_sentence_sha256,
                )
            )
            for item in selected
        ).encode("utf-8")
    ).hexdigest()
    return ScopeManifest(
        records=tuple(selected),
        reason_counts=dict(sorted(Counter(item.reason_code for item in selected).items())),
        split_counts=dict(sorted(Counter(item.split_set for item in selected).items())),
        manifest_sha256=signature,
    )


__all__ = [
    "COORDINATE_REASONS",
    "FINAL_BLIND",
    "INTERMEDIATE_VALIDATION",
    "PUBLICATION_REASONS",
    "RULE_DISCOVERY",
    "ScopeManifest",
    "ScopeRecord",
    "build_scope_manifest",
]
