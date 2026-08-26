import json
from datetime import date

from core.direct_value_multi_claim_scope import DirectValueMultiClaimCase
from core.unified_claim_pipeline import PipelineEntry
from schemas.claim import ClaimSchema
from tools.run_direct_value_multi_claim_scope import (
    _record_from_case,
    _serialize_entry,
)


def case() -> DirectValueMultiClaimCase:
    source = "실업률은 4%이고 일자리는 25만개 늘었다."
    return DirectValueMultiClaimCase(
        parent_claim_id="C1",
        source_sentence=source,
        expressions=("4%", "25만개"),
        source_row={
            "Claim번호": "C1",
            "기사번호": "A1",
            "문장번호": "7",
            "기사작성일": "2025-01-15",
            "지표": "실업률",
            "기사값": "4",
            "단위": "%",
            "기준시점": "2024-12",
            "주기": "M",
            "지역": "",
            "대상집단": "",
            "차원": "",
            "비교조건": "",
            "계산방식": "DIRECT_VALUE",
            "조건": "",
            "출처힌트": "",
            "숫자역할파이프라인보강JSON": json.dumps(
                {
                    "target_link_status": "SOURCE_GROUNDED",
                    "target_numeric_expression": "4%",
                    "target_numeric_start": 5,
                    "target_numeric_end": 7,
                }
            ),
        },
    )


def test_reconstructs_registry_parent_without_losing_grounding() -> None:
    record = _record_from_case(case())

    assert record.article_id == "A1"
    assert record.sentence_id == "7"
    assert record.article_published_at == date(2025, 1, 15)
    assert record.claim.claim_id == "C1"
    assert record.claim.value == 4.0
    assert record.slot_enrichment["target_numeric_expression"] == "4%"


def test_serializes_child_lineage_and_official_result() -> None:
    child = ClaimSchema(
        claim_id="child-1",
        source_sentence=case().source_sentence,
        indicator="실업률",
        value=4.0,
        unit="%",
        time="2024년 12월",
        frequency="월",
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )
    entry = PipelineEntry(
        parent_claim_id="C1",
        claim=child,
        recovery_action="MULTI_CLAIM_SPLIT",
        admission_route="KOSIS_PIPELINE_ELIGIBLE",
        terminal_status="AUTO",
        reason_code=None,
        official_resolution={"route_status": "AUTO", "reason_code": None},
    )

    payload = _serialize_entry(entry)

    assert payload["parent_claim_id"] == "C1"
    assert payload["child_claim_id"] == "child-1"
    assert payload["claim"]["indicator"] == "실업률"
    assert payload["official_resolution"]["route_status"] == "AUTO"
