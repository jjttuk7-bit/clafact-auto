"""Freeze and rebuild the direct-value indicator-refinement problem group."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Iterable, Mapping

from core.direct_value_claim_reclassifier import (
    DirectValueReclassification,
    reclassify_direct_value_claim,
)
from core.source_indicator_refinement import apply_source_indicator_refinement
from schemas.claim_registry import ClaimRegistryRecord


TARGET_REASON = "INDICATOR_REFINEMENT_REQUIRED"


@dataclass(frozen=True, slots=True)
class IndicatorRefinementScope:
    records: tuple[ClaimRegistryRecord, ...]
    decisions: tuple[DirectValueReclassification, ...]
    manifest_sha256: str

    @property
    def decision_counts(self) -> dict[str, int]:
        return dict(sorted(Counter(item.result_code for item in self.decisions).items()))


def build_indicator_refinement_scope(
    ledger_rows: Iterable[Mapping[str, object]],
    registry_records: Iterable[ClaimRegistryRecord],
    *,
    expected_scope_count: int = 18,
    expected_run_count: int = 6,
) -> IndicatorRefinementScope:
    """Classify all 18 rows and return only corrected direct-value inputs."""

    selected = [
        row for row in ledger_rows
        if _text(row, "복구48최종사유") == TARGET_REASON
    ]
    if len(selected) != expected_scope_count:
        raise ValueError(
            f"INDICATOR_REFINEMENT_SCOPE_COUNT_MISMATCH:{len(selected)}:{expected_scope_count}"
        )
    registry_list = list(registry_records)
    registry = {record.claim.claim_id: record for record in registry_list}
    if len(registry) != len(registry_list):
        raise ValueError("INDICATOR_REFINEMENT_REGISTRY_NOT_UNIQUE")

    decisions: list[DirectValueReclassification] = []
    runnable: list[ClaimRegistryRecord] = []
    seen: set[str] = set()
    for row in selected:
        claim_id = _text(row, "자식Claim번호") or _text(row, "원본부모Claim번호")
        if not claim_id or claim_id in seen:
            raise ValueError(f"INDICATOR_REFINEMENT_CLAIM_NOT_UNIQUE:{claim_id}")
        seen.add(claim_id)
        decision_input = dict(row)
        decision_input["개선후사유"] = TARGET_REASON
        decision_input["대상수치표현"] = _text(row, "원문근거표현")
        decision = reclassify_direct_value_claim(decision_input)
        decisions.append(decision)
        if decision.result_code != "KEEP_DIRECT_RECOVERED":
            continue
        record = registry.get(claim_id)
        if record is None:
            raise ValueError(f"INDICATOR_REFINEMENT_REGISTRY_MISSING:{claim_id}")
        if record.claim.source_sentence != _text(row, "원문"):
            raise ValueError(f"INDICATOR_REFINEMENT_SOURCE_MISMATCH:{claim_id}")
        expression = _text(row, "원문근거표현")
        refined = apply_source_indicator_refinement(record, target_expression=expression)
        claim = refined.claim.model_copy(update={"parse_status": "AUTO_OK", "parse_reason": None})
        enrichment = dict(refined.slot_enrichment or {})
        enrichment.update({
            "indicator_refinement_group": TARGET_REASON,
            "indicator_refinement_decision": decision.result_code,
        })
        runnable.append(refined.model_copy(update={"claim": claim, "slot_enrichment": enrichment}))

    if len(runnable) != expected_run_count:
        raise ValueError(
            f"INDICATOR_REFINEMENT_RUN_COUNT_MISMATCH:{len(runnable)}:{expected_run_count}"
        )
    payload = {
        "scope_count": len(decisions),
        "run_count": len(runnable),
        "decisions": [asdict(item) for item in sorted(decisions, key=lambda item: item.claim_id)],
        "run_claim_ids": sorted(record.claim.claim_id for record in runnable),
    }
    digest = sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return IndicatorRefinementScope(
        records=tuple(sorted(runnable, key=lambda item: item.claim.claim_id)),
        decisions=tuple(sorted(decisions, key=lambda item: item.claim_id)),
        manifest_sha256=digest,
    )


def _text(row: Mapping[str, object], key: str) -> str:
    value = row.get(key)
    return "" if value is None else str(value).strip()
