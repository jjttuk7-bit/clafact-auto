from core.catalog_search import search_semantic_catalog
from core.hard_guard import apply_hard_guard
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema


def candidate(**updates: object) -> KosisCandidateSchema:
    payload: dict[str, object] = {
        "org_id": "101",
        "tbl_id": "DT_EMPLOYMENT",
        "tbl_name": "경제활동인구조사 고용률",
        "core_item_names": ["고용률"],
        "dimension_names": ["성별", "연령별", "시도별"],
        "unit_names": ["%"],
        "frequency": "YEAR",
        "start_period": "2020",
        "end_period": "2024",
        "metadata_status": "READY",
    }
    payload.update(updates)
    return KosisCandidateSchema(**payload)


def claim(**updates: object) -> ClaimSchema:
    payload: dict[str, object] = {
        "claim_id": "C1",
        "source_sentence": "2024년 서울 고용률은 70%였다.",
        "indicator": "고용률",
        "value": 70.0,
        "unit": "%",
        "time": "2024",
        "frequency": "YEAR",
        "region": "서울",
        "parse_status": "AUTO_OK",
    }
    payload.update(updates)
    return ClaimSchema(**payload)


def concept() -> StandardConceptSchema:
    return StandardConceptSchema(
        concept_id="C001",
        canonical_name="고용률",
        standard_key="employment_rate",
        matched_alias="취업률",
        status="MATCHED",
    )


def test_catalog_search_returns_matching_candidate() -> None:
    result = search_semantic_catalog(claim(), concept(), [candidate()])

    assert [item.tbl_id for item in result] == ["DT_EMPLOYMENT"]


def test_catalog_search_excludes_unrelated_candidate() -> None:
    result = search_semantic_catalog(
        claim(), concept(), [candidate(tbl_id="DT_PRICE", tbl_name="소비자물가", core_item_names=["물가"])]
    )

    assert result == []


def test_catalog_search_respects_top_k_and_stable_table_order() -> None:
    result = search_semantic_catalog(
        claim(), concept(), [candidate(tbl_id="B"), candidate(tbl_id="A")], top_k=1
    )

    assert [item.tbl_id for item in result] == ["A"]


def test_catalog_search_returns_no_candidates_for_unresolved_concept() -> None:
    unresolved = concept().model_copy(update={"status": "UNRESOLVED", "concept_id": "UNRESOLVED"})

    assert search_semantic_catalog(claim(), unresolved, [candidate()]) == []


def test_hard_guard_passes_compatible_candidate() -> None:
    result = apply_hard_guard(claim(dimension={"sex": "전체"}, population="15세 이상"), candidate())

    assert result.passed is True
    assert result.reject_codes == []


def test_hard_guard_rejects_frequency_conflict() -> None:
    result = apply_hard_guard(claim(frequency="MONTH"), candidate())

    assert result.reject_codes == ["FREQUENCY_CONFLICT"]


def test_hard_guard_rejects_unit_conflict() -> None:
    result = apply_hard_guard(claim(unit="명"), candidate())

    assert result.reject_codes == ["UNIT_CONFLICT"]


def test_hard_guard_rejects_missing_age_dimension() -> None:
    result = apply_hard_guard(claim(population="15세 이상", region="전국"), candidate(dimension_names=["성별"]))

    assert result.reject_codes == ["AGE_DIMENSION_REQUIRED"]


def test_hard_guard_rejects_missing_sex_dimension() -> None:
    result = apply_hard_guard(claim(dimension={"sex": "여성"}, region="전국"), candidate(dimension_names=["연령별"]))

    assert result.reject_codes == ["SEX_DIMENSION_REQUIRED"]


def test_hard_guard_rejects_unavailable_time() -> None:
    result = apply_hard_guard(claim(time="2019"), candidate())

    assert result.reject_codes == ["TIME_NOT_AVAILABLE"]


