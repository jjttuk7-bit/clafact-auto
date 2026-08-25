from datetime import date

import pytest

from core.source_sign_direction import sign_direction_preverification_reason
from core.source_target_grounding import target_link_preverification_reason
from core.unified_claim_pipeline import verify_registry_record
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


class _Extractor:
    def extract(self, source_sentence: str, **kwargs: object) -> ClaimSchema:
        raise AssertionError("unsafe numeric role must stop before reparse")


class _Resolver:
    def __init__(self) -> None:
        self.calls = 0

    def resolve(self, claim: ClaimSchema, *, article_date: date) -> object:
        self.calls += 1
        return None


def _record(enrichment: dict[str, object]) -> ClaimRegistryRecord:
    return ClaimRegistryRecord(
        article_id="A1",
        sentence_id="1",
        article_published_at=date(2025, 1, 1),
        source_ref="numeric_role_gate",
        claim=ClaimSchema(
            claim_id="C1",
            source_sentence="20대 인구는 703만명이다.",
            indicator="인구",
            value=20,
            unit="대",
            time="2024",
            frequency="년",
            calculation="DIRECT_VALUE",
            parse_status="AUTO_OK",
        ),
        slot_enrichment=enrichment,
    )


@pytest.mark.parametrize(
    "enrichment, expected",
    [
        ({"target_link_status": "TARGET_CONTEXT_ROLE_CONFLICT"}, "TARGET_CONTEXT_ROLE_CONFLICT"),
        ({"target_link_status": "TARGET_NOT_FOUND_IN_SOURCE"}, "TARGET_NOT_FOUND_IN_SOURCE"),
        ({"target_link_status": "TARGET_AMBIGUOUS_IN_SOURCE"}, "TARGET_AMBIGUOUS_IN_SOURCE"),
        ({"target_link_status": "SOURCE_GROUNDED", "sign_direction_status": "TARGET_ROLE_REVIEW_REQUIRED"}, "TARGET_ROLE_REVIEW_REQUIRED"),
    ],
)
def test_every_unsafe_numeric_role_stops_before_official_lookup(
    enrichment: dict[str, object],
    expected: str,
) -> None:
    resolver = _Resolver()

    entries = verify_registry_record(
        _record(enrichment),
        extractor=_Extractor(),
        official_service=resolver,
    )

    assert entries[0].terminal_status == "HUMAN_REVIEW"
    assert entries[0].reason_code == expected
    assert resolver.calls == 0


def test_safe_numeric_role_has_no_existing_preverification_block() -> None:
    record = _record({
        "target_link_status": "SOURCE_GROUNDED",
        "target_numeric_expression": "703만명",
        "target_numeric_start": 8,
        "target_numeric_end": 13,
        "sign_direction_status": "NOT_APPLICABLE_LEVEL_VALUE",
    })

    assert target_link_preverification_reason(record) is None
    assert sign_direction_preverification_reason(record) is None
