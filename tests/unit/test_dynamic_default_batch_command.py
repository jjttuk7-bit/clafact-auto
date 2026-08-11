import json

from tools.run_e2e_batch import select_records, run


def test_default_batch_command_uses_dynamic_catalog_without_profiles(tmp_path) -> None:
    registry_path = tmp_path / "registry.jsonl"
    registry_path.write_text(json.dumps({
        "article_id": "A1", "sentence_id": "S1", "article_published_at": "2025-04-01", "source_ref": "test",
        "claim": {"claim_id": "C1", "source_sentence": "2025년 3월 취업자 수는 2,800만 명이다.",
                  "indicator": "취업자 수", "value": 28_000_000, "unit": "명", "time": "2025년 3월",
                  "frequency": "월", "region": "한국", "parse_status": "AUTO_OK"},
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    standard_path = tmp_path / "standard.json"
    standard_path.write_text(json.dumps([{
        "concept_id": "employment", "canonical_name": "취업자 수", "standard_key": "employment_count",
        "aliases": ["취업자 수"],
    }], ensure_ascii=False), encoding="utf-8")
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps([{
        "ORG_ID": "101", "TBL_ID": "DT", "TBL_NM_META": "성별 취업자", "CORE_ITEM_IDS": "T1",
        "CORE_ITEM_NAMES": "취업자", "DIMENSION_IDS": "B", "DIMENSION_NAMES": "성별",
        "DIMENSION_MEMBERS_JSON": {"B": ["계"]}, "UNIT_NAMES_FINAL": "천명", "PRD_SE_META": "월", "METADATA_STATUS": "STRUCTURAL_READY",
    }], ensure_ascii=False), encoding="utf-8")

    results_path, report_path = run(
        registry_path, standard_path, tmp_path / "run", catalog_path=catalog_path, start=0, limit=1,
        api_lookup=lambda _cell: [{"tbl_id": "DT", "item_id": "T1", "period": "202503", "B": "0", "value": 28000, "LST_CHN_DE": "2025-03-31"}],
    )

    result = json.loads(results_path.read_text(encoding="utf-8").strip())
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert result["route_status"] == "HOLD"
    assert result["profile_id"] is None
    assert report["profile_dependency"] == "none"


def test_select_records_returns_a_stable_batch_range() -> None:
    assert select_records(["a", "b", "c", "d"], start=1, limit=2) == ["b", "c"]