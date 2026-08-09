from core.kosis_catalog_adapter import KosisCatalogAdapter

def test_catalog_adapter_rejects_wrong_table_response() -> None:
    adapter=KosisCatalogAdapter(lambda _: {"TBL_ID":"OTHER"})
    try: adapter.fetch_table_metadata("DT_TEST")
    except ValueError: return
    assert False


def test_catalog_adapter_normalizes_official_item_metadata() -> None:
    from core.kosis_catalog_adapter import normalize_item_metadata

    result = normalize_item_metadata([
        {'ORG_ID':'101','TBL_ID':'DT','OBJ_ID':'C1','OBJ_NM':'지역','ITM_ID':'T1','ITM_NM':'고용률','UNIT_NM':'%'},
        {'ORG_ID':'101','TBL_ID':'DT','OBJ_ID':'C1','OBJ_NM':'지역','ITM_ID':'T2','ITM_NM':'실업률','UNIT_NM':'%'},
    ], table_id='DT')

    assert result.table_id == 'DT'
    assert result.item_codes == {'고용률': 'T1', '실업률': 'T2'}
    assert result.dimension_ids == {'지역': 'C1'}
    assert result.unit_names == ['%']

def test_hydrate_candidate_replaces_catalog_items_with_official_codes() -> None:
    from core.kosis_catalog_adapter import OfficialTableStructure, hydrate_candidate
    from schemas.candidate import KosisCandidateSchema

    candidate = KosisCandidateSchema(org_id='101', tbl_id='DT', tbl_name='고용', core_item_ids=['OLD'], core_item_names=['기존'], dimension_ids=['OLD_DIM'], dimension_names=['기존분류'], unit_names=['명'], metadata_status='STRUCTURAL_READY')
    official = OfficialTableStructure('DT', {'고용률': 'T1'}, {'지역': 'C1'}, ['%'])

    hydrated = hydrate_candidate(candidate, official)

    assert hydrated.core_item_ids == ['T1']
    assert hydrated.core_item_names == ['고용률']
    assert hydrated.dimension_ids == ['C1']
    assert hydrated.dimension_names == ['지역']
    assert hydrated.unit_names == ['%']
    assert hydrated.metadata_status == 'OFFICIAL_ITEM_METADATA_READY'

def test_hydrate_candidates_uses_official_itm_metadata_before_matching() -> None:
    from core.kosis_catalog_adapter import hydrate_candidates_from_official_metadata
    from schemas.candidate import KosisCandidateSchema

    candidate = KosisCandidateSchema(
        org_id='101', tbl_id='DT', tbl_name='고용', core_item_ids=['OLD'],
        core_item_names=['기존'], dimension_ids=['OLD_DIM'],
        dimension_names=['기존분류'], unit_names=['명'],
        metadata_status='STRUCTURAL_READY',
    )

    hydrated = hydrate_candidates_from_official_metadata(
        [candidate],
        lambda org_id, table_id: [
            {'ORG_ID': org_id, 'TBL_ID': table_id, 'OBJ_ID': 'C1', 'OBJ_NM': '지역', 'ITM_ID': 'T1', 'ITM_NM': '고용률', 'UNIT_NM': '%'},
        ],
    )

    assert hydrated[0].core_item_ids == ['T1']
    assert hydrated[0].dimension_ids == ['C1']


def test_hydrate_candidates_preserves_candidate_when_official_metadata_fails() -> None:
    from core.kosis_catalog_adapter import hydrate_candidates_from_official_metadata
    from schemas.candidate import KosisCandidateSchema

    candidate = KosisCandidateSchema(org_id='101', tbl_id='DT', tbl_name='고용', metadata_status='STRUCTURAL_READY')
    hydrated = hydrate_candidates_from_official_metadata(
        [candidate], lambda _org_id, _table_id: (_ for _ in ()).throw(RuntimeError('unavailable'))
    )

    assert hydrated == [candidate]