def test_hard_guard_rejects_forecast_claim() -> None:
    result = apply_hard_guard(claim(source_sentence="내년 고용률은 70%가 될 전망이다."), candidate())

    assert result.reject_codes == ["FORECAST_CLAIM"]


def test_catalog_search_matches_count_suffix_to_official_item_name() -> None:
    employment = claim(indicator="취업자 수", unit="명", frequency="월")
    employment_concept = concept().model_copy(update={"canonical_name": "취업자 수", "standard_key": "employment_count"})
    result = search_semantic_catalog(
        employment,
        employment_concept,
        [candidate(tbl_name="경제활동인구", core_item_names=["취업자"], unit_names=["천명"], frequency="월")],
    )

    assert [item.tbl_id for item in result] == ["DT_EMPLOYMENT"]


def test_catalog_search_ranks_candidates_using_frequency_and_region_slots() -> None:
    result = search_semantic_catalog(
        claim(frequency="MONTH", region="서울"),
        concept(),
        [
            candidate(tbl_id="A", frequency="YEAR", dimension_names=["성별"]),
            candidate(tbl_id="B", frequency="MONTH", dimension_names=["시도별"]),
        ],
    )

    assert [item.tbl_id for item in result] == ["B", "A"]

def test_hard_guard_treats_korean_annual_aliases_as_compatible() -> None:
    result = apply_hard_guard(claim(frequency="연", region="전국"), candidate(frequency="년"))

    assert result.passed is True

def test_hard_guard_requires_claim_dimension_member_in_official_metadata() -> None:
    cpi_claim = claim(
        source_sentence="지난달 가공식품 물가는 전년 대비 3.1% 올랐다.",
        indicator="가공식품 물가", frequency="월", region=None,
        dimension={"품목": "가공식품"}, calculation="GROWTH_RATE",
    )
    wrong = candidate(
        tbl_id="WRONG", frequency="월",
        dimension_names=["품목별"], dimension_members={"I": ["신선식품"]},
        metadata_status="OFFICIAL_ITEM_METADATA_READY",
    )
    correct = wrong.model_copy(update={
        "tbl_id": "DT_1J22112",
        "dimension_members": {"I": ["가공식품", "신선식품"]},
    })

    assert apply_hard_guard(cpi_claim, wrong).reject_codes == ["DIMENSION_MEMBER_CONFLICT"]
    assert apply_hard_guard(cpi_claim, correct).passed is True


def test_hard_guard_rejects_official_item_metadata_without_required_period_metadata() -> None:
    incomplete = candidate(
        frequency=None, metadata_status="OFFICIAL_ITEM_METADATA_READY",
    )

    assert apply_hard_guard(claim(frequency="월", region="전국"), incomplete).reject_codes == ["METADATA_INCOMPLETE"]


def test_hard_guard_unwraps_raw_json_dimension_before_official_member_check() -> None:
    country_claim = claim(
        source_sentence="지난해 대미 수출액은 1277억8600만달러였다.",
        indicator="수출액", value=127_786_000_000, unit="달러", time="2024",
        frequency="Y", region=None,
        dimension={"raw": '{"교역상대국": ["미국"]}'},
        calculation="DIRECT_VALUE",
    )
    country_table = candidate(
        tbl_id="DT_COUNTRY_EXPORT", tbl_name="국가별 수출액, 수입액",
        core_item_names=["수출액"], unit_names=["천달러"], frequency="년",
        dimension_names=["국가별"], dimension_members={"NARA": ["미국", "중국"]},
    )

    assert apply_hard_guard(country_claim, country_table).passed is True

