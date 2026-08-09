from core.member_code_mapper import build_member_code_map, resolve_member_code


def test_build_member_code_map_and_resolve_normalized_member() -> None:
    mapping = build_member_code_map([
        {"dimension_id": "C1", "member_code": "28", "member_name": "인천광역시"},
        {"dimension_id": "C2", "member_code": "A08", "member_name": "65~69세"},
    ])
    assert mapping == {"C1": {"인천광역시": "28"}, "C2": {"65~69세": "A08"}}
    assert resolve_member_code(mapping, "C2", "65 - 69세") == "A08"


def test_resolve_member_code_returns_none_when_ambiguous_or_missing() -> None:
    mapping = {"C1": {"서울": "11", "서울특별시": "11"}}
    assert resolve_member_code(mapping, "C1", "부산") is None
