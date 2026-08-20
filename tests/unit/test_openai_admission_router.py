import json

from core.openai_admission_router import (
    ADMISSION_FUNCTION_NAME,
    OpenAIAdmissionRouter,
    build_openai_admission_request,
    parse_openai_admission_response,
)
from schemas.claim import ClaimSchema


def claim() -> ClaimSchema:
    return ClaimSchema(
        claim_id="C-1",
        source_sentence="지난달 제조업 취업자는 439만7000명이었다.",
        indicator="취업자 수",
        value=4_397_000,
        unit="명",
        time="2025-05",
        frequency="월",
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )


def test_request_forces_one_strict_admission_function_call() -> None:
    request = build_openai_admission_request(claim(), "gpt-test")

    assert request["model"] == "gpt-test"
    assert request["tool_choice"] == {"type": "function", "name": ADMISSION_FUNCTION_NAME}
    assert request["parallel_tool_calls"] is False
    assert json.loads(request["input"])["source_sentence"] == claim().source_sentence


def test_router_returns_only_a_pre_kosis_admission_decision() -> None:
    payload = {
        "output": [{
            "type": "function_call",
            "name": ADMISSION_FUNCTION_NAME,
            "arguments": json.dumps({
                "label": "MULTI_CLAIM_SPLIT_REQUIRED",
                "reason_code": "MULTIPLE_INDEPENDENT_STATISTICS",
            }),
        }],
    }

    decision = parse_openai_admission_response(payload)

    assert decision.label == "MULTI_CLAIM_SPLIT_REQUIRED"
    assert decision.reason_code == "MULTIPLE_INDEPENDENT_STATISTICS"

    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return None
        def read(self):
            return json.dumps(payload).encode()

    router = OpenAIAdmissionRouter(api_key="test", model="gpt-test", transport=lambda *_args, **_kwargs: Response())
    assert router.route(claim()).label == "MULTI_CLAIM_SPLIT_REQUIRED"


def test_router_demotes_model_eligible_output_when_required_slot_is_missing() -> None:
    payload = {
        "output": [{
            "type": "function_call",
            "name": ADMISSION_FUNCTION_NAME,
            "arguments": json.dumps({
                "label": "KOSIS_PIPELINE_ELIGIBLE",
                "reason_code": "SINGLE_STATISTICAL_CLAIM",
            }),
        }],
    }

    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return None
        def read(self):
            return json.dumps(payload).encode()

    incomplete = claim().model_copy(update={"time": None})
    router = OpenAIAdmissionRouter(api_key="test", transport=lambda *_args, **_kwargs: Response())

    decision = router.route(incomplete)

    assert decision.label == "CONTEXT_REQUIRED"
    assert decision.reason_code == "MISSING_SLOT_CONTEXT"
