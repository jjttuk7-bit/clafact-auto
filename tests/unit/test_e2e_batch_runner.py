from datetime import date

from core.e2e_batch_runner import run_e2e_batch, summarize_e2e_batch
from schemas.claim_registry import ClaimRegistryRecord
from schemas.concept import StandardConceptSchema
from schemas.verification_profile import VerificationProfileSchema


def _record() -> ClaimRegistryRecord:
    return ClaimRegistryRecord.model_validate({"article_id":"A1","sentence_id":"S1","article_published_at":"2025-04-01","source_ref":"test","claim":{"claim_id":"C1","source_sentence":"2025년 3월 취업자 수는 2,800만 명이다.","unit":"천명","time":"2025년 3월","frequency":"월","calculation":"DIRECT_VALUE","parse_status":"AUTO_OK"}})


def _profile() -> VerificationProfileSchema:
    return VerificationProfileSchema.model_validate({"profile_id":"employment-v1","claim_key":"employment_count","calculation_type":"DIRECT_VALUE","org_id":"101","tbl_id":"DT","itm_id":"T1","prd_se":"월","unit":"천명","dataset_version":"d1","preprocess_version":"p1","claim_schema_version":"c1","semantic_standard_version":"s1","kosis_catalog_version":"k1","matching_version":"m1","calculation_version":"v1"})


def test_e2e_batch_uses_profile_evidence_and_snapshot_value() -> None:
    result = run_e2e_batch([_record()], [_profile()], {("A1", "S1"): StandardConceptSchema(concept_id="x", canonical_name="취업자 수", standard_key="employment_count", status="MATCHED")}, api_lookup=lambda _cell: [{"tbl_id":"DT","item_id":"T1","period":"202503","value":28000,"LST_CHN_DE":"2025-03-31"}])
    assert result[0]["route_status"] == "AUTO"
    assert result[0]["official_value"] == 28000.0
    assert result[0]["versions"]["dataset_version"] == "d1"


def test_e2e_batch_holds_when_no_profile_matches() -> None:
    result = run_e2e_batch([_record()], [], {("A1", "S1"): StandardConceptSchema(concept_id="x", canonical_name="취업자 수", standard_key="employment_count", status="MATCHED")})
    assert result[0]["route_status"] == "HOLD"
    assert result[0]["reason_code"] == "PROFILE_NOT_FOUND"


def test_e2e_report_counts_routes_and_coverage() -> None:
    report = summarize_e2e_batch([{ "route_status":"AUTO", "official_value":1.0, "reason_code":None, "profile_id":"p" }, {"route_status":"HOLD", "official_value":None, "reason_code":"PROFILE_NOT_FOUND", "profile_id":None}])
    assert report["route_counts"] == {"AUTO": 1, "HOLD": 1}
    assert report["snapshot_coverage"] == {"with_official_value": 1, "without_official_value": 1}
