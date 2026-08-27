"""Compile and merge auditable Claim structure reclassification results."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from typing import Iterable, Mapping

from core.direct_value_claim_reclassification_scope import build_reclassification_scope
from core.direct_value_claim_reclassifier import DirectValueReclassification, reclassify_direct_value_claim


OUTPUT_COLUMNS = (
    "Claim구조재판정실행",
    "Claim구조재판정결과",
    "Claim구조상위결과",
    "이동대상탭",
    "적용재판정규칙",
    "원문근거표현",
    "재판정이전사유",
    "재판정최종사유",
    "재판정사용집합",
    "재판정실행근거",
)


def compile_reclassifications(
    rows: Iterable[Mapping[str, object]], *, expected_count: int | None = None
) -> list[DirectValueReclassification]:
    materialized = list(rows)
    scope = build_reclassification_scope(materialized, expected_count=expected_count)
    by_id = {
        str(row.get("자식Claim번호") or row.get("원본부모Claim번호") or "").strip(): row
        for row in materialized
    }
    results = [reclassify_direct_value_claim(by_id[item.claim_id]) for item in scope.records]
    if len({item.claim_id for item in results}) != len(results):
        raise ValueError("DIRECT_VALUE_RECLASSIFICATION_RESULT_NOT_UNIQUE")
    return results


def merge_reclassifications(
    rows: Iterable[Mapping[str, object]],
    results: Iterable[DirectValueReclassification],
    *,
    evidence_ref: str,
) -> list[dict[str, object]]:
    by_id = {item.claim_id: item for item in results}
    merged: list[dict[str, object]] = []
    matched: set[str] = set()
    for source_row in rows:
        row = dict(source_row)
        claim_id = str(row.get("자식Claim번호") or row.get("원본부모Claim번호") or "").strip()
        decision = by_id.get(claim_id)
        if decision is None:
            for column in OUTPUT_COLUMNS:
                row.setdefault(column, "")
        else:
            matched.add(claim_id)
            row.update({
                "Claim구조재판정실행": "Y",
                "Claim구조재판정결과": decision.result_code,
                "Claim구조상위결과": decision.top_level_result,
                "이동대상탭": decision.target_tab,
                "적용재판정규칙": decision.applied_rule,
                "원문근거표현": decision.source_evidence,
                "재판정이전사유": decision.original_reason,
                "재판정최종사유": decision.final_reason,
                "재판정사용집합": decision.split_set,
                "재판정실행근거": evidence_ref,
            })
        merged.append(row)
    missing = set(by_id) - matched
    if missing:
        raise ValueError(f"DIRECT_VALUE_RECLASSIFICATION_RESULT_ORPHAN:{sorted(missing)[0]}")
    return merged


def summarize_reclassifications(results: Iterable[DirectValueReclassification]) -> dict[str, object]:
    materialized = list(results)
    top = Counter(item.top_level_result for item in materialized)
    result = Counter(item.result_code for item in materialized)
    tabs = Counter(item.target_tab for item in materialized)
    splits = Counter(item.split_set for item in materialized)
    remaining = Counter(item.final_reason for item in materialized if item.result_code == "KEEP_DIRECT_REQUIRES_RECOVERY")
    exclusions = Counter(item.final_reason for item in materialized if item.top_level_result == "EXCLUDE_FROM_KOSIS")
    move_rules = Counter(item.applied_rule for item in materialized if item.top_level_result == "MOVE_TO_OTHER_TYPE")
    if sum(top.values()) != len(materialized):
        raise ValueError("DIRECT_VALUE_RECLASSIFICATION_SUMMARY_MISMATCH")
    return {
        "executed_count": len(materialized),
        "top_level_counts": dict(sorted(top.items())),
        "result_counts": dict(sorted(result.items())),
        "target_tab_counts": dict(sorted(tabs.items())),
        "split_counts": dict(sorted(splits.items())),
        "remaining_recovery_reason_counts": dict(sorted(remaining.items())),
        "exclusion_reason_counts": dict(sorted(exclusions.items())),
        "move_rule_counts": dict(sorted(move_rules.items())),
        "records": [asdict(item) for item in materialized],
    }
