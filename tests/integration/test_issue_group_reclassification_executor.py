from __future__ import annotations

from datetime import date

from core.issue_group_executor import ContextGroupExecutor
from core.issue_group_harness import IssueGroup, build_issue_registry, run_group_slice
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


class _ForecastExtractor:
    def extract(self, source_sentence: str, *, article_published_at=None) -> ClaimSchema:
        return ClaimSchema(
            claim_id="parsed",
            source_sentence=source_sentence,
            indicator="consumer price growth",
            value=1.8,
            unit="%",
            time="2025",
            frequency="Y",
            calculation="DIRECT_VALUE",
            parse_status="AUTO_OK",
        )


def test_context_executor_reclassifies_forecast_without_official_lookup() -> None:
    sentence = "정부는 소비자 물가 상승률을 1.8%로 내다봤다."
    record = ClaimRegistryRecord(
        article_id="A-1",
        sentence_id="1",
        article_published_at=date(2025, 1, 2),
        source_ref="test",
        claim=ClaimSchema(
            claim_id="C-1",
            source_sentence=sentence,
            parse_status="HOLD",
            parse_reason="CONTEXT_REQUIRED",
        ),
    )
    baseline = build_issue_registry(
        [
            {
                "article_id": "A-1",
                "sentence_id": "1",
                "parent_claim_id": "C-1",
                "claim_id": "C-1",
                "source_sentence": sentence,
                "terminal_status": "HUMAN_REVIEW",
                "reason_code": "CONTEXT_REQUIRED",
                "claim": {"claim_id": "C-1"},
                "slot_audit": {"entries": []},
                "stage_results": [],
                "official_resolution": None,
            }
        ]
    )

    result = run_group_slice(
        baseline,
        IssueGroup.CONTEXT,
        ContextGroupExecutor([record], extractor=_ForecastExtractor()),
        limit=1,
    )[0]

    assert result["status"] == "RECLASSIFIED"
    assert result["reason_code"] == "PRE_VERIFICATION_RECLASSIFIED"
    assert result["official_lookup_attempted"] is False
    assert result["children"][0]["disposition"] == "FORECAST_OR_POLICY"
