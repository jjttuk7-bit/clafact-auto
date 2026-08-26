from tools.compile_direct_value_generalization_results import extract_improvement


def test_extracts_strict_official_result_and_general_rule_ids():
    row = {
        "terminal_status": "AUTO", "reason_code": "WITHIN_TOLERANCE",
        "claim": {"indicator": "총인구", "source_sentence": "출생자 수는 10명이었다."},
        "official_resolution": {
            "concept": {"canonical_name": "출생아 수", "matched_alias": "출생자 수"},
            "candidates": [{"source_stat_id": "OFFICIAL_STRUCTURAL_COORDINATE_RULE"}],
            "verdict": {
                "route_status": "AUTO", "verdict": "MATCH", "calculated_value": 10,
                "evidence_cells": [],
                "official_value_provenance": [{
                    "source": "OFFICIAL_DOCUMENT", "source_url": "https://official.example/x",
                    "content_hash": "abc", "retrieved_at": "2026-01-01T00:00:00Z",
                    "publication": {"status": "VERIFIED"},
                }],
                "execution_trace": {"events": [{"stage": "VERDICT", "status": "PASS"}]},
            },
        },
    }
    result = extract_improvement(row)
    assert result["공식판정완료"] == "Y"
    assert result["판정"] == "MATCH"
    assert result["공식값"] == "10"
    assert "STRUCTURAL_COORDINATE_UNIQUE_V1" in result["규칙ID"]
    assert "SOURCE_GROUNDED_INDICATOR_V1" in result["규칙ID"]
