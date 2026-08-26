from core.catalog_binding import apply_catalog_binding, seed_catalog_bindings
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema


def test_catalog_binding_selects_least_disaggregated_monthly_employment_table() -> None:
    claim = ClaimSchema(
        claim_id="C1", source_sentence="2025년 3월 취업자 수는 2858만9000명이었다.",
        indicator="취업자 수", value=28589000, unit="명", time="2025년 3월",
        frequency="월", calculation="DIRECT_VALUE", parse_status="AUTO_OK",
    )
    concept = StandardConceptSchema(
        concept_id="C000005", canonical_name="취업자", standard_key="employment_count",
        matched_alias="취업자 수", status="MATCHED",
    )
    candidates = [
        KosisCandidateSchema(
            org_id="101", tbl_id=table_id, tbl_name=table_id,
            core_item_ids=["T30"], core_item_names=["취업자"], unit_names=["천명"],
            frequency="월 | 분기 | 년", metadata_status="READY",
        )
        for table_id in ("DT_1DA7001S", "DT_1DA7028S")
    ]

    result = apply_catalog_binding(claim, concept, candidates)

    assert [candidate.tbl_id for candidate in result] == ["DT_1DA7001S"]


def test_catalog_binding_selects_monthly_cpi_year_on_year_table() -> None:
    claim = ClaimSchema(
        claim_id="CPI-1", source_sentence="2025년 10월 소비자물가는 전년동월대비 2.4% 상승했다.",
        indicator="소비자 물가", value=2.4, unit="%", time="2025년 10월",
        frequency="월", calculation="DIRECT_VALUE", parse_status="AUTO_OK",
    )
    concept = StandardConceptSchema(
        concept_id="C000006", canonical_name="전년동월비(%)", standard_key="year_on_year_cpi_rate",
        matched_alias="소비자 물가", status="MATCHED",
    )
    candidates = [
        KosisCandidateSchema(
            org_id="101", tbl_id=table_id, tbl_name=table_id,
            core_item_ids=["T03"], core_item_names=["전년동월비(%)"],
            unit_names=["%"], frequency="월", metadata_status="READY",
        )
        for table_id in ("DT_1J22042", "DT_1YL20581")
    ]

    result = apply_catalog_binding(claim, concept, candidates)

    assert [candidate.tbl_id for candidate in result] == ["DT_1J22042"]


def test_seed_catalog_binding_adds_missing_applicable_official_table() -> None:
    claim = ClaimSchema(
        claim_id="IND-1", source_sentence="2025년 3월 제조업 취업자는 450만 명이다.",
        indicator="취업자 수", value=4_500_000, unit="명", time="2025년 3월",
        frequency="월", dimension={"산업": "제조업"}, calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )
    concept = StandardConceptSchema(
        concept_id="C000005", canonical_name="취업자", standard_key="employment_count",
        matched_alias="취업자 수", status="MATCHED",
    )
    seeded = seed_catalog_bindings(claim, concept, [])
    assert [(item.org_id, item.tbl_id) for item in seeded] == [("101", "DT_1DA7E06S_NEW")]
    assert seeded[0].metadata_status == "LIVE_SEARCH_UNRESOLVED"
    assert seeded[0].source_stat_id == "OFFICIAL_RECURRING_BINDING_SEED"


def test_seed_catalog_binding_does_not_duplicate_or_seed_wrong_axis() -> None:
    concept = StandardConceptSchema(
        concept_id="C000005", canonical_name="취업자", standard_key="employment_count",
        matched_alias="취업자 수", status="MATCHED",
    )
    existing = KosisCandidateSchema(
        org_id="101", tbl_id="DT_1DA7E06S_NEW", tbl_name="산업별 취업자",
        metadata_status="READY",
    )
    industry_claim = ClaimSchema(
        claim_id="IND-2", source_sentence="제조업 취업자는 450만 명이다.", indicator="취업자 수",
        value=4_500_000, unit="명", time="2025년 3월", frequency="월",
        dimension={"산업": "제조업"}, calculation="DIRECT_VALUE", parse_status="AUTO_OK",
    )
    age_claim = industry_claim.model_copy(update={"dimension": {"연령": "20대"}})
    assert seed_catalog_bindings(industry_claim, concept, [existing]) == [existing]
    assert seed_catalog_bindings(age_claim, concept, []) == []

def test_trade_product_binding_seeds_only_product_table() -> None:
    claim = ClaimSchema(
        claim_id="TRADE-1", source_sentence="2024년 아이스크림 수출액은 9150만달러였다.",
        indicator="수출액", value=91_500_000, unit="달러", time="2024년", frequency="년",
        dimension={"품목": "아이스크림"}, calculation="DIRECT_VALUE", parse_status="AUTO_OK",
    )
    concept = StandardConceptSchema(
        concept_id="TRADE", canonical_name="수출액", standard_key="export_value",
        matched_alias="수출액", status="MATCHED",
    )
    assert [(item.org_id, item.tbl_id) for item in seed_catalog_bindings(claim, concept, [])] == [
        ("360", "DT_1R11001_FRM101")
    ]


def test_trade_product_and_partner_does_not_seed_single_axis_table() -> None:
    claim = ClaimSchema(
        claim_id="TRADE-2", source_sentence="2024년 대미 라면 수출액은 1억달러였다.",
        indicator="수출액", value=100_000_000, unit="달러", time="2024년", frequency="년",
        dimension={"품목": "라면", "교역국": "미국"}, calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )
    concept = StandardConceptSchema(
        concept_id="TRADE", canonical_name="수출액", standard_key="export_value",
        matched_alias="수출액", status="MATCHED",
    )
    assert seed_catalog_bindings(claim, concept, []) == []
