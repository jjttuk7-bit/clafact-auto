from datetime import date

from core.admission_recovery import recover_registry_record
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


class _FailingExtractor:
    def extract(self, *_args, **_kwargs) -> ClaimSchema:
        raise AssertionError("AUTO_OK direct claim must not be reparsed")


class _OfficialService:
    def __init__(self) -> None:
        self.claims: list[ClaimSchema] = []

    def resolve(self, claim: ClaimSchema, *, article_date: date) -> dict[str, str]:
        self.claims.append(claim)
        return {"claim_id": claim.claim_id}


def test_auto_ok_single_claim_reuses_slots_and_enters_official_engine_without_reparse() -> None:
    original = ClaimSchema(
        claim_id="parent", source_sentence="2024년 취업자 수는 2804만명이었다.",
        indicator="취업자 수", value=28_040_000, unit="명", time="2024년",
        frequency="년", calculation="DIRECT_VALUE", parse_status="AUTO_OK",
    )
    record = ClaimRegistryRecord(
        article_id="article", sentence_id="sentence", article_published_at=date(2025, 1, 1),
        source_ref="registry", claim=original,
    )
    service = _OfficialService()

    result = recover_registry_record(
        record, extractor=_FailingExtractor(), official_service=service
    )

    assert result.recovery_action == "DIRECT"
    assert result.entries[0].record.claim == original
    assert result.entries[0].official_resolution == {"claim_id": "parent"}
    assert service.claims == [original]
