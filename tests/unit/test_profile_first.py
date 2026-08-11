from core.profile_first import resolve_profile_first
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema
from schemas.verification_profile import VerificationProfileSchema


def _claim(**updates: object) -> ClaimSchema:
    payload = {
        "claim_id": "claim-1",
        "source_sentence": "취업자 수는 2,800만 명이다.",
        "parse_status": "AUTO_OK",
    }
    payload.update(updates)
    return ClaimSchema.model_validate(payload)


def _concept(**updates: object) -> StandardConceptSchema:
    payload = {
        "concept_id": "employment-count",
        "canonical_name": "취업자 수",
        "standard_key": "employment_count",
        "status": "MATCHED",
    }
    payload.update(updates)
    return StandardConceptSchema.model_validate(payload)


def _profile(**updates: object) -> VerificationProfileSchema:
    payload = {
        "profile_id": "employment-count-v1",
        "claim_key": "employment_count",
        "calculation_type": "DIRECT_VALUE",
        "org_id": "101",
        "tbl_id": "DT_1DA7012",
        "itm_id": "T1",
        "prd_se": "월",
        "unit": "천명",
        "dataset_version": "registry-v1",
        "preprocess_version": "preprocess-v1",
        "claim_schema_version": "claim-v1",
        "semantic_standard_version": "concept-seed-v1",
        "kosis_catalog_version": "catalog-350-v1",
        "matching_version": "matching-v1",
        "calculation_version": "calculation-v1",
    }
    payload.update(updates)
    return VerificationProfileSchema.model_validate(payload)


def test_selects_the_profile_with_an_exact_standard_key() -> None:
    profile = _profile()

    result = resolve_profile_first(_claim(), _concept(), [profile])

    assert result.status == "MATCHED"
    assert result.profile == profile
    assert result.reason_code is None

def test_returns_not_found_for_a_standard_key_without_a_profile() -> None:
    result = resolve_profile_first(_claim(), _concept(), [_profile(claim_key="other_key")])

    assert result.status == "NOT_FOUND"
    assert result.profile is None
    assert result.reason_code is None


def test_holds_when_claim_calculation_conflicts_with_profile() -> None:
    result = resolve_profile_first(
        _claim(calculation="GROWTH_RATE"), _concept(), [_profile()]
    )

    assert result.status == "HOLD"
    assert result.reason_code == "PROFILE_CALCULATION_CONFLICT"


def test_holds_when_multiple_profiles_share_the_standard_key() -> None:
    result = resolve_profile_first(
        _claim(), _concept(), [_profile(), _profile(profile_id="employment-count-v2")]
    )

    assert result.status == "HOLD"
    assert result.reason_code == "PROFILE_KEY_CONFLICT"


def test_holds_when_profile_coordinate_is_incomplete() -> None:
    incomplete = _profile().model_copy(update={"tbl_id": ""})

    result = resolve_profile_first(_claim(), _concept(), [incomplete])

    assert result.status == "HOLD"
    assert result.reason_code == "PROFILE_COORDINATE_INCOMPLETE"


def test_selects_profile_when_declared_applicability_constraints_match() -> None:
    profile = _profile(
        frequency_constraint="월",
        region_constraint="전국",
        population_constraint="전체",
        condition_constraint={"seasonal_adjustment": "계절조정"},
    )

    result = resolve_profile_first(
        _claim(
            frequency="monthly",
            region="전국",
            population="전체",
            condition={"seasonal_adjustment": "계절조정"},
        ),
        _concept(),
        [profile],
    )

    assert result.status == "MATCHED"

def test_holds_when_declared_frequency_constraint_conflicts() -> None:
    result = resolve_profile_first(
        _claim(frequency="년"),
        _concept(),
        [_profile(frequency_constraint="월")],
    )

    assert result.status == "HOLD"
    assert result.reason_code == "PROFILE_FREQUENCY_CONFLICT"


def test_holds_when_declared_region_constraint_conflicts() -> None:
    result = resolve_profile_first(
        _claim(region="서울"),
        _concept(),
        [_profile(region_constraint="전국")],
    )

    assert result.status == "HOLD"
    assert result.reason_code == "PROFILE_REGION_CONFLICT"


def test_holds_when_declared_population_constraint_conflicts() -> None:
    result = resolve_profile_first(
        _claim(population="청년"),
        _concept(),
        [_profile(population_constraint="전체")],
    )

    assert result.status == "HOLD"
    assert result.reason_code == "PROFILE_POPULATION_CONFLICT"


def test_holds_when_declared_condition_constraint_conflicts() -> None:
    result = resolve_profile_first(
        _claim(condition={"seasonal_adjustment": "원계열"}),
        _concept(),
        [_profile(condition_constraint={"seasonal_adjustment": "계절조정"})],
    )

    assert result.status == "HOLD"
    assert result.reason_code == "PROFILE_CONDITION_CONFLICT"


def test_holds_when_required_profile_constraint_is_missing_from_claim() -> None:
    result = resolve_profile_first(
        _claim(frequency=None, region=None, population=None, condition=None),
        _concept(),
        [
            _profile(
                frequency_constraint="월",
                region_constraint="전국",
                population_constraint="전체",
                condition_constraint={"seasonal_adjustment": "계절조정"},
            )
        ],
    )

    assert result.status == "HOLD"
    assert result.reason_code == "PROFILE_FREQUENCY_UNRESOLVED"

def test_holds_when_declared_dimension_constraint_conflicts() -> None:
    result = resolve_profile_first(
        _claim(dimension={"raw": "여성"}),
        _concept(),
        [_profile(dimension_constraint={"raw": "전체"})],
    )

    assert result.status == "HOLD"
    assert result.reason_code == "PROFILE_DIMENSION_CONFLICT"


def test_selects_precomputed_official_rate_profile_for_compatible_growth_claim() -> None:
    profile = _profile(accepted_claim_calculations=["GROWTH_RATE"])

    result = resolve_profile_first(
        _claim(calculation="GROWTH_RATE"), _concept(), [profile]
    )

    assert result.status == "MATCHED"
