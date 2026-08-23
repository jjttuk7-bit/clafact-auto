import csv

from core.issue_group_executor import write_context_child_csv


def test_context_child_csv_writes_each_twelve_slot_value_and_status(tmp_path) -> None:
    output = tmp_path / "children.csv"
    write_context_child_csv(
        [
            {
                "claim_id": "P-001",
                "children": [
                    {
                        "claim_id": "C-001",
                        "admission_route": "CONTEXT_REQUIRED",
                        "twelve_slot_complete": False,
                        "claim": {
                            "indicator": "취업자",
                            "value": 100000,
                            "unit": "명",
                            "time": None,
                        },
                        "slot_audit": {
                            "reason_codes": ["MISSING_REQUIRED_SLOTS:time"],
                            "entries": [
                                {"slot": "indicator", "status": "SOURCE"},
                                {"slot": "value", "status": "SOURCE"},
                                {"slot": "unit", "status": "SOURCE"},
                                {"slot": "time", "status": "MISSING"},
                            ],
                        },
                    }
                ],
            }
        ],
        output,
    )

    with output.open(encoding="utf-8-sig", newline="") as source:
        row = next(csv.DictReader(source))
    assert row["부모Claim번호"] == "P-001"
    assert row["자식Claim번호"] == "C-001"
    assert row["지표"] == "취업자"
    assert row["지표상태"] == "SOURCE"
    assert row["시점상태"] == "MISSING"
    assert row["12개항목완성"] == "아니오"
    assert row["남은문제"] == "MISSING_REQUIRED_SLOTS:time"
