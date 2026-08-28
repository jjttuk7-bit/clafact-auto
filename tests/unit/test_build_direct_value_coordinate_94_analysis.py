import csv
import json

from tools.build_direct_value_coordinate_94_analysis import build_analysis_artifacts


def test_builder_writes_covered_analysis_and_rerun_registry(tmp_path) -> None:
    evaluation_csv = tmp_path / "evaluation.csv"
    row = {
        "Claim번호": "C1",
        "원문": "2024년 수입액은 10억원이다.",
        "최종실패단계": "필수 조건 검사",
        "최종사유": "NO_HARD_GUARD_CANDIDATE",
        "검색지표": "수입액",
        "단위": "원",
        "주기": "년",
        "지역": "전국",
        "대상집단": "",
    }
    with evaluation_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    live_path = tmp_path / "live.jsonl"
    live = {
        "parent_claim_id": "C1",
        "claim": {"claim_id": "C1", "source_sentence": row["원문"], "indicator": "수입액", "unit": "원"},
        "official_resolution": {
            "catalog_diagnostics": {"hard_guard_best_reject_UNIT_CONFLICT": 1},
            "candidates": [{"tbl_id": "T1", "unit_names": ["억원"]}],
        },
    }
    live_path.write_text(json.dumps(live, ensure_ascii=False) + "\n", encoding="utf-8")
    registry_path = tmp_path / "ready.jsonl"
    registry = {"claim": {"claim_id": "C1", "source_sentence": row["원문"]}}
    registry_path.write_text(json.dumps(registry, ensure_ascii=False) + "\n", encoding="utf-8")

    summary = build_analysis_artifacts(
        evaluation_csv,
        live_path,
        registry_path,
        tmp_path / "out",
        expected_count=1,
    )

    assert summary["scope_count"] == 1
    assert summary["rerun_registry_count"] == 1
    assert summary["primary_cause_counts"] == {"UNIT_COORDINATE_GAP": 1}
    assert (tmp_path / "out" / "classification.csv").exists()
    assert (tmp_path / "out" / "input_registry.jsonl").exists()
