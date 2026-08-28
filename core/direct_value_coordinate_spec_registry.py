"""Rebuild durable Claim Registry inputs from the type-8 audit ledger."""

from __future__ import annotations

import json
from datetime import date
from typing import Mapping

from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


def ledger_row_to_registry(row: Mapping[str, object]) -> ClaimRegistryRecord:
    claim_id = _text(row.get("자식Claim번호")) or _text(row.get("원본부모Claim번호"))
    original_sentence_id = _text(row.get("원본부모Claim번호")).rsplit("_", 1)[-1] or "1"
    source = _text(row.get("원문"))
    expression = _text(row.get("원문근거표현")) or _text(row.get("대상수치표현"))
    start = source.find(expression) if expression else -1
    dimension = _json_mapping(row.get("차원JSON"))
    indicator = _text(row.get("지표구체화18수정지표")) or _text(row.get("지표"))
    time = _text(row.get("지표구체화18수정시점")) or _text(row.get("기준시점"))
    frequency = _text(row.get("지표구체화18수정주기")) or _text(row.get("주기"))
    region = _text(row.get("지표구체화18수정지역")) or _text(row.get("지역"))
    parse_status = _text(row.get("파싱상태"))
    if parse_status not in {"AUTO_OK", "HOLD", "HUMAN_REVIEW"}:
        parse_status = "AUTO_OK"
    enrichment: dict[str, object] = {
        "coordinate_spec_scope": "DIRECT_VALUE_UNRESOLVED_176",
        "coordinate_spec_split_set": _text(row.get("사용집합")) or "UNASSIGNED",
        "original_sentence_id": original_sentence_id,
    }
    if start >= 0:
        enrichment.update({
            "target_link_status": "SOURCE_GROUNDED",
            "target_numeric_expression": expression,
            "target_numeric_start": start,
            "target_numeric_end": start + len(expression),
            "target_numeric_role": "대상값",
        })
    else:
        enrichment.update({
            "target_link_status": "TARGET_NOT_FOUND_IN_SOURCE",
            "target_link_reason_code": "LEDGER_TARGET_SPAN_REQUIRES_REPAIR",
        })
    return ClaimRegistryRecord(
        article_id=_text(row.get("기사그룹ID")) or claim_id.split("_", 1)[0],
        sentence_id=f"{original_sentence_id}::{claim_id}",
        article_published_at=_date(row.get("기사작성일")),
        source_ref="direct_value_coordinate_spec_176",
        claim=ClaimSchema(
            claim_id=claim_id,
            source_sentence=source,
            indicator=indicator or None,
            value=_float(row.get("기사값")),
            unit=_text(row.get("단위")) or None,
            time=time or None,
            frequency=frequency or None,
            region=region or None,
            population=_text(row.get("대상집단")) or None,
            dimension=dimension,
            comparison=_json_mapping(row.get("비교JSON")),
            calculation=_text(row.get("계산방식")) or "DIRECT_VALUE",
            condition=_json_mapping(row.get("조건JSON")),
            source_hint=_text(row.get("공식조회진입경로")) or None,
            parse_status=parse_status,
            parse_reason=_text(row.get("최종사유코드")) or None if parse_status != "AUTO_OK" else None,
        ),
        slot_enrichment=enrichment,
    )


def _json_mapping(value: object) -> dict[str, str] | None:
    text = _text(value)
    if not text:
        return None
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}
    if not isinstance(decoded, dict):
        return {"raw": json.dumps(decoded, ensure_ascii=False)}
    if set(decoded) == {"raw"} and isinstance(decoded["raw"], str):
        return {"raw": decoded["raw"]}
    return {str(key): json.dumps(item, ensure_ascii=False) if isinstance(item, (dict, list)) else str(item) for key, item in decoded.items()}


def _date(value: object) -> date | None:
    text = _text(value)[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _float(value: object) -> float | None:
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()
