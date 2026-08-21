from __future__ import annotations

import json
from datetime import date

from core.admission_recovery_v3 import recover_registry_record_v3
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


class _Extractor:
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


class _Service:
    def __init__(self) -> None:
        self.claims: list[ClaimSchema] = []

    def resolve(self, claim, *, article_date):
        self.claims.append(claim)
        return {"route_status": "AUTO"}


def test_v3_creates_one_12_slot_child_per_statistical_target_and_reenters_official_service() -> None:
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
    service = _Service()

    result = recover_registry_record_v3(
        record, extractor=_Extractor(), official_service=service
    )

    assert result.recovery_action == "MULTI_CLAIM_SPLIT"
    assert [entry.record.claim.value for entry in result.entries] == [378000, 12000]
    assert len({entry.record.claim.claim_id for entry in result.entries}) == 2
    assert all(entry.record.claim.source_sentence == source for entry in result.entries)
    assert len(service.claims) == 2
