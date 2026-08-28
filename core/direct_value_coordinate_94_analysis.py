"""Join the frozen 94-Claim scope to live diagnostics and classify causes."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
from typing import Mapping, Sequence

from core.direct_value_coordinate_94_scope import DirectValueCoordinate94Scope
from core.direct_value_coordinate_failure_classifier import classify_coordinate_failure


@dataclass(frozen=True, slots=True)
class DirectValueCoordinate94Analysis:
    rows: tuple[dict[str, object], ...]
    primary_cause_counts: dict[str, int]
    rule_family_counts: dict[str, int]


def analyze_coordinate_94(
    scope: DirectValueCoordinate94Scope,
    live_rows: Sequence[Mapping[str, object]],
) -> DirectValueCoordinate94Analysis:
    by_id: dict[str, Mapping[str, object]] = {}
    for live in live_rows:
        claim_id = _text(live.get("parent_claim_id")) or _text(live.get("claim_id"))
        if not claim_id:
            continue
        if claim_id in by_id:
            raise ValueError(f"DIRECT_VALUE_COORDINATE_94_LIVE_NOT_UNIQUE:{claim_id}")
        by_id[claim_id] = live

    output: list[dict[str, object]] = []
    for record in scope.records:
        live = by_id.get(record.claim_id)
        if live is None:
            raise ValueError(f"DIRECT_VALUE_COORDINATE_94_LIVE_MISSING:{record.claim_id}")
        claim = live.get("claim") if isinstance(live.get("claim"), Mapping) else {}
        resolution = (
            live.get("official_resolution")
            if isinstance(live.get("official_resolution"), Mapping)
            else {}
        )
        diagnostics = (
            resolution.get("catalog_diagnostics")
            if isinstance(resolution.get("catalog_diagnostics"), Mapping)
            else {}
        )
        candidates = [
            candidate
            for candidate in resolution.get("candidates") or []
            if isinstance(candidate, Mapping)
        ]
        classification = classify_coordinate_failure(claim, diagnostics, candidates)
        output.append({
            "Claim번호": record.claim_id,
            "원문해시": record.source_sentence_sha256,
            "개선전실패단계": record.before_failure_stage,
            "개선전사유": record.before_reason,
            "지표": record.indicator,
            "단위": record.unit,
            "주기": record.frequency,
            "지역": record.region,
            "대상집단": record.population,
            "대표원인": classification.primary_cause,
            "보조원인JSON": json.dumps(classification.supporting_causes, ensure_ascii=False),
            "적용규칙군": classification.rule_family,
            "판정근거코드JSON": json.dumps(classification.evidence_codes, ensure_ascii=False),
            "후보수": int(diagnostics.get("candidate_count") or len(candidates)),
            "HardGuard통과후보수": int(diagnostics.get("hard_guard_passed_count") or 0),
        })
    if len(output) != len(scope.records):
        raise ValueError("DIRECT_VALUE_COORDINATE_94_ANALYSIS_COVERAGE_MISMATCH")
    return DirectValueCoordinate94Analysis(
        rows=tuple(output),
        primary_cause_counts=dict(sorted(Counter(row["대표원인"] for row in output).items())),
        rule_family_counts=dict(sorted(Counter(row["적용규칙군"] for row in output).items())),
    )


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


__all__ = ["DirectValueCoordinate94Analysis", "analyze_coordinate_94"]
