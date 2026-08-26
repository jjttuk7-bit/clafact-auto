import json
from datetime import date

from core.admission_recovery_v3 import recover_registry_record_v3
from core.unified_claim_pipeline import verify_registry_record
from schemas.claim import ClaimSchema
from schemas.claim_group import ClaimGroupingPlan
from schemas.claim_registry import ClaimRegistryRecord


SOURCE = "실업률은 4% 수준이고, 작년 12월에는 일자리 25만개가 새로 만들어졌다."


class GroupingExtractor:
    def __init__(self) -> None:
        self.group_calls = 0

    def group_claims(self, source_sentence: str, mentions: object) -> ClaimGroupingPlan:
        self.group_calls += 1
        return ClaimGroupingPlan.model_validate(
            {
                "status": "READY",
                "assignments": [
                    {"mention_id": "n1", "role": "MAIN_VALUE", "group_id": "g1"},
                    {"mention_id": "n2", "role": "MAIN_VALUE", "group_id": "g2"},
                ],
                "groups": [
                    {"group_id": "g1", "main_mention_id": "n1"},
                    {"group_id": "g2", "main_mention_id": "n2"},
                ],
            }
        )

    def extract(self, source_sentence: str, **kwargs: object) -> ClaimSchema:
        expression = json.loads(source_sentence)["target_numeric_expression"]
        if expression == "4%":
            indicator, value, unit = "실업률", 4.0, "%"
        else:
            indicator, value, unit = "신규 일자리 수", 250_000.0, "개"
        return ClaimSchema(
            claim_id="temporary",
            source_sentence=source_sentence,
            indicator=indicator,
            value=value,
            unit=unit,
            time="2024년 12월",
            frequency="월",
            calculation="DIRECT_VALUE",
            parse_status="AUTO_OK",
        )


class Resolver:
    def __init__(self) -> None:
        self.claims: list[ClaimSchema] = []

    def resolve(self, claim: ClaimSchema, *, article_date: date) -> dict[str, object]:
        self.claims.append(claim)
        return {"route_status": "AUTO", "reason_code": None}


def record(*, indicator_status: str = "COMPATIBLE") -> ClaimRegistryRecord:
    return ClaimRegistryRecord(
        article_id="A1",
        sentence_id="1",
        article_published_at=date(2025, 1, 1),
        source_ref="direct_value_audit",
        claim=ClaimSchema(
            claim_id="parent",
            source_sentence=SOURCE,
            indicator="실업률",
            value=4.0,
            unit="%",
            time="2024년 12월",
            frequency="월",
            calculation="DIRECT_VALUE",
            parse_status="AUTO_OK",
        ),
        slot_enrichment={
            "target_link_status": "SOURCE_GROUNDED",
            "target_numeric_expression": "4%",
            "target_numeric_start": 5,
            "target_numeric_end": 7,
            "indicator_unit_status": indicator_status,
            "indicator_unit_reason_code": "INDICATOR_UNIT_MEASURE_MISMATCH",
            "sign_direction_status": "NOT_APPLICABLE_LEVEL_VALUE",
        },
    )


def test_prelinked_target_does_not_hide_independent_sibling_claim() -> None:
    extractor = GroupingExtractor()
    resolver = Resolver()

    result = recover_registry_record_v3(
        record(), extractor=extractor, official_service=resolver
    )

    assert extractor.group_calls == 1
    assert len(result.entries) == 2
    assert {
        entry.record.slot_enrichment["target_numeric_expression"]
        for entry in result.entries
    } == {"4%", "25만개"}
    assert len(resolver.claims) == 2


def test_parent_indicator_conflict_cannot_block_valid_children_before_split() -> None:
    extractor = GroupingExtractor()
    resolver = Resolver()

    entries = verify_registry_record(
        record(indicator_status="INDICATOR_UNIT_CONFLICT"),
        extractor=extractor,
        official_service=resolver,
    )

    assert extractor.group_calls == 1
    assert len(entries) == 2
    assert {entry.claim.indicator for entry in entries} == {"실업률", "신규 일자리 수"}
    assert len(resolver.claims) == 2
