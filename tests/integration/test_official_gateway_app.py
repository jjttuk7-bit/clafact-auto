from datetime import date

from fastapi.testclient import TestClient

from core.official_evidence_service import OfficialEvidenceResolution
from schemas.concept import StandardConceptSchema
from schemas.verdict import VerdictSchema


def test_gateway_verifies_structured_claim_through_injected_core_service() -> None:
    from gateway.official_gateway_app import create_gateway_app

    class Service:
        def __init__(self) -> None:
            self.received = None

        def resolve(self, claim, *, article_date):
            self.received = (claim, article_date)
            return OfficialEvidenceResolution(
                concept=StandardConceptSchema(
                    concept_id="C000008",
                    canonical_name="취업자 수",
                    standard_key="employment_count",
                    status="MATCHED",
                ),
                candidates=[],
                catalog_diagnostics={"metadata_itm_succeeded": 1},
                verdict=VerdictSchema(
                    claim_id=claim.claim_id,
                    verdict="UNDETERMINED",
                    route_status="HOLD",
                    reason_code="NO_EVIDENCE",
                    explanation="Official evidence is unavailable.",
                    dataset_version="test",
                    semantic_standard_version="test",
                    kosis_catalog_version="test",
                    matching_version="test",
                    calculation_version="test",
                ),
            )

    service = Service()
    client = TestClient(create_gateway_app(lambda: service, gateway_token="test-token"))

    response = client.post(
        "/verify",
        headers={"X-CLAFACT-GATEWAY-TOKEN": "test-token"},
        json={
            "claim": {
                "claim_id": "claim-1",
                "source_sentence": "2024년 12월 취업자 수는 전년 동월 대비 0.2% 감소했다.",
                "indicator": "취업자 수",
                "parse_status": "AUTO_OK",
            },
            "article_date": "2025-01-16",
        },
    )

    assert response.status_code == 200
    assert response.json()["concept"]["concept_id"] == "C000008"
    assert response.json()["catalog_diagnostics"] == {"metadata_itm_succeeded": 1}
    assert service.received[0].claim_id == "claim-1"
    assert service.received[1] == date(2025, 1, 16)


def test_gateway_rejects_request_without_shared_token() -> None:
    from gateway.official_gateway_app import create_gateway_app

    client = TestClient(create_gateway_app(lambda: None, gateway_token="test-token"))
    response = client.post(
        "/verify",
        json={
            "claim": {
                "claim_id": "claim-1",
                "source_sentence": "문장",
                "indicator": "취업자 수",
                "parse_status": "AUTO_OK",
            },
            "article_date": "2025-01-16",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "GATEWAY_AUTH_REQUIRED"

def test_gateway_returns_only_safe_kosis_probe_summary_with_valid_token() -> None:
    from gateway.official_gateway_app import create_gateway_app

    client = TestClient(
        create_gateway_app(
            lambda: None,
            gateway_token="test-token",
            kosis_metadata_probe=lambda: 17,
        )
    )

    response = client.get(
        "/diagnostics/kosis",
        headers={"X-CLAFACT-GATEWAY-TOKEN": "test-token"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "OK", "metadata_row_count": 17}