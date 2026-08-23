from core.issue_group_harness import build_issue_registry, compare_result


def test_admission_pass_at_same_stage_counts_as_improvement() -> None:
    before = build_issue_registry(
        [
            {
                "article_id": "A-001",
                "sentence_id": "1",
                "parent_claim_id": "C-001",
                "claim_id": "C-001",
                "source_sentence": "취업자는 10만 명이다.",
                "terminal_status": "HUMAN_REVIEW",
                "reason_code": "CONTEXT_REQUIRED",
                "claim": {"claim_id": "C-001"},
                "slot_audit": {"entries": []},
                "stage_results": [],
                "official_resolution": None,
            }
        ]
    )[0]

    compared = compare_result(
        before,
        {
            "claim_id": "C-001",
            "status": "PASS",
            "reason_code": "KOSIS_PIPELINE_ELIGIBLE",
            "stop_stage": "CLAIM_PARSE",
        },
    )

    assert compared.outcome == "IMPROVED"
