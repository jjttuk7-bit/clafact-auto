import json

from tools.run_e2e_batch import run


def test_run_uses_dynamic_kosis_contract_without_profile_inputs(tmp_path) -> None:
    registry_path = tmp_path / "registry.jsonl"
    registry_path.write_text(
        json.dumps({
            "article_id": "A1", "sentence_id": "S1", "article_published_at": "2025-04-01", "source_ref": "test",
            "claim": {
                "claim_id": "C1", "source_sentence": "2025년 3월 취업자 수는 2,800만 명이다.",
                "indicator": "취업자 수", "value": 28_000_000, "unit": "명", "time": "2025년 3월",
                "frequency": "월", "region": "한국", "parse_status": "AUTO_OK",
            },
        }, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    standard_path = tmp_path / "standard.json"
    standard_path.write_text(json.dumps([{
        "concept_id": "employment", "canonical_name": "취업자 수", "standard_key": "employment_count",
        "aliases": ["취업자 수"],
    }], ensure_ascii=False), encoding="utf-8")
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text("[]", encoding="utf-8")

    results_path, report_path = run(
        registry_path, standard_path, tmp_path / "run", catalog_path=catalog_path
    )

    result = json.loads(results_path.read_text(encoding="utf-8").strip())
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert result["reason_code"] == "NO_HARD_GUARD_CANDIDATE"
    assert "profile_id" not in result
    assert "profile_dependency" not in report
