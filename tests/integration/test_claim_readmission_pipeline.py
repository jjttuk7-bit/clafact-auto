from __future__ import annotations

from datetime import date
import json

from core.pipeline_run_reporting import serialize_pipeline_entry
from core.unified_claim_pipeline import verify_registry_record
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


class _TargetExtractor:
    def extract(self, source_sentence: str, *, article_published_at=None) -> ClaimSchema:
        payload = json.loads(source_sentence)
        expression = payload["target_numeric_expression"]
        value = 378000 if expression == "37만8000명" else 12000
        return ClaimSchema(
            claim_id="temporary",
            source_sentence=source_sentence,
            indicator="쉬었음 인구",
            value=value,
            unit="명",
            time="2025년 2월",
            frequency="월",
            calculation="DIRECT_VALUE" if value == 378000 else "DIFFERENCE",
            comparison=(
                None
                if value == 378000
                else {
                    "type": "YEAR_OVER_YEAR",
                    "current_value": "378000",
                    "reference_value": "366000",
                    "operand_unit": "명",
                }
            ),
            condition=None if value == 378000 else {"direction": "INCREASE"},
            parse_status="AUTO_OK",
        )


class _OfficialService:
    def __init__(self) -> None:
        self.claims: list[ClaimSchema] = []

    def resolve(self, claim: ClaimSchema, *, article_date: date) -> dict[str, str]:
        self.claims.append(claim)
        return {"route_status": "AUTO", "reason_code": "WITHIN_TOLERANCE"}


def test_split_children_keep_lineage_and_stage_results_and_reenter_official_service() -> None:
    source = "20대 쉬었음 인구는 37만8000명으로 전년 동월 대비 1만2000명 늘었다."
    record = ClaimRegistryRecord(
        article_id="A1",
        sentence_id="1",
        article_published_at=date(2025, 3, 12),
        source_ref="registry",
        claim=ClaimSchema(
            claim_id="parent",
            source_sentence=source,
            parse_status="HOLD",
            parse_reason="MULTI_CLAIM_SPLIT_REQUIRED",
        ),
    )
    service = _OfficialService()

    entries = verify_registry_record(
        record,
        extractor=_TargetExtractor(),
        official_service=service,
    )

    assert len(entries) == 2
    assert len(service.claims) == 2
    assert [entry.lineage_record.child_ordinal for entry in entries] == [1, 2]
    assert {entry.lineage_record.parent_claim_id for entry in entries} == {"parent"}
    assert len({entry.lineage_record.child_claim_id for entry in entries}) == 2
    assert all(
        [event.stage for event in entry.stage_results]
        == ["CLAIM_SPLIT", "CLAIM_PARSE"]
        for entry in entries
    )
    serialized = serialize_pipeline_entry(record, entries[0])
    assert serialized["lineage_record"]["parent_claim_id"] == "parent"
    assert serialized["stage_results"][0]["stage"] == "CLAIM_SPLIT"


def test_pre_official_context_gap_is_human_review_not_official_hold() -> None:
    record = ClaimRegistryRecord(
        article_id="A2",
        sentence_id="1",
        article_published_at=date(2025, 3, 12),
        source_ref="registry",
        claim=ClaimSchema(
            claim_id="context-parent",
            source_sentence="지난달 고용률은 증가했다.",
            parse_status="HOLD",
            parse_reason="SOURCE_CONTEXT_UNCLEAR",
        ),
    )
    service = _OfficialService()

    entries = verify_registry_record(
        record,
        extractor=_TargetExtractor(),
        official_service=service,
        article_context=None,
    )

    assert len(entries) == 1
    assert entries[0].terminal_status == "HUMAN_REVIEW"
    assert entries[0].reason_code == "SOURCE_CONTEXT_UNCLEAR"
    assert entries[0].official_resolution is None
    assert service.claims == []
    assert entries[0].stage_results[-1].status == "HUMAN_REVIEW"
