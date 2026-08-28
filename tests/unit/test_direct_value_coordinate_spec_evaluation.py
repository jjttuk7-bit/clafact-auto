from core.direct_value_coordinate_spec_evaluation import compile_coordinate_evaluation


def test_evaluation_keeps_one_row_per_scope_and_stage_counts() -> None:
    scope = {
        "C1": {"source_sentence": "값은 1명이다.", "current_reason": "OLD_A", "split_set": "RULE_DISCOVERY"},
        "C2": {"source_sentence": "값은 2명이다.", "current_reason": "OLD_B", "split_set": "FINAL_BLIND"},
    }
    specs = {
        "C1": {"readiness_status": "PRE_VERIFICATION", "readiness_reasons": ["MISSING_TIME"]},
        "C2": {"readiness_status": "COORDINATE_READY", "readiness_reasons": [], "indicator": "출생아 수"},
    }
    live = [{
        "claim_id": "C2", "parent_claim_id": "C2", "terminal_status": "AUTO", "terminal_reason": None,
        "official_resolution": {"candidate_count": 1, "catalog_diagnostics": {
            "metadata_itm_attempted": 1, "metadata_itm_succeeded": 1,
            "metadata_prd_attempted": 1, "metadata_prd_succeeded": 1,
        }, "verdict": {
            "route_status": "AUTO", "verdict": "MATCH", "reason_code": None,
            "evidence_cells": [{"canonical_key": "K1"}], "evidence_values": [2.0],
            "official_value_provenance": [{
                "evidence_key": "K1", "source": "API", "source_url": "https://kosis.kr/x",
                "content_hash": "abc", "retrieved_at": "2026-08-28T00:00:00Z",
                "publication": {"status": "VERIFIED"},
            }],
            "execution_trace": {"events": [
                {"stage": "SEMANTIC_MAPPING", "status": "PASS"},
                {"stage": "CATALOG_SEARCH", "status": "PASS"},
                {"stage": "HARD_GUARD", "status": "PASS"},
                {"stage": "EVIDENCE_CELL", "status": "PASS"},
                {"stage": "OFFICIAL_VALUE_FETCH", "status": "PASS"},
                {"stage": "VERDICT", "status": "PASS"},
            ]},
        }},
    }]

    evaluation = compile_coordinate_evaluation(scope, specs, live)

    assert len(evaluation.rows) == 2
    assert evaluation.summary["scope_count"] == 2
    assert evaluation.summary["coordinate_ready_count"] == 1
    assert evaluation.summary["catalog_pass_count"] == 1
    assert evaluation.summary["metadata_pass_count"] == 1
    assert evaluation.summary["strict_official_complete_count"] == 1
    assert evaluation.rows[0]["최종실패단계"] == "사전 구조화"


def test_preverification_claim_cannot_be_counted_complete_from_stale_live_result() -> None:
    scope = {"C1": {"source_sentence": "청년 실업률은 5.9%다.", "current_reason": "OLD", "split_set": "RULE_DISCOVERY"}}
    specs = {"C1": {"readiness_status": "PRE_VERIFICATION", "readiness_reasons": ["SOURCE_TARGET_DIMENSION_MISSING:청년"]}}
    live = [{
        "claim_id": "C1", "parent_claim_id": "C1", "official_resolution": {"verdict": {
            "route_status": "AUTO", "verdict": "MISMATCH",
            "evidence_cells": [{"canonical_key": "K1"}],
            "official_value_provenance": [{
                "evidence_key": "K1", "source": "API", "source_url": "https://kosis.kr/x",
                "content_hash": "abc", "retrieved_at": "2026-08-28T00:00:00Z",
                "publication": {"status": "VERIFIED"},
            }],
        }},
    }]

    evaluation = compile_coordinate_evaluation(scope, specs, live)

    assert evaluation.rows[0]["엄격공식판정완료"] == "N"
    assert evaluation.summary["strict_official_complete_count"] == 0
