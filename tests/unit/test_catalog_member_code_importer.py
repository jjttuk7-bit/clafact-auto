import json

from core.catalog_member_code_importer import import_member_codes


def test_import_member_codes_groups_by_table_and_dimension(tmp_path) -> None:
    source = tmp_path / "members.json"
    source.write_text(json.dumps([{"tbl_id":"DT","dimension_id":"C1","member_code":"00","member_name":"전국"}]), encoding="utf-8")
    assert import_member_codes(source) == {"DT": {"C1": {"전국": "00"}}}
