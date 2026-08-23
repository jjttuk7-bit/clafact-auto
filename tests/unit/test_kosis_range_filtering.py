import core.kosis_api_adapter as adapter
from schemas.evidence import EvidenceCellSchema


def test_range_adapter_filters_exact_operands_but_preserves_raw_response(monkeypatch) -> None:
    raw_rows = [
        {"TBL_ID": "DT", "ITM_ID": "T", "PRD_DE": "202406", "DT": "60"},
        {"TBL_ID": "DT", "ITM_ID": "T", "PRD_DE": "202407", "DT": "61"},
        {"TBL_ID": "DT", "ITM_ID": "T", "PRD_DE": "202506", "DT": "70"},
    ]
    monkeypatch.setattr(adapter, "get_parameter_data", lambda *_args, **_kwargs: raw_rows)
    cells = [
        EvidenceCellSchema(
            org_id="101", tbl_id="DT", itm_id="T", dimension_codes={"C1": "00"},
            prd_se="월", prd_de=period, canonical_key=period, status="CONFIRMED",
        )
        for period in ("2024-06", "2025-06")
    ]

    rows = adapter.build_kosis_api_lookup("secret").fetch_many(cells)

    assert [row["PRD_DE"] for row in rows] == ["202406", "202506"]
    assert rows.raw_rows == raw_rows
