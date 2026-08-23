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


class _IndexExtractor:
    def extract(self, source_sentence: str, *, article_published_at=None) -> ClaimSchema:
        expression = json.loads(source_sentence)["target_numeric_expression"]
        is_index = expression.startswith("116.31")
        return ClaimSchema(
            claim_id="temporary",
            source_sentence=source_sentence,
            indicator="\uc18c\ube44\uc790\ubb3c\uac00\uc9c0\uc218" if is_index else "\uc18c\ube44\uc790\ubb3c\uac00 \uc0c1\uc2b9\ub960",
            value=116.31 if is_index else 2.2,
            unit="2020=100" if is_index else "%",
            time="2025\ub144 1\uc6d4",
            frequency="\uc6d4",
            calculation="DIRECT_VALUE",
            parse_status="AUTO_OK",
        )


def test_v3_preserves_index_basis_and_admits_the_index_child() -> None:
    source = (
        "\uc9c0\ub09c\ub2ec \uc18c\ube44\uc790\ubb3c\uac00\uc9c0\uc218\ub294 116.31(2020\ub144=100)\ub85c "
        "\uc791\ub144 \ub3d9\uc6d4 \ub300\ube44 2.2% \uc62c\ub790\ub2e4."
    )
    record = ClaimRegistryRecord(
        article_id="A2",
        sentence_id="1",
        article_published_at=date(2025, 2, 1),
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
        record, extractor=_IndexExtractor(), official_service=service
    )

    assert result.entries[0].record.slot_enrichment["target_numeric_expression"] == "116.31(2020\ub144=100)"
    assert result.entries[0].record.claim.unit == "2020=100"
    assert result.entries[0].admission_route == "KOSIS_PIPELINE_ELIGIBLE"
    assert len(service.claims) == 2
