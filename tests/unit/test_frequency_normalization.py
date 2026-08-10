from core.verification_evidence_service import resolve_profile_evidence
from schemas.claim import ClaimSchema
from schemas.verification_profile import VerificationProfileSchema


def test_profile_evidence_accepts_monthly_for_kosis_m_frequency() -> None:
    claim = ClaimSchema(claim_id="C", source_sentence="", frequency="monthly", calculation="GROWTH_RATE", parse_status="AUTO_OK")
    profile = VerificationProfileSchema.model_validate({"profile_id":"p","claim_key":"k","calculation_type":"GROWTH_RATE","org_id":"101","tbl_id":"DT","itm_id":"T","prd_se":"M","unit":"2020=100","dataset_version":"d","preprocess_version":"p","claim_schema_version":"c","semantic_standard_version":"s","kosis_catalog_version":"k","matching_version":"m","calculation_version":"v"})
    assert resolve_profile_evidence(claim, profile, period="202510").status == "CONFIRMED"
