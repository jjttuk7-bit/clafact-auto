import json

import pytest

from core.data_loader import (
    load_kosis_catalog,
    load_standard_concepts,
    normalize_catalog_record,
)


def test_load_standard_concepts_reads_structured_seed_data(tmp_path) -> None:
    path = tmp_path / "concepts.json"
    path.write_text(
        json.dumps(
            [
                {
                    "concept_id": "C001",
                    "canonical_name": "고용률",
                    "standard_key": "employment_rate",
                    "aliases": ["고용률", "취업률"],
                    "kosis_search_terms": ["경제활동인구 고용률"],
                }
            ]
        ),
        encoding="utf-8",
    )

    concepts = load_standard_concepts(path)

    assert concepts[0].concept_id == "C001"
    assert concepts[0].aliases == ("고용률", "취업률")
    assert concepts[0].kosis_search_terms == ("경제활동인구 고용률",)


def test_normalize_catalog_record_parses_json_and_delimited_metadata() -> None:
    candidate = normalize_catalog_record(
        {
            "ORG_ID": 101,
            "TBL_ID": "DT_TEST",
            "TBL_NM_META": "고용률",
            "CORE_ITEM_IDS": "T1|T2",
            "CORE_ITEM_NAMES": "고용률|실업률",
            "DIMENSION_IDS": "SEX|AGE",
            "DIMENSION_NAMES": "성별|연령",
            "DIMENSION_MEMBERS_JSON": '{"SEX": ["전체"]}',
            "UNIT_NAMES_FINAL": "%|명",
            "PRD_SE_META": "Y",
            "STRT_PRD_DE": 2020,
            "END_PRD_DE": 2024,
            "semantic_core_status": "READY",
        }
    )

    assert candidate.org_id == "101"
    assert candidate.core_item_ids == ["T1", "T2"]
    assert candidate.dimension_members == {"SEX": ["전체"]}
    assert candidate.unit_names == ["%", "명"]


def test_load_kosis_catalog_returns_deterministic_table_order(tmp_path) -> None:
    path = tmp_path / "catalog.json"
    path.write_text(
        json.dumps(
            [
                {"ORG_ID": "101", "TBL_ID": "B", "TBL_NM_META": "B", "semantic_core_status": "READY"},
                {"ORG_ID": "101", "TBL_ID": "A", "TBL_NM_META": "A", "semantic_core_status": "READY"},
            ]
        ),
        encoding="utf-8",
    )

    catalog = load_kosis_catalog(path)

    assert [candidate.tbl_id for candidate in catalog] == ["A", "B"]


def test_normalize_catalog_record_rejects_invalid_dimension_json() -> None:
    with pytest.raises(ValueError, match="DIMENSION_MEMBERS_JSON"):
        normalize_catalog_record(
            {
                "ORG_ID": "101",
                "TBL_ID": "DT_TEST",
                "TBL_NM_META": "테스트",
                "DIMENSION_MEMBERS_JSON": "not-json",
                "semantic_core_status": "READY",
            }
        )
