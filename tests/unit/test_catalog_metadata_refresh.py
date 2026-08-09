from core.kosis_catalog_adapter import OfficialTableStructure
from schemas.candidate import KosisCandidateSchema


def test_refresh_uses_kosis_itm_metadata_with_api_key() -> None:
    from core.catalog_metadata_refresh import refresh_item_metadata

    candidate = KosisCandidateSchema(org_id='101', tbl_id='DT', tbl_name='고용', metadata_status='STRUCTURAL_READY')
    refreshed = refresh_item_metadata(
        [candidate],
        'secret',
        metadata_fetcher=lambda api_key, org_id, table_id, *, meta_type, retries, timeout_seconds: [
            {'ORG_ID': org_id, 'TBL_ID': table_id, 'OBJ_ID': 'C1', 'OBJ_NM': '지역', 'ITM_ID': 'T1', 'ITM_NM': '고용률', 'UNIT_NM': '%'},
        ],
    )

    assert refreshed[0].core_item_ids == ['T1']
    assert refreshed[0].dimension_ids == ['C1']


def test_refresh_keeps_candidates_unchanged_without_api_key() -> None:
    from core.catalog_metadata_refresh import refresh_item_metadata

    candidate = KosisCandidateSchema(org_id='101', tbl_id='DT', tbl_name='고용', metadata_status='STRUCTURAL_READY')
    assert refresh_item_metadata([candidate], None) == [candidate]