from core.verification_evidence_service import resolve_profile_evidence
from schemas.claim import ClaimSchema
from schemas.verification_profile import VerificationProfileSchema


def _claim(**updates: object) -> ClaimSchema:
    payload = {
        "claim_id": "claim-1",
        "source_sentence": "2025년 3월 취업자 수는 2,800만 명이다.",
        "unit": "천명",
        "time": "2025년 3월",
        "frequency": "월",
        "parse_status": "AUTO_OK",
    }
    payload.update(updates)
    return ClaimSchema.model_validate(payload)


def _profile(**updates: object) -> VerificationProfileSchema:
    payload = {
        "profile_id": "employment-count-v1",
        "claim_key": "employment_count",
        "calculation_type": "DIRECT_VALUE",
        "org_id": "101",
        "tbl_id": "DT_1DA7028S",
        "itm_id": "T30",
        "prd_se": "월",
        "unit": "천명",
        "dimension_codes": {"B": "0", "J": "00"},
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


def test_builds_confirmed_evidence_cell_from_profile_and_period() -> None:
    result = resolve_profile_evidence(_claim(), _profile(), period="2025-03")

    assert result.status == "CONFIRMED"
    assert result.evidence_cell is not None
    assert result.evidence_cell.dimension_codes == {"B": "0", "J": "00"}
    assert result.evidence_cell.canonical_key == (
        "ORG=101|TBL=DT_1DA7028S|ITM=T30|PRD_SE=월|PRD_DE=2025-03|DIMS=B:0,J:00"
    )


def test_holds_when_resolved_period_is_missing() -> None:
    result = resolve_profile_evidence(_claim(), _profile(), period=None)

    assert result.status == "HOLD"
    assert result.reason_code == "EVIDENCE_PERIOD_MISSING"


def test_holds_when_claim_unit_conflicts_with_profile_unit() -> None:
    result = resolve_profile_evidence(_claim(unit="%"), _profile(), period="2025-03")

    assert result.status == "HOLD"
    assert result.reason_code == "EVIDENCE_UNIT_MISMATCH"


def test_holds_when_claim_frequency_conflicts_with_profile_frequency() -> None:
    result = resolve_profile_evidence(_claim(frequency="년"), _profile(), period="2025-03")

    assert result.status == "HOLD"
    assert result.reason_code == "EVIDENCE_FREQUENCY_MISMATCH"


def test_holds_when_claim_is_not_auto_ok() -> None:
    result = resolve_profile_evidence(
        _claim(parse_status="HOLD"), _profile(), period="2025-03"
    )

    assert result.status == "HOLD"
    assert result.reason_code == "CLAIM_NOT_AUTO_OK"
