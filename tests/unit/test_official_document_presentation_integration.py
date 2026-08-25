from core.pipeline_trace import PipelineTrace
from core.review_handoff import build_review_payload
from core.trace_presentation import build_trace_summary
from core.verdict_engine import make_verdict
from core.verdict_explainer import build_template_explanation
from schemas.verdict import OfficialValueProvenanceSchema


def _document_verdict():
    provenance = OfficialValueProvenanceSchema(
        evidence_key="OFFICIAL_TRADE_RELEASE:관세청:2025-01-01/2025-02-20",
        source="OFFICIAL_DOCUMENT",
        source_url="https://www.customs.go.kr/release/1",
        retrieved_at="2026-08-25T00:00:00Z",
        content_hash="a" * 64,
    )
    return make_verdict("trade-1", -10.0, [-10.0], -10.0).model_copy(update={
        "official_value_provenance": [provenance],
    })


def test_review_payload_counts_document_provenance_without_kosis_cell() -> None:
    payload = build_review_payload(_document_verdict())

    assert payload.evidence_count == 1


def test_trace_groups_official_author_lookup_under_data_branch() -> None:
    trace = (
        PipelineTrace.for_claim(
            "trade-1", preprocess_version="1.0", claim_schema_version="1.0"
        )
        .pass_stage("OFFICIAL_AUTHOR_SEARCH", output_ref="관세청")
        .pass_stage("OFFICIAL_AUTHOR_FETCH", output_ref="a" * 64)
    )

    summary = build_trace_summary(trace)

    assert [event["stage"] for event in summary["어떤 데이터"]] == [
        "OFFICIAL_AUTHOR_SEARCH",
        "OFFICIAL_AUTHOR_FETCH",
    ]


def test_explanation_names_official_author_document_value() -> None:
    explanation = build_template_explanation(_document_verdict())

    assert "공식 작성기관 문서값" in explanation.summary
    assert "KOSIS 공식값" not in explanation.summary
