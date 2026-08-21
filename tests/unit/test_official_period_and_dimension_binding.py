from core.catalog_binding import apply_catalog_binding
from core.kosis_api_adapter import _api_period
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema


def test_quarter_period_converts_to_kosis_parameter_code():
    assert _api_period("2025-Q1") == "202501"
    assert _api_period("2025-03") == "202503"


def test_industry_production_binding_limits_verified_dimension_code():
    claim=ClaimSchema(claim_id='I',source_sentence='2024년 산업 생산은 1.7% 늘었다.',indicator='산업 생산',value=1.7,unit='%',time='2024년',frequency='년',calculation='GROWTH_RATE',parse_status='AUTO_OK')
    concept=StandardConceptSchema(concept_id='I',canonical_name='전산업생산지수',standard_key='all_industry_production_index',matched_alias='산업 생산',status='MATCHED')
    candidate=KosisCandidateSchema(org_id='101',tbl_id='DT_1JH20201',tbl_name='전산업생산지수',core_item_ids=['T1'],core_item_names=['원지수'],dimension_ids=['A'],dimension_names=['산업별 지수'],dimension_members={'A':['농림어업 제외','농림어업 포함']},dimension_member_codes={'A':{'농림어업 제외':'0','농림어업 포함':'1'}},unit_names=['2020=100'],frequency='년',metadata_status='OFFICIAL_METADATA_READY')
    selected=apply_catalog_binding(claim,concept,[candidate])[0]
    assert selected.dimension_members=={'A':['농림어업 제외']}
    assert selected.dimension_member_codes=={'A':{'농림어업 제외':'0'}}
