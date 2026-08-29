from datetime import date

from core.catalog_binding import apply_catalog_binding
from core.direct_value_child_guard import apply_direct_value_child_guard
from core.evidence_resolver import resolve_evidence_cell
from core.source_target_grounding import repair_exact_target_grounding
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord
from schemas.concept import StandardConceptSchema


def _concept(key: str, name: str) -> StandardConceptSchema:
    return StandardConceptSchema(
        concept_id="TEST", canonical_name=name, standard_key=key,
        matched_alias=name, status="MATCHED",
    )


def _candidate(table: str, item: str, name: str) -> KosisCandidateSchema:
    return KosisCandidateSchema(
        org_id="101", tbl_id=table, tbl_name=name,
        core_item_ids=[item], core_item_names=[name],
        unit_names=["%" if "률" in name else "천명"],
        item_units={item: "%" if "률" in name else "천명"},
        frequency="월|분기|년", metadata_status="OFFICIAL_METADATA_READY",
    )


def test_monthly_total_employment_binding_consumes_fifteen_plus_table_scope() -> None:
    claim = ClaimSchema(
        claim_id="EMP-TOTAL", source_sentence="2025년 9월 15세 이상 취업자는 2915만4000명이다.",
        indicator="취업자", value=29_154_000, unit="명", time="2025년 9월",
        frequency="월", region="대한민국", population="15세 이상",
        dimension={"age": "15세 이상"}, calculation="DIRECT_VALUE", parse_status="AUTO_OK",
    )
    target = _candidate("DT_1DA7001S", "T30", "취업자")
    other = _candidate("DT_1DA7024S", "T30", "성/연령별 취업자")

    selected = apply_catalog_binding(
        claim, _concept("employment_count", "취업자"), [other, target]
    )

    assert [item.tbl_id for item in selected] == ["DT_1DA7001S"]
    assert "15세 이상" in selected[0].binding_scope_terms


def test_table_scope_term_satisfies_population_without_fake_dimension_code() -> None:
    claim = ClaimSchema(
        claim_id="EMP-SCOPE", source_sentence="2025년 2월 15세 이상 전체 취업자는 2817만9000명이다.",
        indicator="취업자", value=28_179_000, unit="명", time="2025년 2월",
        frequency="월", population="15세 이상 전체",
        calculation="DIRECT_VALUE", parse_status="AUTO_OK",
    )
    candidate = KosisCandidateSchema(
        org_id="101", tbl_id="DT_1DA7001S", tbl_name="경제활동인구 총괄",
        core_item_ids=["T30"], core_item_names=["취업자"],
        dimension_ids=["B"], dimension_names=["성별"],
        dimension_members={"B": ["계"]}, dimension_member_codes={"B": {"계": "0"}},
        unit_names=["천명"], item_units={"T30": "천명"}, frequency="월",
        binding_scope_terms=["15세 이상", "15세 이상 전체"],
        metadata_status="OFFICIAL_METADATA_READY",
    )

    cell = resolve_evidence_cell(claim, candidate)

    assert cell.status == "CONFIRMED"
    assert cell.dimension_codes == {"B": "0"}


def test_monthly_age_employment_rate_binding_keeps_age_dynamic() -> None:
    claim = ClaimSchema(
        claim_id="EMP-RATE-AGE", source_sentence="2025년 9월 20대 고용률은 60.7%였다.",
        indicator="고용률", value=60.7, unit="%", time="2025년 9월",
        frequency="월", population="20대", calculation="DIRECT_VALUE", parse_status="AUTO_OK",
    )
    selected = apply_catalog_binding(
        claim, _concept("employment_rate", "고용률"),
        [_candidate("DT_OTHER", "T90", "고용률"), _candidate("DT_1DA7002S", "T90", "고용률")],
    )

    assert [item.tbl_id for item in selected] == ["DT_1DA7002S"]


def test_monthly_age_unemployment_rate_binding_keeps_age_dynamic() -> None:
    claim = ClaimSchema(
        claim_id="UNEMP-RATE-YOUTH",
        source_sentence="2024년 12월 청년 실업률은 5.9%였다.",
        indicator="실업률", value=5.9, unit="%", time="2024년 12월",
        frequency="월", population="청년",
        calculation="DIRECT_VALUE", parse_status="AUTO_OK",
    )
    selected = apply_catalog_binding(
        claim, _concept("unemployment_rate", "실업률"),
        [_candidate("DT_OTHER", "T80", "실업률"), _candidate("DT_1DA7002S", "T80", "실업률")],
    )

    assert [item.tbl_id for item in selected] == ["DT_1DA7002S"]


