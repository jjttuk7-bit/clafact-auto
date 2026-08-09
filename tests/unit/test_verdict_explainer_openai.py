import json
from unittest.mock import MagicMock, patch

from core.verdict_explainer import explain_verdict_with_openai
from schemas.verdict import VerdictSchema


def test_openai_explanation_uses_strict_function_call_and_keeps_fixed_conclusion() -> None:
    verdict = VerdictSchema(
        claim_id="claim-1",
        claim_value=-34.5,
        evidence_values=[136.62, 208.57],
        calculated_value=-34.4968,
        verdict="MATCH",
        route_status="AUTO",
        reason_code="WITHIN_TOLERANCE",
        explanation="deterministic result",
        dataset_version="test",
        semantic_standard_version="1.0",
        kosis_catalog_version="1.0",
        matching_version="1.0",
        calculation_version="1.0",
    )
    response_payload = {
        "output": [
            {
                "type": "function_call",
                "name": "emit_verdict_explanation",
                "arguments": json.dumps(
                    {
                        "summary": "공식 계산 결과와 기사 주장이 허용 오차 안에서 일치합니다.",
                        "detail": "계산된 결과가 검증 기준을 충족했습니다.",
                        "next_action": None,
                    }
                ),
            }
        ]
    }
    fake_response = MagicMock()
    fake_response.read.return_value = json.dumps(response_payload).encode()
    fake_response.__enter__.return_value = fake_response
    fake_response.__exit__.return_value = False

    with patch("core.verdict_explainer.urlopen", return_value=fake_response) as urlopen:
        result = explain_verdict_with_openai(
            verdict,
            api_key="test-key",
            model="test-model",
        )

    body = json.loads(urlopen.call_args.args[0].data.decode())
    assert body["tools"][0]["strict"] is True
    assert body["tools"][0]["parameters"]["additionalProperties"] is False
    assert result.source == "LLM"
    assert result.conclusion == "일치"
