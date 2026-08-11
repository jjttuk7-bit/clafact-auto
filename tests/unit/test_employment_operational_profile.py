from pathlib import Path

from core.verification_profile_loader import load_verification_profiles


def test_employment_profile_has_verified_total_coordinate() -> None:
    profiles = load_verification_profiles(Path("data/verification_profiles/employment_count_v1.json"))

    assert len(profiles) == 1
    profile = profiles[0]
    assert profile.claim_key == "employment_count"
    assert profile.calculation_type == "DIRECT_VALUE"
    assert (profile.org_id, profile.tbl_id, profile.itm_id) == ("101", "DT_1DA7028S", "T30")
    assert profile.dimension_codes == {"C1": "0", "C2": "00"}
    assert profile.frequency_constraint == "M"


def test_employment_profile_selects_only_its_declared_claim_scope() -> None:
    from core.profile_first import resolve_profile_first
    from schemas.claim import ClaimSchema
    from schemas.concept import StandardConceptSchema

    profile = load_verification_profiles(Path("data/verification_profiles/employment_count_v1.json"))[0]
    claim = ClaimSchema.model_validate(
        {
            "claim_id": "employment-202503",
            "source_sentence": "employment total",
            "indicator": "employment",
            "value": 28589,
            "unit": "thousand persons",
            "time": "2025-03",
            "frequency": "monthly",
            "region": "\uC804\uAD6D",
            "population": "\uCDE8\uC5C5\uC790",
            "dimension": {"raw": "\uC804\uCCB4"},
            "calculation": "DIRECT_VALUE",
            "parse_status": "AUTO_OK",
        }
    )
    concept = StandardConceptSchema.model_validate(
        {"concept_id": "employment", "canonical_name": "employment", "standard_key": "employment_count", "status": "MATCHED"}
    )

    result = resolve_profile_first(claim, concept, [profile])

    assert result.status == "MATCHED"
    assert result.profile == profile
