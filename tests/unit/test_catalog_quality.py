from core.catalog_quality import inspect_catalog_records


def test_catalog_quality_reports_encoding_duplicates_and_missing_structure() -> None:
    report = inspect_catalog_records(
        [
            {
                'ORG_ID': '101', 'TBL_ID': 'DT_GOOD', 'TBL_NM_META': '고용률',
                'CORE_ITEM_IDS': 'T1', 'CORE_ITEM_NAMES': '고용률',
                'DIMENSION_MEMBERS_JSON': '{}', 'UNIT_NAMES_FINAL': '%',
                'semantic_core_status': 'STRUCTURAL_READY',
            },
            {
                'ORG_ID': '101', 'TBL_ID': 'DT_BAD', 'TBL_NM_META': 'ì‹¤ì—…ë¥ ',
                'CORE_ITEM_IDS': '', 'CORE_ITEM_NAMES': '',
                'DIMENSION_MEMBERS_JSON': '{broken', 'UNIT_NAMES_FINAL': '',
                'semantic_core_status': 'STRUCTURAL_READY',
            },
            {
                'ORG_ID': '101', 'TBL_ID': 'DT_GOOD', 'TBL_NM_META': '고용률(중복)',
                'CORE_ITEM_IDS': 'T1', 'CORE_ITEM_NAMES': '고용률',
                'DIMENSION_MEMBERS_JSON': '{}', 'UNIT_NAMES_FINAL': '%',
                'semantic_core_status': 'STRUCTURAL_READY',
            },
        ]
    )

    assert report.total_records == 3
    assert report.encoding_suspect_table_ids == ['DT_BAD']

    real_style = inspect_catalog_records([{'TBL_ID': 'DT_REAL_STYLE', 'TBL_NM_META': '(ì™¸êµ­ì¸) ì°½ì—…', 'CORE_ITEM_IDS': 'T1', 'CORE_ITEM_NAMES': 'ì°½ì—…', 'DIMENSION_MEMBERS_JSON': '{}', 'UNIT_NAMES_FINAL': '%', 'semantic_core_status': 'STRUCTURAL_READY'}])
    assert real_style.encoding_suspect_table_ids == ['DT_REAL_STYLE']
    assert report.duplicate_table_ids == ['DT_GOOD']
    assert report.missing_core_item_table_ids == ['DT_BAD']
    assert report.invalid_dimension_json_table_ids == ['DT_BAD']
    assert report.ready_records == 1