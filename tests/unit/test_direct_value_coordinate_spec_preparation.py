from datetime import date

from core.direct_value_coordinate_spec_preparation import prepare_coordinate_spec
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


def _record(*, grounded: bool = True, **updates) -> ClaimRegistryRecord:
    claim = {
        "claim_id": "C1",
        "source_sentence": "2024년 전국 취업자는 2800만 명이다.",
        "indicator": "취업자 수",
        "value": 28_000_000,
        "unit": "명",
        "time": "2024",
        "frequency": "Y",
        "region": "전국",
        "calculation": "DIRECT_VALUE",
        "parse_status": "AUTO_OK",
    }
    claim.update(updates)
    enrichment = None
    if grounded:
        source = str(claim["source_sentence"])
        expression = "2800만 명"
        start = source.index(expression)
        enrichment = {
            "target_link_status": "SOURCE_GROUNDED",
            "target_numeric_expression": expression,
            "target_numeric_start": start,
            "target_numeric_end": start + len(expression),
            "target_numeric_role": "대상값",
        }
    return ClaimRegistryRecord(
        article_id="A1",
        sentence_id="1",
        article_published_at=date(2025, 1, 10),
        source_ref="test",
        claim=ClaimSchema(**claim),
        slot_enrichment=enrichment,
    )


def test_preparation_reuses_pipeline_guards_and_returns_ready_record() -> None:
    prepared = prepare_coordinate_spec(_record())

    assert prepared.spec.readiness_status == "COORDINATE_READY"
    assert prepared.record.claim.parse_status == "AUTO_OK"
    assert prepared.target_expression == "2800만 명"


def test_preparation_fails_before_catalog_without_source_grounding() -> None:
    prepared = prepare_coordinate_spec(_record(grounded=False))

    assert prepared.spec.readiness_status == "PRE_VERIFICATION"
    assert "TARGET_NOT_SOURCE_GROUNDED" in prepared.spec.readiness_reasons


def test_preparation_does_not_relabel_change_amount_as_direct_value() -> None:
    record = _record(
        source_sentence="2024년 전국 취업자는 2800만 명 증가했다.",
        calculation="DIRECT_VALUE",
    )
    source = record.claim.source_sentence
    start = source.index("2800만 명")
    record = record.model_copy(update={"slot_enrichment": {
        "target_link_status": "SOURCE_GROUNDED",
        "target_numeric_expression": "2800만 명",
        "target_numeric_start": start,
        "target_numeric_end": start + len("2800만 명"),
        "target_numeric_role": "대상값",
    }})

    prepared = prepare_coordinate_spec(record)

    assert prepared.spec.readiness_status == "PRE_VERIFICATION"
    assert "RECLASSIFY_TO_DIFFERENCE" in prepared.spec.readiness_reasons
