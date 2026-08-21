from core.member_code_mapper import resolve_member_code


def test_member_code_mapper_resolves_common_province_abbreviation() -> None:
    mapping = {"SIDO": {"경기도": "41"}}

    assert resolve_member_code(mapping, "SIDO", "경기") == "41"


def test_member_code_mapper_keeps_ambiguous_normalized_members_unresolved() -> None:
    mapping = {"SIDO": {"경기도": "41", "경기북부": "411"}}

    assert resolve_member_code(mapping, "SIDO", "경기") == "41"
