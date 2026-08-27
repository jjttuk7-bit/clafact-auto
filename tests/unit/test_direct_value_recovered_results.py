from core.direct_value_recovered_results import compile_recovered_official_results, summarize_recovered_official_results


def _ledger(claim_id: str, value: str, expression: str) -> dict[str, str]:
    return {"자식Claim번호": claim_id, "Claim구조재판정결과": "KEEP_DIRECT_RECOVERED", "기사값": value, "원문근거표현": expression}


def _entry(parent: str, child: str, value: float, expression: str, *, status: str = "HOLD") -> dict:
    return {"parent_claim_id": parent, "claim_id": child, "claim": {"value": value}, "lineage_record": {"target_expression": expression}, "terminal_status": status, "reason_code": "NO_HARD_GUARD_CANDIDATE", "official_resolution": None}


def test_compiler_selects_exact_lineage_child_from_split_parent() -> None:
    results = compile_recovered_official_results([_ledger("P1", "20", "20만명")], [_entry("P1", "C1", 10, "10만명"), _entry("P1", "C2", 20, "20만명")], expected_count=1)
    assert results[0].selected_claim_id == "C2"
    assert results[0].child_count == 2


def test_compiler_uses_numeric_target_when_lineage_is_normalized() -> None:
    results = compile_recovered_official_results([_ledger("P1", "127800000000", "1278억달러")], [_entry("P1", "C1", 683600000000, "6.836e+11달러"), _entry("P1", "C2", 127800000000, "1.278e+11달러")], expected_count=1)
    assert results[0].selected_claim_id == "C2"


def test_kosis_value_plus_verified_official_document_counts_as_complete() -> None:
    entry = _entry("P1", "C1", 20, "20만명", status="AUTO")
    entry["reason_code"] = "WITHIN_TOLERANCE"
    entry["official_resolution"] = {"candidates": [{}], "verdict": {"verdict": "MATCH", "calculated_value": 20, "evidence_cells": [{"canonical_key": "E1"}], "official_value_provenance": [{"evidence_key": "E1", "source": "API", "source_url": "https://kosis.kr/value", "content_hash": "api", "retrieved_at": "2026-08-28T00:00:00Z", "publication": {"status": "UNRESOLVED"}}, {"evidence_key": "DOC:1", "source": "OFFICIAL_DOCUMENT", "source_url": "https://official.example/doc", "content_hash": "doc", "retrieved_at": "2026-08-28T00:00:01Z", "publication": {"status": "VERIFIED"}}]}}
    results = compile_recovered_official_results([_ledger("P1", "20", "20만명")], [entry], expected_count=1)
    summary = summarize_recovered_official_results(results)
    assert results[0].official_complete is True
    assert results[0].official_path == "KOSIS_API_VALUE_PLUS_OFFICIAL_DOCUMENT"
    assert summary["official_complete_count"] == 1


def test_unverified_or_unkeyed_provenance_is_not_complete() -> None:
    entry = _entry("P1", "C1", 20, "20만명", status="AUTO")
    entry["official_resolution"] = {"verdict": {"verdict": "MATCH", "evidence_cells": [{"canonical_key": "E1"}], "official_value_provenance": [{"evidence_key": "OTHER", "source": "API", "source_url": "https://kosis.kr", "content_hash": "abc", "retrieved_at": "2026-08-28", "publication": {"status": "VERIFIED"}}]}}
    result = compile_recovered_official_results([_ledger("P1", "20", "20만명")], [entry], expected_count=1)[0]
    assert result.official_complete is False
