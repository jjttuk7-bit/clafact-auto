import json

from tools.run_e2e_batch import run


def test_run_uses_injected_kosis_lookup_for_registered_profile(tmp_path) -> None:
    registry_path = tmp_path / "registry.jsonl"
    registry_path.write_text(
        json.dumps(
            {
                "article_id": "A1",
                "sentence_id": "S1",
                "article_published_at": "2025-04-01",
                "source_ref": "test",
                "claim": {
                    "claim_id": "C1",
                    "source_sentence": "2025년 3월 취업자 수는 2,800만 명이다.",
                    "value": 28000,
                    "unit": "천명",
                    "time": "2025년 3월",
                    "frequency": "월",
                    "calculation": "DIRECT_VALUE",
                    "parse_status": "AUTO_OK",
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    profiles_path = tmp_path / "profiles.json"
    profiles_path.write_text(
        json.dumps(
            {
                "profile_schema_version": "v1",
                "profiles": [
                    {
                        "profile_id": "employment-v1",
                        "claim_key": "employment_count",
                        "calculation_type": "DIRECT_VALUE",
                        "org_id": "101",
                        "tbl_id": "DT",
                        "itm_id": "T1",
                        "prd_se": "M",
                        "unit": "천명",
                        "dataset_version": "d1",
                        "preprocess_version": "p1",
                        "claim_schema_version": "c1",
                        "semantic_standard_version": "s1",
                        "kosis_catalog_version": "k1",
                        "matching_version": "m1",
                        "calculation_version": "v1",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    concepts_path = tmp_path / "concepts.json"
    concepts_path.write_text(
        json.dumps(
            [
                {
                    "article_id": "A1",
                    "sentence_id": "S1",
                    "concept": {
                        "concept_id": "employment",
                        "canonical_name": "취업자 수",
                        "standard_key": "employment_count",
                        "status": "MATCHED",
                    },
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    results_path, _ = run(
        registry_path,
        profiles_path,
        concepts_path,
        tmp_path / "run",
        api_lookup=lambda _cell: [
            {
                "tbl_id": "DT",
                "item_id": "T1",
                "period": "202503",
                "value": 28000,
                "LST_CHN_DE": "2025-03-31",
            }
        ],
    )

    result = json.loads(results_path.read_text(encoding="utf-8").strip())
    assert result["route_status"] == "AUTO"
    assert json.loads((tmp_path / "run" / "profile_review_priority_queue.json").read_text(encoding="utf-8")) == []
