from datetime import date

from core.official_evidence_service import OfficialEvidenceResolution
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord
from schemas.concept import StandardConceptSchema
from schemas.verdict import VerdictSchema


def _record(claim_id: str) -> ClaimRegistryRecord:
    return ClaimRegistryRecord(
        article_id=f"A-{claim_id}",
        sentence_id="1",
        article_published_at=date(2025, 1, 15),
        source_ref="gold_standard_v1",
        claim=ClaimSchema(
            claim_id=claim_id,
            source_sentence=f"{claim_id} 문장",
            indicator="취업자 수",
            value=1,
            unit="명",
            time="2024년 12월",
            frequency="월",
            parse_status="AUTO_OK",
        ),
    )


def test_official_batch_runner_uses_shared_service_and_applies_resumable_range() -> None:
    from core.official_e2e_batch_runner import run_official_e2e_batch

    calls: list[str] = []

    class Service:
        def resolve(self, claim, *, article_date):
            calls.append(claim.claim_id)
            return OfficialEvidenceResolution(
                concept=StandardConceptSchema(
                    concept_id="employment_count", canonical_name="취업자 수",
                    standard_key="employment_count", status="MATCHED",
                ),
                candidates=[],
                verdict=VerdictSchema(
                    claim_id=claim.claim_id, claim_value=1, evidence_values=[1],
                    calculated_value=1, verdict="MATCH", route_status="AUTO",
                    reason_code="WITHIN_TOLERANCE", explanation="matched", dataset_version="test", semantic_standard_version="test", kosis_catalog_version="test", matching_version="test", calculation_version="test",
                ),
            )

    rows = run_official_e2e_batch(
        [_record("C1"), _record("C2"), _record("C3")], Service(), start=1, limit=1
    )

    assert calls == ["C2"]
    assert [row["claim_id"] for row in rows] == ["C2"]
    assert rows[0]["route_status"] == "AUTO"
    assert rows[0]["reason_code"] == "WITHIN_TOLERANCE"
    assert rows[0]["official_value"] == 1


def test_official_batch_runner_converts_operational_stage_error_and_continues() -> None:
    from core.official_e2e_batch_runner import run_official_e2e_batch
    from core.operational_error import OperationalStageError

    class Service:
        def resolve(self, claim, *, article_date):
            if claim.claim_id == "C1":
                raise OperationalStageError("KOSIS_CATALOG", "diag123")
            return OfficialEvidenceResolution(
                concept=StandardConceptSchema(concept_id="employment_count", canonical_name="취업자 수", standard_key="employment_count", status="MATCHED"),
                candidates=[],
                verdict=VerdictSchema(
                    claim_id=claim.claim_id, claim_value=1, evidence_values=[1], calculated_value=1,
                    verdict="MATCH", route_status="AUTO", reason_code="WITHIN_TOLERANCE", explanation="matched",
                    dataset_version="test", semantic_standard_version="test", kosis_catalog_version="test", matching_version="test", calculation_version="test",
                ),
            )

    rows = run_official_e2e_batch([_record("C1"), _record("C2")], Service())

    assert [(row["claim_id"], row["route_status"], row["reason_code"]) for row in rows] == [
        ("C1", "HOLD", "KOSIS_CATALOG_UNAVAILABLE"),
        ("C2", "AUTO", "WITHIN_TOLERANCE"),
    ]
    assert rows[0]["diagnostic_id"] == "diag123"