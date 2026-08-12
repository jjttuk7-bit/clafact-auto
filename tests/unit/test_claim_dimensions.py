from core.claim_dimensions import normalized_dimension_members


def test_normalized_dimension_members_unwraps_json_encoded_raw_slot() -> None:
    assert normalized_dimension_members(
        {"raw": '{"교역상대국": ["미국"]}'}
    ) == {"교역상대국": ["미국"]}


def test_normalized_dimension_members_preserves_plain_structured_slot() -> None:
    assert normalized_dimension_members({"품목": "사과"}) == {"품목": ["사과"]}


def test_normalized_dimension_members_keeps_non_json_raw_text() -> None:
    assert normalized_dimension_members({"raw": "전체"}) == {"raw": ["전체"]}