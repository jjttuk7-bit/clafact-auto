from core.issue_group_harness import build_issue_registry, compare_result


def test_compare_result_reads_canonical_official_pipeline_shape() -> None:
    before = build_issue_registry([
        {
            "article_id": "A-001", "sentence_id": "S-001",
            "parent_claim_id": "C-001", "claim_id": "C-001",
            "source_sentence": "고졸 실업률은 5.5%였다.",
            "terminal_status": "HOLD", "reason_code": "NO_HARD_GUARD_CANDIDATE",
            "claim": {"claim_id": "C-001", "indicator": "실업률"},
            "slot_audit": {"eligible_for_official_search": True, "entries": []},
            "stage_results": [], "official_resolution": None,
        }
    ])[0]
    after = {
        "claim_id": "C-001",
        "terminal_status": "AUTO",
        "reason_code": "OUTSIDE_TOLERANCE",
        "official_resolution": {
            "verdict": {
                "route_status": "AUTO",
                "reason_code": "OUTSIDE_TOLERANCE",
                "execution_trace": {"events": [
                    {"stage": "HARD_GUARD", "status": "PASS", "reason_code": None},
                    {"stage": "VERDICT", "status": "PASS", "reason_code": None},
                ]},
                "evidence_cells": [{"tbl_id": "DT_1DA7003S"}],
                "official_value_provenance": [{
                    "source": "API", "source_url": "https://kosis.kr/openapi/example",
                }],
            }
        },
    }

    comparison = compare_result(before, after)

    assert comparison.after_status == "AUTO"
    assert comparison.after_stage == "VERDICT"
    assert comparison.after_reason == "OUTSIDE_TOLERANCE"
    assert comparison.outcome == "RESOLVED"
    assert comparison.official_evidence is True
    assert comparison.table_id == "DT_1DA7003S"
    assert comparison.source_url == "https://kosis.kr/openapi/example"
