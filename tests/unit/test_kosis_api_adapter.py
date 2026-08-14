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


def test_api_lookup_fetches_comparison_periods_in_one_range_request(monkeypatch) -> None:
    captured = {"calls": 0}

    def fake_get(*args, **kwargs):
        captured["calls"] += 1
        captured["start_end"] = args[5:7]
        return [
            {"TBL_ID":"DT", "ITM_ID":"T1", "PRD_DE":"202410", "DT":"208.57"},
            {"TBL_ID":"DT", "ITM_ID":"T1", "PRD_DE":"202510", "DT":"136.62"},
        ]

    monkeypatch.setattr(adapter, "get_parameter_data", fake_get)
    cells = [
        EvidenceCellSchema(
            org_id="101", tbl_id="DT", itm_id="T1", prd_se="월", prd_de=period,
            dimension_codes={"C":"T10", "I":"A02A01701"},
            canonical_key=period, status="CONFIRMED",
        )
        for period in ("2025-10", "2024-10")
    ]

    rows = adapter.build_kosis_api_lookup("secret").fetch_many(cells)

    assert captured == {"calls": 1, "start_end": ("202410", "202510")}
    assert [row["DT"] for row in rows] == ["208.57", "136.62"]
def test_api_lookup_passes_configured_timeout_and_retry_budget(monkeypatch) -> None:
    captured = {}

    def fake_get(*args, **kwargs):
        captured.update(kwargs)
        return [{"TBL_ID": "DT", "ITM_ID": "T1", "PRD_DE": "202405", "DT": "70"}]

    monkeypatch.setattr(adapter, "get_parameter_data", fake_get)
    cell = EvidenceCellSchema(
        org_id="101", tbl_id="DT", itm_id="T1", prd_se="월", prd_de="202405",
        dimension_codes={"C1": "00"}, canonical_key="key", status="CONFIRMED",
    )

    adapter.build_kosis_api_lookup("secret", retries=1, timeout_seconds=4)(cell)

    assert captured == {"retries": 1, "timeout_seconds": 4}
