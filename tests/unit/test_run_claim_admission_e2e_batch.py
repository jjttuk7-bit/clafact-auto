from datetime import date

from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord
from tools.run_claim_admission_e2e_batch import build_child_parser, build_context_reparser, build_report


def test_report_separates_admission_outcomes_from_official_holds() -> None:
    report = build_report([
        {
            "admission_label": "KOSIS_PIPELINE_ELIGIBLE",
            "route_status": "AUTO",
            "verdict": "MATCH",
            "reason_code": "WITHIN_TOLERANCE",
        },
        {
            "admission_label": "CONTEXT_REQUIRED",
            "route_status": "ADMISSION_ROUTED",
            "verdict": "UNDETERMINED",
            "reason_code": "MISSING_TIME_CONTEXT",
        },
        {
            "admission_label": "KOSIS_PIPELINE_ELIGIBLE",
            "route_status": "HOLD",
            "verdict": "UNDETERMINED",
            "reason_code": "CONCEPT_NOT_FOUND",
        },
    ])

    assert report["admission_counts"] == {
        "CONTEXT_REQUIRED": 1,
        "KOSIS_PIPELINE_ELIGIBLE": 2,
    }
    assert report["official_route_counts"] == {"AUTO": 1, "HOLD": 1}
    assert report["admission_routed_count"] == 1
    assert report["official_hold_reason_counts"] == {"CONCEPT_NOT_FOUND": 1}

class _ContextCapturingExtractor:
    def __init__(self) -> None:
        self.context: str | None = None

    def extract(self, source_sentence: str, *, article_published_at=None, article_context=None) -> ClaimSchema:
        self.context = article_context
        return ClaimSchema(
            claim_id="model", source_sentence=source_sentence, indicator="재배 면적",
            value=2.0, unit="ha", time="2025-10", calculation="DIRECT_VALUE", parse_status="AUTO_OK",
        )


def test_split_child_parser_uses_parent_sentence_context() -> None:
    record = ClaimRegistryRecord(
        article_id="A1", sentence_id="1", article_published_at=date(2025, 10, 2), source_ref="test",
        claim=ClaimSchema(claim_id="A1_1", source_sentence="올해 재배 면적은 10ha로 전년보다 2ha 감소했다.", parse_status="AUTO_OK"),
    )
    extractor = _ContextCapturingExtractor()
    parser = build_child_parser(extractor, {"A1": {"title": "재배 면적", "body": "앞. 올해 재배 면적은 10ha로 전년보다 2ha 감소했다. 뒤."}})

    child = parser(record, record.claim, "올해 재배 면적은 10ha이다.", "A1_1__split_1")

    assert child.claim_id == "A1_1__split_1"
    assert extractor.context is not None
    assert "올해 재배 면적은 10ha로 전년보다 2ha 감소했다." in extractor.context

def test_split_child_parser_inherits_only_missing_common_slots_from_parent() -> None:
    class SparseExtractor:
        def extract(self, source_sentence: str, **_kwargs) -> ClaimSchema:
            return ClaimSchema(claim_id="model", source_sentence=source_sentence, value=10.0, unit="ha", calculation="DIRECT_VALUE", parse_status="HOLD", parse_reason="MISSING_REQUIRED_SLOTS:indicator,time")
    parent = ClaimSchema(claim_id="A1_1", source_sentence="원문", indicator="벼 재배 면적", value=12.0, unit="ha", time="2025-10", frequency="M", region="전국", calculation="DIRECT_VALUE", parse_status="AUTO_OK")
    record = ClaimRegistryRecord(article_id="A1", sentence_id="1", article_published_at=date(2025, 10, 2), source_ref="test", claim=parent)
    child = build_child_parser(SparseExtractor(), {})(record, parent, "올해 벼 재배 면적은 10ha이다.", "A1_1__split_1")
    assert child.indicator == "벼 재배 면적"
    assert child.time == "2025-10"
    assert child.value == 10.0
    assert child.parse_status == "AUTO_OK"

def test_context_reparser_keeps_explicit_numeric_slots_for_a_split_child() -> None:
    class MissingNumericExtractor:
        def extract(self, source_sentence: str, **_kwargs) -> ClaimSchema:
            return ClaimSchema(
                claim_id="model", source_sentence=source_sentence,
                indicator="벼 재배 면적", time="올해", parse_status="AUTO_OK",
            )

    parent = ClaimSchema(
        claim_id="A1_1", source_sentence="올해 벼 재배 면적은 67만8000ha이다.",
        indicator="벼 재배 면적", value=678000.0, unit="ha", time="2025년",
        frequency="년", calculation="DIRECT_VALUE", parse_status="AUTO_OK",
    )
    record = ClaimRegistryRecord(
        article_id="A1", sentence_id="1", article_published_at=date(2025, 10, 2),
        source_ref="test", claim=parent,
    )

    reparsed = build_context_reparser(MissingNumericExtractor(), {"A1": {"title": "", "body": parent.source_sentence}})(record, parent)

    assert reparsed.value == 678000.0
    assert reparsed.unit == "ha"
    assert reparsed.calculation == "DIRECT_VALUE"
    assert reparsed.parse_status == "AUTO_OK"