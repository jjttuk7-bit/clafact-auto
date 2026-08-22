from core.claim_lineage import ClaimLineageRecord, validate_claim_lineage


def test_lineage_accepts_complete_unique_parent_child_relationships() -> None:
    records = [
        ClaimLineageRecord(
            parent_claim_id="P-001",
            child_claim_id="P-001-01",
            child_ordinal=1,
            source_sentence="취업자는 10만 명 증가했고 실업률은 3%로 하락했다.",
            target_expression="10만 명",
        ),
        ClaimLineageRecord(
            parent_claim_id="P-001",
            child_claim_id="P-001-02",
            child_ordinal=2,
            source_sentence="취업자는 10만 명 증가했고 실업률은 3%로 하락했다.",
            target_expression="3%",
        ),
        ClaimLineageRecord(
            parent_claim_id="P-002",
            child_claim_id="P-002-01",
            child_ordinal=1,
            source_sentence="출생아 수는 2만 명이다.",
            target_expression="2만 명",
        ),
    ]

    result = validate_claim_lineage(records, expected_parent_ids={"P-001", "P-002"})

    assert result.is_valid is True
    assert result.parent_count == 2
    assert result.child_count == 3
    assert result.missing_parent_ids == []
    assert result.duplicate_child_ids == []


def test_lineage_reports_missing_parent_and_duplicate_child() -> None:
    records = [
        ClaimLineageRecord(
            parent_claim_id="P-001",
            child_claim_id="C-001",
            child_ordinal=1,
            source_sentence="첫 문장",
            target_expression="10명",
        ),
        ClaimLineageRecord(
            parent_claim_id="P-001",
            child_claim_id="C-001",
            child_ordinal=2,
            source_sentence="첫 문장",
            target_expression="20명",
        ),
    ]

    result = validate_claim_lineage(records, expected_parent_ids={"P-001", "P-002"})

    assert result.is_valid is False
    assert result.missing_parent_ids == ["P-002"]
    assert result.duplicate_child_ids == ["C-001"]

