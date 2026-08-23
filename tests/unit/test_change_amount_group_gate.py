import csv
import json


def test_gate_accepts_match_or_mismatch_after_complete_official_calculation(tmp_path) -> None:
    from tools.evaluate_change_amount_group import main

    reclassification = tmp_path / "reclassification.csv"
    with reclassification.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["claim_id", "result"])
        writer.writeheader()
        writer.writerows([
            {"claim_id": "match", "result": "RECLASSIFIED"},
            {"claim_id": "mismatch", "result": "RECLASSIFIED"},
        ])
    results = tmp_path / "results.jsonl"
    rows = []
    for claim_id, verdict_name in (("match", "MATCH"), ("mismatch", "MISMATCH")):
        rows.append({
            "claim_id": claim_id,
            "terminal_status": "AUTO",
            "claim": {"calculation": "DIFFERENCE"},
            "official_resolution": {"verdict": {
                "verdict": verdict_name,
                "calculated_value": 19_000,
                "evidence_cells": [{"prd_de": "2024-12"}, {"prd_de": "2023-12"}],
                "evidence_values": [100, 81],
                "official_value_provenance": [
                    {
                        "source": "API", "source_url": "https://kosis.kr/value/1",
                        "content_hash": "value-1", "retrieved_at": "2026-08-23T00:00:00Z",
                        "publication": {"status": "VERIFIED", "source_url": "https://kostat.go.kr/release/1",
                            "content_hash": "release-1", "retrieved_at": "2026-08-23T00:00:00Z"},
                    },
                    {
                        "source": "API", "source_url": "https://kosis.kr/value/2",
                        "content_hash": "value-2", "retrieved_at": "2026-08-23T00:00:00Z",
                        "publication": {"status": "VERIFIED", "source_url": "https://kostat.go.kr/release/2",
                            "content_hash": "release-2", "retrieved_at": "2026-08-23T00:00:00Z"},
                    },
                ],
                "execution_trace": {"events": [
                    {"stage": "OFFICIAL_VALUE_FETCH", "status": "PASS"},
                    {"stage": "CALCULATION", "status": "PASS"},
                    {"stage": "VERDICT", "status": "PASS"},
                ]},
            }},
        })
    results.write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8",
    )
    output = tmp_path / "gate.csv"

    assert main([
        str(reclassification), str(results), str(output),
        "--claim-id", "match", "--claim-id", "mismatch",
    ]) == 0

    with output.open(encoding="utf-8-sig", newline="") as handle:
        gate_rows = list(csv.DictReader(handle))
    assert [row["gate_passed"] for row in gate_rows] == ["true", "true"]
    assert [row["terminal_verdict"] for row in gate_rows] == ["MATCH", "MISMATCH"]


def test_gate_fails_without_two_verified_api_cells(tmp_path) -> None:
    from tools.evaluate_change_amount_group import evaluate_claim

    result = evaluate_claim(
        "claim",
        reclassified=True,
        result={
            "terminal_status": "AUTO",
            "claim": {"calculation": "DIFFERENCE"},
            "official_resolution": {"verdict": {
                "verdict": "MATCH", "calculated_value": 1,
                "evidence_cells": [{"prd_de": "2024"}],
                "official_value_provenance": [],
                "execution_trace": {"events": []},
            }},
        },
    )

    assert result["gate_passed"] == "false"
    assert "OFFICIAL_EVIDENCE_NOT_TWO_CELLS" in result["gate_reasons"]
