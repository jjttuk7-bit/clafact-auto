from datetime import date

from core.e2e_batch_runner import run_e2e_batch, summarize_e2e_batch
from schemas.claim_registry import ClaimRegistryRecord
from schemas.concept import StandardConceptSchema
from schemas.verification_profile import VerificationProfileSchema


def _record() -> ClaimRegistryRecord:
    return ClaimRegistryRecord.model_validate({"article_id":"A1","sentence_id":"S1","article_published_at":"2025-04-01","source_ref":"test","claim":{"claim_id":"C1","source_sentence":"2025년 3월 취업자 수는 2,800만 명이다.","value":28000,"unit":"천명","time":"2025년 3월","frequency":"월","calculation":"DIRECT_VALUE","parse_status":"AUTO_OK"}})


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


def test_e2e_batch_isolates_one_record_error_and_continues(monkeypatch) -> None:
    import core.e2e_batch_runner as runner

    records = [_record(), _record().model_copy(update={"article_id": "A2", "sentence_id": "S2", "claim": _record().claim.model_copy(update={"claim_id": "C2"})})]
    concepts = {
        ("A1", "S1"): StandardConceptSchema(concept_id="x", canonical_name="취업자 수", standard_key="employment_count", status="MATCHED"),
        ("A2", "S2"): StandardConceptSchema(concept_id="x", canonical_name="취업자 수", standard_key="employment_count", status="MATCHED"),
    }
    original = runner.resolve_profile_first

    def raise_for_first(claim, concept, profiles):
        if claim.claim_id == "C1":
            raise RuntimeError("simulated profile failure")
        return original(claim, concept, profiles)

    monkeypatch.setattr(runner, "resolve_profile_first", raise_for_first)
    results = runner.run_e2e_batch(records, [], concepts)

    assert [row["reason_code"] for row in results] == ["BATCH_RECORD_ERROR", "PROFILE_NOT_FOUND"]
    assert all(row["route_status"] == "HOLD" for row in results)


def test_e2e_batch_uses_registered_direct_value_when_claim_calculation_is_missing() -> None:
    record = _record().model_copy(update={"claim": _record().claim.model_copy(update={"calculation": None})})
    result = run_e2e_batch(
        [record],
        [_profile()],
        {("A1", "S1"): StandardConceptSchema(concept_id="x", canonical_name="취업자 수", standard_key="employment_count", status="MATCHED")},
        api_lookup=lambda _cell: [{"tbl_id": "DT", "item_id": "T1", "period": "202503", "value": 28000, "LST_CHN_DE": "2025-03-31"}],
    )

    assert result[0]["route_status"] == "AUTO"
    assert result[0]["official_value"] == 28000.0


def test_e2e_batch_compares_direct_values_after_profile_unit_conversion() -> None:
    record = _record().model_copy(
        update={
            "claim": _record().claim.model_copy(
                update={"value": 28_000_000, "unit": "명"}
            )
        }
    )
    result = run_e2e_batch(
        [record],
        [_profile()],
        {("A1", "S1"): StandardConceptSchema(concept_id="x", canonical_name="취업자 수", standard_key="employment_count", status="MATCHED")},
        api_lookup=lambda _cell: [{"tbl_id": "DT", "item_id": "T1", "period": "202503", "value": 28000, "LST_CHN_DE": "2025-03-31"}],
    )

    assert result[0]["route_status"] == "AUTO"
    assert result[0]["verdict"] == "MATCH"
    assert result[0]["claim_value_in_profile_unit"] == 28000.0
