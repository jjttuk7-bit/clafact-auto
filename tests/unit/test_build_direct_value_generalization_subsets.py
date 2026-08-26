from datetime import date

from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord
from tools.build_direct_value_generalization_subsets import select_registry_records


def _record(claim_id: str) -> ClaimRegistryRecord:
    return ClaimRegistryRecord(
        article_id=f"article_{claim_id}", sentence_id="1",
        article_published_at=date(2025, 1, 2), source_ref="fixture",
        claim=ClaimSchema(
            claim_id=claim_id, source_sentence="2024년 취업자는 10명이었다.",
            indicator="취업자 수", value=10, unit="명", time="2024년",
            frequency="년", calculation="DIRECT_VALUE", parse_status="AUTO_OK",
        ),
    )


def test_select_registry_records_preserves_requested_order_and_rejects_missing():
    records = [_record("b"), _record("a")]
    assert [x.claim.claim_id for x in select_registry_records(records, ["a", "b"])] == ["a", "b"]
    try:
        select_registry_records(records, ["missing"])
    except ValueError as error:
        assert str(error) == "GENERALIZATION_REGISTRY_CLAIM_NOT_FOUND:missing"
    else:
        raise AssertionError("missing Claim must fail closed")