def test_hard_guard_accepts_claim_dimension_bound_by_official_table_name() -> None:
    from core.hard_guard import apply_hard_guard

    claim = ClaimSchema(
        claim_id="COSMETICS",
        source_sentence="지난해 화장품 수출액은 68억달러였다.",
        indicator="수출액",
        value=6_800_000_000,
        unit="달러",
        time="2024",
        frequency="Y",
        dimension={"raw": '{"품목": ["화장품"]}'},
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )
    candidate = KosisCandidateSchema(
        org_id="145",
        tbl_id="DT_145011_A006",
        tbl_name="화장품 수입 및 수출액 현황",
        core_item_ids=["T002"],
        core_item_names=["수출액"],
        dimension_ids=["13999000"],
        dimension_names=["가상분류"],
        dimension_members={"13999000": ["데이터"]},
        dimension_member_codes={"13999000": {"데이터": "DATA"}},
        unit_names=["천$"],
        item_units={"T002": "천$"},
        frequency="년",
        start_period="1995",
        end_period="2024",
        metadata_status="OFFICIAL_METADATA_READY",
    )

    result = apply_hard_guard(claim, candidate)

    assert result.passed is True
    assert "DIMENSION_MEMBER_CONFLICT" not in result.reject_codes
def test_hard_guard_accepts_korean_gender_alias_for_official_member() -> None:
    result = apply_hard_guard(
        claim(dimension={"sex": "여성"}, region="전국"),
        candidate(
            dimension_names=["성별"],
            dimension_members={"B": ["계", "남자", "여자"]},
            dimension_member_codes={"B": {"계": "0", "남자": "2", "여자": "3"}},
        ),
    )

    assert result.passed is True
    assert result.reject_codes == []
def test_hard_guard_accepts_official_region_and_age_spelling_variants() -> None:
    result = apply_hard_guard(
        claim(region="서울", population="15~29세", dimension={"sex": "여성"}),
        candidate(
            dimension_names=["시도별", "성별", "연령계층별"],
            dimension_members={"A": ["서울특별시"], "B": ["여자"], "G": ["15 - 29세"]},
            dimension_member_codes={"A": {"서울특별시": "11"}, "B": {"여자": "3"}, "G": {"15 - 29세": "75"}},
        ),
    )

    assert result.passed is True

def test_hard_guard_accepts_gender_and_age_member_spelling_variants() -> None:
    result = apply_hard_guard(
        claim(dimension={"sex": "여성", "age": "15~29세"}, region="전국"),
        candidate(
            dimension_names=["성별", "연령계층별"],
            dimension_members={"B": ["여자"], "G": ["15 - 29세"]},
            dimension_member_codes={"B": {"여자": "3"}, "G": {"15 - 29세": "75"}},
        ),
    )

    assert "DIMENSION_MEMBER_CONFLICT" not in result.reject_codes

def test_hard_guard_allows_direct_value_query_when_item_metadata_and_frequency_are_confirmed() -> None:
    result = apply_hard_guard(
        claim(frequency="월", region="전국"),
        candidate(
            core_item_ids=["T30"],
            frequency="월",
            dimension_member_codes={"B": {"계": "0"}},
            metadata_status="OFFICIAL_PERIOD_METADATA_UNAVAILABLE",
        ),
    )

    assert result.passed is True
    assert result.reject_codes == []


def test_hard_guard_rejects_non_age_population_missing_from_official_scope() -> None:
    youth_claim = claim(
        source_sentence="청년 실업률은 5.9%였다.",
        indicator="실업률",
        population="청년",
        region="전국",
    )
    total_only = candidate(
        tbl_name="경제활동인구 총괄",
        core_item_names=["실업률"],
        dimension_names=["성별"],
        dimension_members={"B": ["계"]},
    )

    assert apply_hard_guard(youth_claim, total_only).reject_codes == [
        "POPULATION_DIMENSION_CONFLICT"
    ]


def test_hard_guard_accepts_non_age_population_confirmed_by_official_scope() -> None:
    youth_claim = claim(
        source_sentence="청년 실업률은 5.9%였다.",
        indicator="실업률",
        population="청년",
        region="전국",
    )
    youth_table = candidate(
        tbl_name="청년층 실업률",
        core_item_names=["실업률"],
        dimension_names=["연령계층별"],
        dimension_members={"G": ["청년층"]},
    )

    assert apply_hard_guard(youth_claim, youth_table).passed is True
