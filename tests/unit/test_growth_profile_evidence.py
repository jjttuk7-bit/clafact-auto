from core.verification_evidence_service import resolve_profile_evidence
from schemas.claim import ClaimSchema
from schemas.verification_profile import VerificationProfileSchema


def test_growth_profile_accepts_percent_claim_and_index_evidence_unit() -> None:
    claim = ClaimSchema(claim_id="C", source_sentence="", unit="%", frequency="M", calculation="GROWTH_RATE", parse_status="AUTO_OK")
    profile = VerificationProfileSchema.model_validate({"profile_id":"p","claim_key":"k","calculation_type":"GROWTH_RATE","org_id":"101","tbl_id":"DT","itm_id":"T","prd_se":"M","unit":"2020=100","dataset_version":"d","preprocess_version":"p","claim_schema_version":"c","semantic_standard_version":"s","kosis_catalog_version":"k","matching_version":"m","calculation_version":"v"})
    result = resolve_profile_evidence(claim, profile, period="202510")
    assert result.status == "CONFIRMED"
