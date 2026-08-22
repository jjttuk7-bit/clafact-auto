from __future__ import annotations

from datetime import date
import json

from core.unified_claim_pipeline import verify_registry_record
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


class _Extractor:
    def extract(self, source_sentence: str, **kwargs) -> ClaimSchema:
        payload = json.loads(source_sentence)
        expression = payload.get("target_numeric_expression", "83.5%")
        if "article_context" not in payload:
            return ClaimSchema(
                claim_id="first",
                source_sentence=source_sentence,
                indicator="고용률",
                value=83.5 if expression == "83.5%" else 1.1,
                unit="%" if expression == "83.5%" else "%p",
                calculation="DIRECT_VALUE" if expression == "83.5%" else "DIFFERENCE",
                parse_status="HOLD",
                parse_reason="CLAIM_PARSE_UNCERTAIN",
            )
        return ClaimSchema(
            claim_id="second",
            source_sentence=source_sentence,
            indicator="고용률",
            value=83.5 if expression == "83.5%" else 1.1,
            unit="%" if expression == "83.5%" else "%p",
            time="2024년 하반기",
            frequency="반기",
            region="울릉군",
            calculation="DIRECT_VALUE" if expression == "83.5%" else "DIFFERENCE",
            comparison=(
                None
                if expression == "83.5%"
                else {
                    "type": "YEAR_OVER_YEAR",
                    "current_value": "83.5",
                    "reference_value": "82.4",
                    "operand_unit": "%",
                }
            ),
            condition=None if expression == "83.5%" else {"direction": "INCREASE"},
            parse_status="AUTO_OK",
        )


class _Official:
    def resolve(self, claim: ClaimSchema, *, article_date: date) -> dict[str, str]:
        return {"route_status": "AUTO"}


def test_original_target_expression_and_context_enriched_slots_are_preserved() -> None:
    source = "울릉군 고용률은 83.5%로 1.1%포인트 상승했다."
    record = ClaimRegistryRecord(
        article_id="A1",
        sentence_id="1",
        article_published_at=date(2025, 2, 21),
        source_ref="registry",
        claim=ClaimSchema(
            claim_id="parent",
            source_sentence=source,
            indicator="고용률",
            value=83.5,
            unit="%",
            calculation="DIRECT_VALUE",
            parse_status="HOLD",
            parse_reason="MULTI_CLAIM_SPLIT_REQUIRED",
        ),
    )

    entries = verify_registry_record(
        record,
        extractor=_Extractor(),
        official_service=_Official(),
        article_context="기사 본문에서 대상 시점은 2024년 하반기이며 지역은 울릉군이다.",
    )

    assert [entry.lineage_record.target_expression for entry in entries] == [
        "83.5%",
        "1.1%포인트",
    ]
    assert entries[0].slot_audit.by_slot("region").status == "CONTEXT"
    assert entries[0].slot_audit.by_slot("time").status == "CONTEXT"
    assert entries[0].slot_audit.by_slot("value").status == "SOURCE"
