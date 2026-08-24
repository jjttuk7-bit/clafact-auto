import pytest

from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord
from tools.run_official_author_fallback_group import select_frozen_records


def _record(claim_id: str) -> ClaimRegistryRecord:
    return ClaimRegistryRecord(
        article_id="A1", sentence_id=claim_id, source_ref="test",
        claim=ClaimSchema(
            claim_id=claim_id, source_sentence=claim_id, indicator="지표",
            value=1, unit="%", time="2024", parse_status="AUTO_OK",
        ),
    )


def test_selects_exactly_five_frozen_ids_in_frozen_order() -> None:
    records = [_record(f"c{index}") for index in range(6)]
    frozen = [{"claim_id": claim_id} for claim_id in ("c4", "c0", "c3", "c1", "c2")]

    selected = select_frozen_records(records, frozen, expected_count=5)

    assert [record.claim.claim_id for record in selected] == ["c4", "c0", "c3", "c1", "c2"]


def test_rejects_missing_or_duplicate_frozen_ids() -> None:
    records = [_record(f"c{index}") for index in range(5)]

    with pytest.raises(ValueError, match="FROZEN_CLAIM_ID_NOT_FOUND"):
        select_frozen_records(records, [{"claim_id": f"c{index}"} for index in range(4)] + [{"claim_id": "missing"}], expected_count=5)
    with pytest.raises(ValueError, match="FROZEN_CLAIM_IDS_INVALID"):
        select_frozen_records(records, [{"claim_id": "c0"}] * 5, expected_count=5)