def test_explicit_korea_quarterly_growth_uses_official_gdp_growth_table() -> None:
    claim = ClaimSchema(
        claim_id="GDP-GROWTH-KR",
        source_sentence="2025년 1분기 우리나라 경제성장률은 -0.2%였다.",
        indicator="경제성장률", value=-0.2, unit="%", time="2025년 1분기",
        frequency="분기", region="대한민국",
        calculation="DIRECT_VALUE", parse_status="AUTO_OK",
    )
    target = KosisCandidateSchema(
        org_id="101", tbl_id="DT_2OEEO001", tbl_name="GDP 성장률(실질)",
        core_item_ids=["T1"], core_item_names=["GDP 성장률"],
        unit_names=["%"], item_units={"T1": "%"}, frequency="분기|년",
        dimension_members={"A": ["대한민국", "미국"]},
        dimension_member_codes={"A": {"대한민국": "1005", "미국": "2030"}},
        metadata_status="OFFICIAL_METADATA_READY",
    )

    selected = apply_catalog_binding(
        claim, _concept("economic_growth_rate", "경제성장률"),
        [_candidate("DT_2KAA905", "T1", "경제성장률"), target],
    )

    assert [item.tbl_id for item in selected] == ["DT_2OEEO001"]
    assert selected[0].dimension_member_codes["A"] == {"대한민국": "1005"}


def test_quarterly_education_unemployment_binding_selects_age_education_table() -> None:
    claim = ClaimSchema(
        claim_id="UNEMP-EDU", source_sentence="2025년 1분기 30대 고졸 실업률은 4.2%였다.",
        indicator="실업률", value=4.2, unit="%", time="2025년 1분기",
        frequency="분기", population="30대", dimension={"학력": "고졸"},
        calculation="DIRECT_VALUE", parse_status="AUTO_OK",
    )
    selected = apply_catalog_binding(
        claim, _concept("unemployment_rate", "실업률"),
        [_candidate("DT_1DA7103S", "T80", "실업률"), _candidate("DT_1DA7105S", "T80", "실업률")],
    )

    assert [item.tbl_id for item in selected] == ["DT_1DA7105S"]


def test_wrong_frequency_does_not_use_quarterly_education_binding() -> None:
    claim = ClaimSchema(
        claim_id="UNEMP-EDU-MONTH", source_sentence="2025년 1월 고졸 실업률은 4.2%였다.",
        indicator="실업률", value=4.2, unit="%", time="2025년 1월",
        frequency="월", dimension={"학력": "고졸"},
        calculation="DIRECT_VALUE", parse_status="AUTO_OK",
    )
    candidates = [_candidate("DT_1DA7103S", "T80", "실업률"), _candidate("DT_1DA7105S", "T80", "실업률")]

    assert apply_catalog_binding(
        claim, _concept("unemployment_rate", "실업률"), candidates
    ) == candidates


def test_exact_unique_value_repairs_stale_target_not_found_and_education_slot() -> None:
    source = "올해 1분기 고졸 실업률은 5.5%로 4년제 대학 이상 졸업자(6.9%)보다 낮았다."
    record = ClaimRegistryRecord(
        article_id="A1", sentence_id="1", article_published_at=date(2025, 6, 17),
        source_ref="frozen",
        claim=ClaimSchema(
            claim_id="UNEMP-REPAIR", source_sentence=source, indicator="실업률",
            value=5.5, unit="%", time="2025-Q1", frequency="Q",
            calculation="THRESHOLD", condition={"operator": "GTE"}, parse_status="AUTO_OK",
        ),
        slot_enrichment={"target_link_status": "TARGET_NOT_FOUND_IN_SOURCE"},
    )

    repaired = repair_exact_target_grounding(record)
    expression = repaired.slot_enrichment["target_numeric_expression"]
    guarded = apply_direct_value_child_guard(
        repaired.claim, target_expression=str(expression)
    )

    assert repaired.slot_enrichment["target_link_status"] == "SOURCE_GROUNDED"
    assert expression == "5.5%"
    assert guarded.dimension == {"학력": "고졸"}
    assert guarded.calculation == "DIRECT_VALUE"
    assert guarded.parse_status == "AUTO_OK"


def test_age_number_never_repairs_as_statistical_target() -> None:
    record = ClaimRegistryRecord(
        article_id="A2", sentence_id="1", article_published_at=date(2025, 1, 1),
        source_ref="frozen",
        claim=ClaimSchema(
            claim_id="AGE-BLOCK", source_sentence="20대 인구는 703만명이다.",
            indicator="인구", value=20, unit="대", time="2024", frequency="년",
            calculation="DIRECT_VALUE", parse_status="AUTO_OK",
        ),
        slot_enrichment={"target_link_status": "TARGET_NOT_FOUND_IN_SOURCE"},
    )

    assert repair_exact_target_grounding(record) == record

