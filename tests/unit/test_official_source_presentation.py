from core.official_source_presentation import build_official_source_presentation
from core.verdict_engine import make_verdict
from schemas.evidence import EvidenceCellSchema
from schemas.verdict import OfficialValueProvenanceSchema


def _document_provenance() -> OfficialValueProvenanceSchema:
    return OfficialValueProvenanceSchema(
        evidence_key="OFFICIAL_TRADE_RELEASE:관세청:2025-01-01/2025-02-20",
        source="OFFICIAL_DOCUMENT",
        source_url="https://www.customs.go.kr/release/1",
        retrieved_at="2026-08-25T00:00:00Z",
        content_hash="a" * 64,
    )


def test_labels_document_only_value_as_official_author_document() -> None:
    verdict = make_verdict("c1", -10.0, [-10.0], -10.0).model_copy(update={
        "official_value_provenance": [_document_provenance()],
    })

    presentation = build_official_source_presentation(verdict)

    assert presentation.value_label == "공식 작성기관 문서값"
    assert presentation.evidence_label == "공식 작성기관 문서 근거"
    assert presentation.evidence_count == 1
    assert presentation.provenance_rows[0]["출처 URL"] == "https://www.customs.go.kr/release/1"


def test_prefers_kosis_value_label_when_evidence_coordinate_exists() -> None:
    cell = EvidenceCellSchema(
        org_id="134",
        tbl_id="DT_134001_001",
        itm_id="T005",
        prd_se="M",
        prd_de="2025-02",
        unit="천불",
        canonical_key="ORG=134|TBL=DT_134001_001|ITM=T005|PRD_DE=2025-02",
        status="CONFIRMED",
    )
    verdict = make_verdict("c2", -10.0, [-10.0], -10.0).model_copy(update={
        "evidence_cells": [cell],
        "official_value_provenance": [_document_provenance()],
    })

    presentation = build_official_source_presentation(verdict)

    assert presentation.value_label == "KOSIS 공식값"
    assert presentation.evidence_label == "KOSIS 공식 근거"
    assert presentation.evidence_count == 1
