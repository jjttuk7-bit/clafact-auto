from __future__ import annotations

from datetime import date

from core.admission_recovery_v2 import recover_registry_record_v2
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


class _Extractor:
    def __init__(self) -> None:
        self.inputs: list[str] = []

    def extract(self, source_sentence: str, *, article_published_at: date | None = None) -> ClaimSchema:
        self.inputs.append(source_sentence)
        return ClaimSchema(
            claim_id="temporary",
            source_sentence=source_sentence,
            indicator="사망자 수",
            value=132600,
            unit="명",
            time="2025년",
            frequency="년",
            calculation="DIRECT_VALUE",
            dimension={"연령": "80대"},
            parse_status="AUTO_OK",
        )


class _Service:
    def __init__(self) -> None:
        self.claims: list[ClaimSchema] = []

    def resolve(self, claim: ClaimSchema, *, article_date: date) -> dict[str, str]:
        self.claims.append(claim)
        return {"route_status": "AUTO"}


def _record(claim: ClaimSchema) -> ClaimRegistryRecord:
    return ClaimRegistryRecord(
        article_id="A1",
        sentence_id="1",
        article_published_at=date(2025, 8, 1),
        source_ref="registry",
        claim=claim,
    )


def test_v2_reparses_an_auto_claim_that_uses_an_age_as_the_claim_value() -> None:
    source = "반면 80대 사망자는 13만2600명으로 전년 대비 400명 줄었다."
    extractor = _Extractor()
    service = _Service()

    result = recover_registry_record_v2(
        _record(ClaimSchema(
            claim_id="bad",
            source_sentence=source,
            indicator="사망자 수",
            value=80,
            unit="대",
            time="2025",
            frequency="Y",
            calculation="DIFFERENCE",
            comparison={"type": "YEAR_OVER_YEAR"},
            parse_status="AUTO_OK",
        )),
        extractor=extractor,
        official_service=service,
    )

    assert extractor.inputs == [source]
    assert result.recovery_action == "SLOT_REPARSE"
    assert service.claims[0].value == 132600
    assert service.claims[0].dimension == {"연령": "80대"}


def test_v2_keeps_a_valid_single_claim_without_an_extra_structured_output_call() -> None:
    source = "2024년 취업자는 2804만1000명이었다."
    extractor = _Extractor()
    service = _Service()

    result = recover_registry_record_v2(
        _record(ClaimSchema(
            claim_id="valid",
            source_sentence=source,
            indicator="취업자 수",
            value=28041000,
            unit="명",
            time="2024년",
            frequency="년",
            calculation="DIRECT_VALUE",
            parse_status="AUTO_OK",
        )),
        extractor=extractor,
        official_service=service,
    )

    assert extractor.inputs == []
    assert result.recovery_action == "DIRECT"
    assert service.claims[0].value == 28041000
