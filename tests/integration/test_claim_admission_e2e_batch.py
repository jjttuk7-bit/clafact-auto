from datetime import date

from core.claim_admission_e2e_batch_runner import run_claim_admission_e2e_batch
from core.official_evidence_service import OfficialEvidenceResolution
from schemas.claim import ClaimSchema
from schemas.claim_admission import AdmissionDecision
from schemas.claim_registry import ClaimRegistryRecord
from schemas.concept import StandardConceptSchema
from schemas.verdict import VerdictSchema


def record(claim_id: str, sentence: str) -> ClaimRegistryRecord:
    return ClaimRegistryRecord(
        article_id=f"A-{claim_id}",
        sentence_id="1",
        article_published_at=date(2025, 6, 10),
        source_ref="test",
        claim=ClaimSchema(
            claim_id=claim_id,
            source_sentence=sentence,
            indicator="취업자 수",
            value=100,
            unit="명",
            time="2025-05",
            frequency="월",
            calculation="DIRECT_VALUE",
            parse_status="AUTO_OK",
        ),
    )


def resolution(claim_id: str) -> OfficialEvidenceResolution:
    return OfficialEvidenceResolution(
        concept=StandardConceptSchema(
            concept_id="employment_count", canonical_name="취업자 수",
            standard_key="employment_count", status="MATCHED",
        ),
        candidates=[],
        verdict=VerdictSchema(
            claim_id=claim_id, claim_value=100, evidence_values=[100], calculated_value=100,
            verdict="MATCH", route_status="AUTO", reason_code="WITHIN_TOLERANCE",
            explanation="matched", dataset_version="test", semantic_standard_version="test",
            kosis_catalog_version="test", matching_version="test", calculation_version="test",
        ),
    )


def test_batch_calls_official_service_only_for_admitted_claims() -> None:
    calls: list[str] = []

    class Service:
        def resolve(self, claim, *, article_date):
            calls.append(claim.claim_id)
            return resolution(claim.claim_id)

    rows = run_claim_admission_e2e_batch([
        record("C-eligible", "지난달 제조업 취업자는 100명이었다."),
        record("C-policy", "정부는 1인당 15만원의 소비쿠폰을 지급한다."),
    ], Service())

    assert calls == ["C-eligible"]
    assert [(row["claim_id"], row["route_status"], row["admission_label"]) for row in rows] == [
        ("C-eligible", "AUTO", "KOSIS_PIPELINE_ELIGIBLE"),
        ("C-policy", "ADMISSION_ROUTED", "NOT_A_VERIFIABLE_CLAIM"),
    ]
    assert rows[0]["official_result"]["reason_code"] == "WITHIN_TOLERANCE"
    assert rows[1]["official_result"] is None
    assert rows[1]["admission_events"][0]["stage"] == "CLAIM_ADMISSION"


def test_batch_passes_source_record_to_contextual_admission_router() -> None:
    seen: list[tuple[str, str]] = []

    class Service:
        def resolve(self, claim, *, article_date):
            return resolution(claim.claim_id)

    def router(source_record: ClaimRegistryRecord, claim: ClaimSchema) -> AdmissionDecision:
        seen.append((source_record.article_id, claim.claim_id))
        return AdmissionDecision(
            label="NOT_A_VERIFIABLE_CLAIM", reason_code="TEST_CONTEXTUAL_ROUTER"
        )

    rows = run_claim_admission_e2e_batch(
        [record("C-context", "정부는 1인당 15만원의 소비쿠폰을 지급한다.")],
        Service(),
        contextual_admission_router=router,
    )

    assert seen == [("A-C-context", "C-context")]
    assert rows[0]["route_status"] == "ADMISSION_ROUTED"
    assert rows[0]["admission_reason_code"] == "TEST_CONTEXTUAL_ROUTER"
