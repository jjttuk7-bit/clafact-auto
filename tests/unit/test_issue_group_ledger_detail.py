import csv

from core.issue_group_harness import build_issue_registry, write_issue_ledgers


def test_master_ledger_records_twelve_slots_and_official_attempt_counts(tmp_path) -> None:
    records = build_issue_registry(
        [
            {
                "article_id": "A-001",
                "sentence_id": "1",
                "parent_claim_id": "C-001",
                "claim_id": "C-001",
                "source_sentence": "취업자는 증가했다.",
                "terminal_status": "HOLD",
                "reason_code": "KOSIS_METADATA_UNAVAILABLE",
                "claim": {"claim_id": "C-001", "domain": "employment"},
                "slot_audit": {
                    "eligible_for_official_search": False,
                    "entries": [
                        {"slot": "indicator", "status": "SOURCE", "value": "취업자"},
                        {"slot": "time", "status": "MISSING", "value": None},
                    ],
                },
                "stage_results": [],
                "official_resolution": {
                    "catalog_diagnostics": {
                        "attempted_queries": 4,
                        "metadata_itm_attempted": 3,
                        "metadata_prd_attempted": 2,
                    },
                    "verdict": {
                        "route_status": "HOLD",
                        "reason_code": "KOSIS_METADATA_UNAVAILABLE",
                    },
                },
            }
        ]
    )

    write_issue_ledgers(records, tmp_path)

    with (tmp_path / "claim_issue_master.csv").open(
        encoding="utf-8-sig", newline=""
    ) as source:
        row = next(csv.DictReader(source))
    assert row["분야"] == "employment"
    assert row["12개항목공식조회가능"] == "아니오"
    assert "indicator=SOURCE" in row["12개항목상태"]
    assert "time=MISSING" in row["12개항목상태"]
    assert row["통계표검색시도"] == "4"
    assert row["항목정보조회시도"] == "3"
    assert row["기간정보조회시도"] == "2"
