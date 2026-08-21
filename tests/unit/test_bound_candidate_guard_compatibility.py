from core.hard_guard import apply_hard_guard
from core.semantic_matcher import semantic_match
from core.unit_normalizer import compatible_units
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema


def _candidate(**updates):
    values = dict(
        org_id="101", tbl_id="T", tbl_name="표", core_item_ids=["I"],
        core_item_names=["취업자"], dimension_ids=["B"], dimension_names=["성별"],
        dimension_members={"B": ["계"]}, dimension_member_codes={"B": {"계": "0"}},
        unit_names=["천명"], item_units={"I": "천명"}, frequency="월",
        start_period="2000.01", end_period="2026.07",
        metadata_status="OFFICIAL_METADATA_READY",
    )
    values.update(updates)
    return KosisCandidateSchema(**values)


def _claim(**updates):
    values = dict(
        claim_id="C", source_sentence="2025년 2월 취업자는 2817만9000명이다.",
        indicator="취업자", value=28179000, unit="명", time="2025년 2월",
        frequency="월", population="15세 이상 전체", calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )
    values.update(updates)
    return ClaimSchema(**values)


def test_guard_accepts_population_scope_stated_by_table_item_definition():
    candidate = _candidate(tbl_name="15세 이상 경제활동인구 총괄")
    assert apply_hard_guard(_claim(), candidate).passed


def test_guard_accepts_dimension_member_consumed_by_bound_measurement_item():
    claim = _claim(
        source_sentence="2025년 벼 재배면적은 67만8000ha다.", indicator="벼 재배 면적",
        value=678000, unit="ha", time="2025년", frequency="년", population=None,
        dimension={"작물": "벼"},
    )
    candidate = _candidate(
        tbl_name="시도별 식량작물 재배면적", core_item_ids=["T06"],
        core_item_names=["벼 계"], dimension_ids=["C1"], dimension_names=["시도별"],
        dimension_members={"C1": ["전국"]}, dimension_member_codes={"C1": {"전국": "00"}},
        unit_names=["ha"], item_units={}, frequency="년",
    )
    assert apply_hard_guard(claim, candidate).passed


def test_base_year_index_unit_spellings_are_compatible():
    assert compatible_units("지수 (2020년=100)", "2020=100")


def test_registered_official_binding_does_not_require_semantic_margin_again():
    claim = _claim(indicator="출생아 수", unit="명", population=None)
    candidate = _candidate(
        tbl_name="월분기연간 인구동향", core_item_names=["계"], unit_names=["명"],
        item_units={"I": "명"}, source_stat_id="OFFICIAL_RECURRING_DOMAIN_BINDING",
    )
    assert semantic_match(claim, [candidate])[0].route_status == "AUTO"
