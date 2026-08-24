from __future__ import annotations

from datetime import date

from core.issue_group_executor import ContextGroupExecutor, build_article_contexts
from core.issue_group_harness import IssueGroup, build_issue_registry, run_group_slice
from schemas.claim import ClaimSchema
from schemas.claim_group import ClaimGroupingPlan
from schemas.claim_registry import ClaimRegistryRecord


class _Extractor:
    def extract(self, source_sentence: str, *, article_published_at=None) -> ClaimSchema:
        return ClaimSchema(
            claim_id="parsed",
            source_sentence=source_sentence,
            indicator="취업자 수",
            value=100000,
            unit="명",
            time="2025-01",
            frequency="M",
            calculation="DIRECT_VALUE",
            parse_status="AUTO_OK",
        )


class _DuplicateGroupingExtractor(_Extractor):
    def group_claims(self, source_sentence, mentions):
        return ClaimGroupingPlan.model_validate({
            "status": "READY",
            "assignments": [
                {"mention_id": "n1", "role": "MAIN_VALUE", "group_id": "g1"},
                {"mention_id": "n2", "role": "REFERENCE_VALUE", "group_id": "g1"},
                {"mention_id": "n2", "role": "REFERENCE_VALUE", "group_id": "g1"},
            ],
            "groups": [{"group_id": "g1", "main_mention_id": "n1"}],
        })


def test_context_executor_reconstructs_article_context_and_stops_before_official_lookup() -> None:
    records = [
        _record("C-001", "1", "첫 문장이다."),
        _record("C-002", "2", "취업자는 10만 명이다."),
    ]
    contexts = build_article_contexts(records)
    assert contexts == {"A-001": "첫 문장이다.\n취업자는 10만 명이다."}
    baseline = build_issue_registry([_baseline_row()])
    executor = ContextGroupExecutor(records, extractor=_Extractor())

    results = run_group_slice(
        baseline,
        IssueGroup.CONTEXT,
        executor,
        limit=1,
    )

    assert results[0]["executed_stages"] == ["CLAIM_SPLIT", "CLAIM_PARSE"]
    assert results[0]["status"] == "PASS"
    assert results[0]["reason_code"] == "KOSIS_PIPELINE_ELIGIBLE"
    assert results[0]["official_lookup_attempted"] is False
    assert results[0]["children"][0]["twelve_slot_complete"] is True


def test_grouping_hold_is_reported_as_parent_review_not_as_recovered_child() -> None:
    records = [
        _record("C-001", "1", "첫 문장이다."),
        _record("C-002", "2", "취업자는 10만명이고 기준값은 9만명이다."),
    ]
    baseline = build_issue_registry([{
        **_baseline_row(),
        "source_sentence": "취업자는 10만명이고 기준값은 9만명이다.",
    }])
    executor = ContextGroupExecutor(records, extractor=_DuplicateGroupingExtractor())

    result = run_group_slice(baseline, IssueGroup.CONTEXT, executor, limit=1)[0]

    assert result["status"] == "HUMAN_REVIEW"
    assert result["reason_code"] == "GROUPING_DUPLICATE_ASSIGNMENT"
    assert result["child_count"] == 0
    assert result["children"] == []
    assert result["stop_stage"] == "CLAIM_SPLIT"


def _record(claim_id: str, sentence_id: str, sentence: str) -> ClaimRegistryRecord:
    return ClaimRegistryRecord(
        article_id="A-001",
        sentence_id=sentence_id,
        article_published_at=date(2025, 2, 1),
        source_ref="test",
        claim=ClaimSchema(
            claim_id=claim_id,
            source_sentence=sentence,
            indicator="취업자 수",
            value=100000,
            unit="명",
            time="2025-01",
            frequency="M",
            calculation="DIRECT_VALUE",
            parse_status="HOLD" if claim_id == "C-002" else "AUTO_OK",
            parse_reason="CONTEXT_REQUIRED" if claim_id == "C-002" else None,
        ),
    )


def _baseline_row() -> dict[str, object]:
    return {
        "article_id": "A-001",
        "sentence_id": "2",
        "parent_claim_id": "C-002",
        "claim_id": "C-002",
        "source_sentence": "취업자는 10만 명이다.",
        "terminal_status": "HUMAN_REVIEW",
        "reason_code": "CONTEXT_REQUIRED",
        "claim": {"claim_id": "C-002"},
        "slot_audit": {"entries": []},
        "stage_results": [],
        "official_resolution": None,
    }
