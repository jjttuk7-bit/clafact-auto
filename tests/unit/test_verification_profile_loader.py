import json
from pathlib import Path

import pytest

from core.verification_profile_loader import load_verification_profiles
from schemas.verification_profile import VerificationProfileSchema


def _profile(**updates: object) -> dict[str, object]:
    profile = {
        "profile_id": "employment-count-v1",
        "claim_key": "employment_count",
        "calculation_type": "DIRECT_VALUE",
        "org_id": "101",
        "tbl_id": "DT_1DA7012",
        "itm_id": "T1",
        "prd_se": "월",
        "unit": "천명",
        "dimension_codes": {"C1": "TOTAL"},
        "dataset_version": "registry-v1",
        "preprocess_version": "preprocess-v1",
        "claim_schema_version": "claim-v1",
        "semantic_standard_version": "concept-seed-v1",
        "kosis_catalog_version": "catalog-350-v1",
        "matching_version": "matching-v1",
        "calculation_version": "calculation-v1",
    }
    profile.update(updates)
    return profile


def test_profile_schema_accepts_complete_official_coordinate() -> None:
    profile = VerificationProfileSchema.model_validate(_profile())

    assert profile.profile_id == "employment-count-v1"
    assert profile.calculation_type == "DIRECT_VALUE"


def test_profile_schema_rejects_unsupported_calculation_type() -> None:
    with pytest.raises(ValueError, match="calculation_type"):
        VerificationProfileSchema.model_validate(_profile(calculation_type="FREE_TEXT"))


def test_profile_schema_requires_all_version_fields() -> None:
    invalid = _profile()
    invalid.pop("matching_version")

    with pytest.raises(ValueError, match="matching_version"):
        VerificationProfileSchema.model_validate(invalid)


def test_profile_schema_requires_profile_owned_evidence_metadata() -> None:
    invalid = _profile()
    invalid.pop("prd_se")

    with pytest.raises(ValueError, match="prd_se"):
        VerificationProfileSchema.model_validate(invalid)


def test_loader_returns_typed_profiles_from_versioned_document(tmp_path: Path) -> None:
    path = tmp_path / "verification_profiles_v1.json"
    path.write_text(
        json.dumps({"profile_schema_version": "v1", "profiles": [_profile()]}),
        encoding="utf-8",
    )

    profiles = load_verification_profiles(path)

    assert [profile.profile_id for profile in profiles] == ["employment-count-v1"]


def test_loader_rejects_duplicate_profile_ids(tmp_path: Path) -> None:
    path = tmp_path / "verification_profiles_v1.json"
    path.write_text(
        json.dumps({"profile_schema_version": "v1", "profiles": [_profile(), _profile()]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Duplicate verification profile ID"):
        load_verification_profiles(path)
