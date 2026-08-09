import core.kosis_api_adapter as adapter
from schemas.evidence import EvidenceCellSchema


def test_api_lookup_passes_complete_evidence_coordinate(monkeypatch) -> None:
    captured = {}
    def fake_get(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return [{"TBL_ID":"DT", "ITM_ID":"T1", "PRD_DE":"202405", "C1":"00", "DT":"70"}]
    monkeypatch.setattr(adapter, "get_parameter_data", fake_get)
    cell = EvidenceCellSchema(org_id="101", tbl_id="DT", itm_id="T1", prd_se="월", prd_de="202405", dimension_codes={"C1":"00"}, canonical_key="key", status="CONFIRMED")

    rows = adapter.build_kosis_api_lookup("secret")(cell)

    assert rows[0]["DT"] == "70"
    assert captured["args"][:5] == ("secret", "101", "DT", "T1", "M")
    assert captured["args"][5:7] == ("202405", "202405")
    assert captured["args"][7] == ["00"]


def test_api_lookup_uses_ordered_non_c_dimension_codes(monkeypatch) -> None:
    captured = {}
    def fake_get(*args, **kwargs):
        captured["codes"] = args[7]
        return [{"TBL_ID":"DT", "ITM_ID":"T1", "PRD_DE":"202405", "I":"T10", "DT":"2.4"}]
    monkeypatch.setattr(adapter, "get_parameter_data", fake_get)
    cell = EvidenceCellSchema(org_id="101", tbl_id="DT", itm_id="T1", prd_se="월", prd_de="202405", dimension_codes={"I":"T10"}, canonical_key="key", status="CONFIRMED")

    adapter.build_kosis_api_lookup("secret")(cell)

    assert captured["codes"] == ["T10"]
