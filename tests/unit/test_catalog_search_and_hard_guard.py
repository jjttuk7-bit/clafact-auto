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
