from datetime import date

from core.official_evidence_service import OfficialEvidenceResolution
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema
from schemas.verdict import VerdictSchema


def test_gateway_client_sends_claim_without_credentials_and_reconstructs_resolution() -> None:
    from core.official_gateway_client import OfficialGatewayClient

    seen: dict[str, object] = {}
    resolution = OfficialEvidenceResolution(
        concept=StandardConceptSchema(
            concept_id="C000008", canonical_name="취업자 수", standard_key="employment_count", status="MATCHED"
        ),
        candidates=[],
        catalog_diagnostics={"metadata_itm_succeeded": 1},
        verdict=VerdictSchema(
            claim_id="claim-1", verdict="UNDETERMINED", route_status="HOLD",
            reason_code="NO_EVIDENCE", explanation="Official evidence is unavailable.",
            dataset_version="test", semantic_standard_version="test", kosis_catalog_version="test",
            matching_version="test", calculation_version="test",
        ),
    )

    def transport(url: str, payload: dict[str, object], token: str) -> dict[str, object]:
        seen["url"] = url
        seen["payload"] = payload
        seen["token"] = token
        return {
            "concept": resolution.concept.model_dump(mode="json"),
            "candidates": [],
            "verdict": resolution.verdict.model_dump(mode="json"),
            "catalog_diagnostics": resolution.catalog_diagnostics,
        }

    client = OfficialGatewayClient("https://gateway.example/verify", gateway_token="shared-token", transport=transport)
    result = client.resolve(
        ClaimSchema(claim_id="claim-1", source_sentence="문장", indicator="취업자 수", parse_status="AUTO_OK"),
        article_date=date(2025, 1, 16),
    )

    assert seen["url"] == "https://gateway.example/verify"
    assert seen["token"] == "shared-token"
    assert seen["payload"] == {
        "claim": {"claim_id": "claim-1", "source_sentence": "문장", "indicator": "취업자 수", "value": None, "unit": None, "time": None, "frequency": None, "region": None, "population": None, "dimension": None, "comparison": None, "calculation": None, "condition": None, "source_hint": None, "parse_status": "AUTO_OK", "parse_reason": None},
        "article_date": "2025-01-16",
    }
    assert result.catalog_diagnostics == {"metadata_itm_succeeded": 1}
    assert result.verdict.claim_id == "claim-1"
