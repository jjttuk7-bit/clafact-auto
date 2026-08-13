from core.verdict_explainer import build_template_explanation
from schemas.verdict import VerdictSchema


def _verdict(verdict: str, route_status: str, reason_code: str) -> VerdictSchema:
    return VerdictSchema(
        claim_id="claim-1",
        claim_value=-34.5,
        evidence_values=[136.62, 208.57],
        calculated_value=-34.4968,
        verdict=verdict,
        route_status=route_status,
        reason_code=reason_code,
        explanation="deterministic result",
        dataset_version="test",
        semantic_standard_version="1.0",
        kosis_catalog_version="1.0",
        matching_version="1.0",
        calculation_version="1.0",
    )


def test_template_explanation_describes_match_without_changing_verdict() -> None:
    result = build_template_explanation(_verdict("MATCH", "AUTO", "WITHIN_TOLERANCE"))

    assert result.source == "TEMPLATE"
    assert result.conclusion == "일치"
    assert "KOSIS" in result.summary


def test_template_explanation_describes_undetermined_next_action() -> None:
    result = build_template_explanation(_verdict("UNDETERMINED", "HOLD", "VALUE_UNAVAILABLE"))

    assert result.source == "TEMPLATE"
    assert result.conclusion == "판정 불가"
    assert result.next_action is not None


def test_publication_transport_failure_explains_external_lookup_retry() -> None:
    result = build_template_explanation(_verdict("UNDETERMINED", "HOLD", "PUBLICATION_FETCH_FAILED"))
    assert "공표정보 조회" in result.detail
    assert "다시 시도" in (result.next_action or "")
