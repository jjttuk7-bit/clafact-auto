from core.profile_priority_queue import build_profile_priority_queue


def _derived(article_id: str, sentence_id: str, **claim: object) -> dict:
    return {
        "article_id": article_id,
        "sentence_id": sentence_id,
        "claim": {"claim_id": f"{article_id}:{sentence_id}", **claim},
    }


def test_groups_profile_not_found_claims_by_verification_type_and_priority() -> None:
    result = build_profile_priority_queue(
        [
            {"article_id": "A1", "sentence_id": "1", "reason_code": "PROFILE_NOT_FOUND"},
            {"article_id": "A2", "sentence_id": "1", "reason_code": "PROFILE_NOT_FOUND"},
            {"article_id": "A3", "sentence_id": "1", "reason_code": "CONCEPT_NOT_FOUND"},
        ],
        [
            _derived("A1", "1", indicator="수출액", calculation="DIRECT_VALUE", frequency="연", time="2024", unit="달러"),
            _derived("A2", "1", indicator="수출액", calculation="DIRECT_VALUE", frequency="연", time=None, unit="달러"),
            _derived("A3", "1", indicator="취업자 수", calculation="DIRECT_VALUE", frequency="월", time="2025-03", unit="천명"),
        ],
    )

    assert result == [
        {
            "priority_rank": 1,
            "indicator": "수출액",
            "calculation": "DIRECT_VALUE",
            "frequency": "연",
            "claim_count": 2,
            "claim_ids": ["A1:1", "A2:1"],
            "unresolved_claim_slots": ["time"],
            "required_kosis_metadata": ["TABLE", "ITEM", "DIMENSIONS", "UNIT", "PUBLICATION_POLICY"],
        }
    ]
