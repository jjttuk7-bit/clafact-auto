"""Freeze and reconstruct the 48 source-grounded direct-value Claims."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable, Mapping

from core.source_numeric_inventory import inventory_numeric_mentions
from core.source_numeric_role_classifier import classify_numeric_roles
from schemas.claim_registry import ClaimRegistryRecord


TARGET_RESULT = "KEEP_DIRECT_RECOVERED"


@dataclass(frozen=True, slots=True)
class RecoveredDirectScope:
    records: tuple[ClaimRegistryRecord, ...]
    claim_ids: tuple[str, ...]
    manifest_sha256: str


def build_recovered_direct_scope(
    ledger_rows: Iterable[Mapping[str, object]],
    registry_records: Iterable[ClaimRegistryRecord],
    *,
    expected_count: int = 48,
) -> RecoveredDirectScope:
    selected_rows = {
        _text(row, "자식Claim번호") or _text(row, "원본부모Claim번호"): row
        for row in ledger_rows
        if _text(row, "Claim구조재판정결과") == TARGET_RESULT
    }
    if len(selected_rows) != expected_count:
        raise ValueError(f"RECOVERED_DIRECT_SCOPE_COUNT_MISMATCH:{len(selected_rows)}:{expected_count}")
    registry: dict[str, ClaimRegistryRecord] = {}
    for record in registry_records:
        claim_id = record.claim.claim_id
        if claim_id in registry:
            raise ValueError(f"RECOVERED_DIRECT_REGISTRY_NOT_UNIQUE:{claim_id}")
        registry[claim_id] = record

    patched: list[ClaimRegistryRecord] = []
    for claim_id in sorted(selected_rows):
        row = selected_rows[claim_id]
        record = registry.get(claim_id)
        if record is None:
            raise ValueError(f"RECOVERED_DIRECT_REGISTRY_MISSING:{claim_id}")
        source = _text(row, "원문")
        if source != record.claim.source_sentence:
            raise ValueError(f"RECOVERED_DIRECT_SOURCE_MISMATCH:{claim_id}")
        expression = _text(row, "원문근거표현")
        value = _float_or_none(row.get("기사값"))
        mentions = inventory_numeric_mentions(source)
        classified = classify_numeric_roles(
            source_sentence=source,
            mentions=mentions,
            claim_value=value,
            claim_unit=_text(row, "단위"),
            indicator=_text(row, "지표"),
        )
        role_selected = [item for item in classified.assignments if item.auto_target_eligible]
        selected_mentions = [
            mention
            for assignment in role_selected
            for mention in mentions
            if mention.mention_id == assignment.mention_id and mention.expression == expression
        ]
        if len(selected_mentions) != 1:
            raise ValueError(
                f"RECOVERED_DIRECT_TARGET_NOT_UNIQUE:{claim_id}:{len(selected_mentions)}"
            )
        start = selected_mentions[0].start
        claim = record.claim.model_copy(update={
            "indicator": _text(row, "지표") or record.claim.indicator,
            "value": value if value is not None else record.claim.value,
            "unit": _text(row, "단위") or record.claim.unit,
            "time": _text(row, "기준시점") or record.claim.time,
            "frequency": _text(row, "주기") or record.claim.frequency,
            "calculation": "DIRECT_VALUE",
            "parse_status": "AUTO_OK",
            "parse_reason": None,
        })
        enrichment = dict(record.slot_enrichment or {})
        enrichment.update({
            "target_link_status": "SOURCE_GROUNDED",
            "target_link_reason_code": "SOURCE_TARGET_EXACT_MATCH_RECLASSIFIED",
            "target_link_version": "1.2",
            "target_numeric_expression": expression,
            "target_numeric_role": "대상값",
            "target_numeric_start": start,
            "target_numeric_end": start + len(expression),
            "claim_structure_reclassification": TARGET_RESULT,
        })
        patched.append(record.model_copy(update={"claim": claim, "slot_enrichment": enrichment}))

    signature = sha256(
        "\n".join(
            f"{record.claim.claim_id}|{sha256(record.claim.source_sentence.encode('utf-8')).hexdigest()}|"
            f"{record.slot_enrichment['target_numeric_expression']}"
            for record in patched
        ).encode("utf-8")
    ).hexdigest()
    return RecoveredDirectScope(
        records=tuple(patched),
        claim_ids=tuple(record.claim.claim_id for record in patched),
        manifest_sha256=signature,
    )


def _text(row: Mapping[str, object], key: str) -> str:
    value = row.get(key)
    return "" if value is None else str(value).strip()


def _float_or_none(value: object) -> float | None:
    text = "" if value is None else str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None
