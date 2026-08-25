import json
from datetime import date

from core.admission_recovery_v3 import recover_registry_record_v3
from core.unified_claim_pipeline import verify_registry_record
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


def _claim() -> ClaimSchema:
    return ClaimSchema(
        claim_id="parent",
        source_sentence="20대 인구는 2020년 703만명이다.",
        indicator="인구",
        value=7_030_000,
        unit="명",
        time="2020",
        frequency="Y",
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )


class Extractor:
    def __init__(self) -> None:
        self.inputs: list[str] = []

    def extract(self, source_sentence: str, **kwargs: object) -> ClaimSchema:
        self.inputs.append(source_sentence)
        return _claim()

    def group_claims(self, source_sentence: str, mentions: object) -> object:
        raise AssertionError("trusted target must bypass regrouping")


class Resolver:
    def __init__(self) -> None:
        self.calls = 0

    def resolve(self, claim: ClaimSchema, *, article_date: date) -> dict[str, object]:
        self.calls += 1
        return {"route_status": "AUTO", "reason_code": None}


def test_prelinked_target_bypasses_regrouping_and_drives_recovery() -> None:
    extractor = Extractor()
    resolver = Resolver()
    record = ClaimRegistryRecord(
        article_id="A02624",
        sentence_id="7",
        article_published_at=date(2025, 1, 1),
        source_ref="grounded",
        claim=_claim(),
        slot_enrichment={
            "target_link_status": "SOURCE_GROUNDED",
            "target_numeric_expression": "703만명",
            "target_numeric_mention_id": "n3",
            "target_numeric_role": "대상값",
            "target_numeric_start": 14,
            "target_numeric_end": 19,
        },
    )

    result = recover_registry_record_v3(
        record,
        extractor=extractor,
        official_service=resolver,
    )

    assert len(result.entries) == 1
    assert json.loads(extractor.inputs[0])["target_numeric_expression"] == "703만명"
    assert result.entries[0].record.slot_enrichment["target_numeric_expression"] == "703만명"


def test_unlinked_enriched_record_stops_before_official_lookup() -> None:
    resolver = Resolver()
    record = ClaimRegistryRecord(
        article_id="A02624",
        sentence_id="7",
        article_published_at=date(2025, 1, 1),
        source_ref="grounded",
        claim=_claim(),
        slot_enrichment={
            "target_link_status": "TARGET_CONTEXT_ROLE_CONFLICT",
            "target_link_reason_code": "TARGET_CONTEXT_ROLE_CONFLICT",
        },
    )

    entries = verify_registry_record(
        record,
        extractor=Extractor(),
        official_service=resolver,
    )

    assert len(entries) == 1
    assert entries[0].terminal_status == "HUMAN_REVIEW"
    assert entries[0].reason_code == "TARGET_CONTEXT_ROLE_CONFLICT"
    assert resolver.calls == 0
