from datetime import date

from core.source_sign_direction import (
    apply_source_sign_direction_enrichment,
    sign_direction_preverification_reason,
)
from core.unified_claim_pipeline import verify_registry_record
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


def _record(enrichment: dict[str, object]) -> ClaimRegistryRecord:
    claim = ClaimSchema(
        claim_id="C1",
        source_sentence="취업자가 31만명 이상 늘었다.",
        indicator="취업자 수",
        value=310_000,
        unit="명",
        time="2025-09",
        frequency="월",
        calculation="DIRECT_VALUE",
        condition={"direction": "DECREASE", "operator": "GTE"},
        parse_status="AUTO_OK",
    )
    return ClaimRegistryRecord(
        article_id="A1",
        sentence_id="1",
        article_published_at=date(2025, 10, 1),
        source_ref="sign_direction_audit",
        claim=claim,
        slot_enrichment=enrichment,
    )


def test_applies_source_direction_without_discarding_other_condition_keys() -> None:
    record = _record({
        "sign_direction_status": "STORED_DIRECTION_CONFLICT_CORRECTED",
        "source_direction": "INCREASE",
        "signed_target_value": 310_000,
    })

    updated = apply_source_sign_direction_enrichment(record)

    assert updated.claim.value == 310_000
    assert updated.claim.condition == {"direction": "INCREASE", "operator": "GTE"}
    assert updated.slot_enrichment["signed_target_value"] == 310_000


def test_applies_balance_polarity_without_changing_claim_value() -> None:
    record = _record({
        "sign_direction_status": "BALANCE_POLARITY_CONFIRMED",
        "source_polarity": "DEFICIT",
        "signed_target_value": -310_000,
    })

    updated = apply_source_sign_direction_enrichment(record)

    assert updated.claim.value == 310_000
    assert updated.claim.condition == {
        "direction": "DECREASE",
        "operator": "GTE",
        "polarity": "DEFICIT",
    }


class _Extractor:
    def extract(self, source_sentence: str, **kwargs: object) -> ClaimSchema:
        raise AssertionError("ambiguous sign Claim must stop before reparse")


class _Resolver:
    def __init__(self) -> None:
        self.calls = 0

    def resolve(self, claim: ClaimSchema, *, article_date: date) -> object:
        self.calls += 1
        return None


def test_role_review_stops_before_official_lookup() -> None:
    record = _record({
        "sign_direction_status": "TARGET_ROLE_REVIEW_REQUIRED",
        "sign_direction_reason_code": "TARGET_IS_LEVEL_NOT_CHANGE_AMOUNT",
    })
    resolver = _Resolver()

    entries = verify_registry_record(
        record,
        extractor=_Extractor(),
        official_service=resolver,
    )

    assert sign_direction_preverification_reason(record) == "TARGET_ROLE_REVIEW_REQUIRED"
    assert entries[0].terminal_status == "HUMAN_REVIEW"
    assert entries[0].reason_code == "TARGET_ROLE_REVIEW_REQUIRED"
    assert resolver.calls == 0
