import csv
import hashlib
import json
from pathlib import Path

from tools.verify_frozen_input import verify_frozen_input


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _write_fixture(tmp_path: Path, claim_ids: list[str]) -> tuple[Path, Path, Path]:
    headers = ["Claim번호", "원문", "기사값"]
    records = [
        {"Claim번호": claim_id, "원문": f"문장 {index}", "기사값": index}
        for index, claim_id in enumerate(claim_ids, start=1)
    ]
    csv_path = tmp_path / "input.csv"
    jsonl_path = tmp_path / "input.jsonl"
    manifest_path = tmp_path / "manifest.json"

    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(records)
    with jsonl_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")

    manifest = {
        "row_count": len(records),
        "column_count": len(headers),
        "headers": headers,
        "outputs": {
            "csv": {"path": str(csv_path), "sha256": _sha256(csv_path)},
            "jsonl": {"path": str(jsonl_path), "sha256": _sha256(jsonl_path)},
        },
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return manifest_path, csv_path, jsonl_path


def test_verify_frozen_input_confirms_complete_unique_matching_rows(tmp_path: Path) -> None:
    manifest_path, csv_path, jsonl_path = _write_fixture(tmp_path, ["A_1", "A_2"])

    result = verify_frozen_input(
        manifest_path=manifest_path,
        csv_path=csv_path,
        jsonl_path=jsonl_path,
        expected_rows=2,
        claim_id_column="Claim번호",
    )

    assert result["status"] == "PASS"
    assert result["input_count"] == 2
    assert result["unique_claim_id_count"] == 2
    assert result["missing_claim_id_count"] == 0
    assert result["duplicate_claim_id_count"] == 0
    assert result["csv_jsonl_rows_equal"] is True
    assert result["issues"] == []


def test_verify_frozen_input_reports_duplicate_and_missing_claim_ids(tmp_path: Path) -> None:
    manifest_path, csv_path, jsonl_path = _write_fixture(tmp_path, ["A_1", "A_1", ""])

    result = verify_frozen_input(
        manifest_path=manifest_path,
        csv_path=csv_path,
        jsonl_path=jsonl_path,
        expected_rows=3,
        claim_id_column="Claim번호",
    )

    assert result["status"] == "FAIL"
    assert result["unique_claim_id_count"] == 1
    assert result["missing_claim_id_count"] == 1
    assert result["duplicate_claim_id_count"] == 1
    assert result["duplicate_claim_ids"] == ["A_1"]


def test_verify_frozen_input_reports_content_and_hash_mismatch(tmp_path: Path) -> None:
    manifest_path, csv_path, jsonl_path = _write_fixture(tmp_path, ["A_1"])
    jsonl_path.write_text('{"Claim번호":"A_1","원문":"변경","기사값":1}\n', encoding="utf-8")

    result = verify_frozen_input(
        manifest_path=manifest_path,
        csv_path=csv_path,
        jsonl_path=jsonl_path,
        expected_rows=1,
        claim_id_column="Claim번호",
    )

    assert result["status"] == "FAIL"
    assert result["csv_jsonl_rows_equal"] is False
    assert result["jsonl_hash_matches_manifest"] is False
