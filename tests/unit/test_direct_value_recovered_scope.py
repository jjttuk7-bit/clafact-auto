from datetime import date

import pytest

from core.direct_value_recovered_scope import build_recovered_direct_scope
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


def _ledger(claim_id: str, source: str, expression: str) -> dict[str, str]:
    return {
        "원본부모Claim번호": claim_id,
        "자식Claim번호": claim_id,
        "Claim구조재판정결과": "KEEP_DIRECT_RECOVERED",
        "원문": source,
        "원문근거표현": expression,
        "지표": "취업자",
        "기사값": "2800",
        "단위": "만명",
        "기준시점": "2024-01",
        "주기": "M",
    }


def _record(claim_id: str, source: str) -> ClaimRegistryRecord:
    return ClaimRegistryRecord(
        article_id="A1",
        sentence_id="1",
        article_published_at=date(2024, 2, 15),
        source_ref="fixture",
        claim=ClaimSchema(
            claim_id=claim_id,
            source_sentence=source,
            parse_status="HOLD",
            parse_reason="CLAIM_PARSE_UNCERTAIN",
        ),
    )


def test_scope_patches_exact_source_target_and_auto_slots() -> None:
    source = "2024년 1월 취업자는 2800만명이었다."
    scope = build_recovered_direct_scope(
        [_ledger("C1", source, "2800만명")],
        [_record("C1", source)],
        expected_count=1,
    )
    record = scope.records[0]
    assert record.claim.parse_status == "AUTO_OK"
    assert record.claim.calculation == "DIRECT_VALUE"
    assert record.slot_enrichment["target_link_status"] == "SOURCE_GROUNDED"
    start = record.slot_enrichment["target_numeric_start"]
    end = record.slot_enrichment["target_numeric_end"]
    assert source[start:end] == "2800만명"


def test_scope_uses_indicator_proximity_when_expression_repeats() -> None:
    source = "취업자는 2800만명이고 다른 값도 2800만명이다."
    scope = build_recovered_direct_scope(
        [_ledger("C1", source, "2800만명")],
        [_record("C1", source)],
        expected_count=1,
    )
    assert scope.records[0].slot_enrichment["target_numeric_start"] == source.find("2800만명")


def test_scope_rejects_ambiguous_repeated_target() -> None:
    source = "수치는 2800만명이고 다른 수치도 2800만명이다."
    with pytest.raises(ValueError, match="RECOVERED_DIRECT_TARGET_NOT_UNIQUE:C1:0"):
        build_recovered_direct_scope(
            [_ledger("C1", source, "2800만명")],
            [_record("C1", source)],
            expected_count=1,
        )
