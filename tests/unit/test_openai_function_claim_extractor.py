from __future__ import annotations

import copy
import json
import socket
import traceback
from datetime import date
from io import BytesIO
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from core.openai_claim_contract import openai_emit_claim_tool_definition
from core.openai_function_claim_extractor import (
    OpenAIAuthenticationError,
    OpenAIClaimExtractorError,
    OpenAIConfigurationError,
    OpenAIContractError,
    OpenAIFunctionClaimExtractor,
    OpenAITransientError,
    build_openai_claim_request,
    parse_openai_emit_claim_response,
)


def _arguments(**overrides: Any) -> dict[str, Any]:
    arguments: dict[str, Any] = {
        "claim_id": "claim-1",
        "source_sentence": "2025년 전국 고용률은 70%였다.",
        "indicator": "고용률",
        "value": 70.0,
        "unit": "%",
        "time": "2025년",
        "frequency": "년",
        "region": "전국",
        "population": None,
        "dimension": [],
        "comparison": [],
        "calculation": "DIRECT_VALUE",
        "condition": [],
        "source_hint": None,
        "parse_status": "AUTO_OK",
        "parse_reason": None,
    }
    arguments.update(overrides)
    return arguments


def _response(arguments: object | None = None) -> dict[str, Any]:
    encoded_arguments = json.dumps(
        _arguments() if arguments is None else arguments,
        ensure_ascii=False,
    )
    return {
        "id": "resp-1",
        "output": [
            {
                "type": "function_call",
                "name": "emit_claim",
                "arguments": encoded_arguments,
            }
        ],
    }


class _Response:
    def __init__(self, payload: object) -> None:
        self._body = json.dumps(payload, ensure_ascii=False).encode()

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def test_build_request_forces_one_emit_claim_call_for_requested_model() -> None:
    request = build_openai_claim_request(
        "2025년 전국 고용률은 70%였다.",
        "gpt-5.6-luna",
    )

    assert request["model"] == "gpt-5.6-luna"
    assert request["tool_choice"] == {"type": "function", "name": "emit_claim"}
    assert request["parallel_tool_calls"] is False
    assert request["tools"] == [openai_emit_claim_tool_definition()]


def test_build_request_contains_only_concise_instructions_and_sentence_input() -> None:
    sentence = "2025년 전국 고용률은 70%였다."
    request = build_openai_claim_request(sentence, "gpt-5.6-luna")

    assert request["input"] == sentence
    assert isinstance(request["instructions"], str)
    assert 0 < len(request["instructions"]) < 1_600
    for required_term in (
        "indicator", "value", "unit", "time", "frequency", "region",
        "population", "dimension", "comparison", "calculation", "condition",
        "source_hint", "DIRECT_VALUE", "GROWTH_RATE", "PART_TO_WHOLE",
    ):
        assert required_term in request["instructions"]
    assert set(request) == {
        "model",
        "instructions",
        "input",
        "tools",
        "tool_choice",
        "parallel_tool_calls",
    }
    assert [tool["name"] for tool in request["tools"]] == ["emit_claim"]


def test_build_request_includes_article_date_as_claim_parsing_context() -> None:
    sentence = "지난달 가공식품 물가는 전년 대비 3.1% 올랐다."
    request = build_openai_claim_request(sentence, "gpt-5.6-luna", article_published_at=date(2025, 4, 5))
    assert json.loads(request["input"]) == {"source_sentence": sentence, "article_published_at": "2025-04-05"}
    assert "target time" in request["instructions"]
    assert "comparison.reference_period" in request["instructions"]


def test_parse_accepts_one_emit_claim_function_call_with_json_arguments() -> None:
    claim = parse_openai_emit_claim_response(_response())

    assert claim.indicator == "고용률"
    assert claim.dimension is None
    assert claim.parse_status == "AUTO_OK"


def test_parse_ignores_reasoning_item_when_one_emit_claim_call_exists() -> None:
    payload = _response()
    payload["output"].insert(
        0,
        {"type": "reasoning", "id": "reasoning-1", "summary": []},
    )

    claim = parse_openai_emit_claim_response(payload)

    assert claim.indicator == "고용률"


def test_parse_rejects_reasoning_item_without_function_call() -> None:
    payload = {
        "output": [{"type": "reasoning", "id": "reasoning-1", "summary": []}]
    }

    with pytest.raises(OpenAIContractError, match="ONE_EMIT_CLAIM_CALL_REQUIRED"):
        parse_openai_emit_claim_response(payload)


def test_parse_rejects_reasoning_item_with_multiple_function_calls() -> None:
    payload = _response()
    payload["output"].insert(
        0,
        {"type": "reasoning", "id": "reasoning-1", "summary": []},
    )
    payload["output"].append(copy.deepcopy(payload["output"][1]))

    with pytest.raises(OpenAIContractError, match="ONE_EMIT_CLAIM_CALL_REQUIRED"):
        parse_openai_emit_claim_response(payload)



def test_parse_accepts_valid_hold_payload() -> None:
    claim = parse_openai_emit_claim_response(
        _response(
            _arguments(
                indicator=None,
                value=None,
                unit=None,
                time=None,
                frequency=None,
                region=None,
                calculation=None,
                parse_status="HOLD",
                parse_reason="필수 시점이 불명확함",
            )
        )
    )

    assert claim.parse_status == "HOLD"
    assert claim.parse_reason == "필수 시점이 불명확함"


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (lambda payload: payload.update(output=[]), "ONE_EMIT_CLAIM_CALL_REQUIRED"),
        (
            lambda payload: payload["output"].append(copy.deepcopy(payload["output"][0])),
            "ONE_EMIT_CLAIM_CALL_REQUIRED",
        ),
        (
            lambda payload: payload["output"][0].update(type="message"),
            "ONE_EMIT_CLAIM_CALL_REQUIRED",
        ),
        (
            lambda payload: payload["output"][0].update(name="fetch_kosis"),
            "ONE_EMIT_CLAIM_CALL_REQUIRED",
        ),
        (
            lambda payload: payload["output"][0].update(arguments={}),
            "EMIT_CLAIM_ARGUMENTS_JSON_REQUIRED",
        ),
        (
            lambda payload: payload["output"][0].update(arguments="{not-json"),
            "INVALID_EMIT_CLAIM_ARGUMENTS",
        ),
        (
            lambda payload: payload["output"][0].update(arguments=json.dumps({})),
            "INVALID_EMIT_CLAIM_ARGUMENTS",
        ),
    ],
)
def test_parse_rejects_invalid_provider_contract(mutate, reason: str) -> None:
    payload = _response()
    mutate(payload)

    with pytest.raises(OpenAIContractError, match=reason):
        parse_openai_emit_claim_response(payload)


def test_missing_api_key_raises_configuration_error(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(OpenAIConfigurationError, match="OPENAI_API_KEY_NOT_CONFIGURED"):
        OpenAIFunctionClaimExtractor().extract("문장")


def test_extractor_loads_api_key_from_dotenv(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    (tmp_path / ".env").write_text("OPENAI_API_KEY=dotenv-secret\n", encoding="utf-8")

    extractor = OpenAIFunctionClaimExtractor(transport=lambda *_args, **_kwargs: _Response(_response()))

    assert extractor.extract("문장").parse_status == "AUTO_OK"


@pytest.mark.parametrize("explicit_api_key", [None, ""])
def test_explicit_missing_api_key_does_not_load_ambient_credentials(
    monkeypatch, tmp_path, explicit_api_key: str | None,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "ambient-secret")
    (tmp_path / ".env").write_text("OPENAI_API_KEY=dotenv-secret\n", encoding="utf-8")

    extractor = OpenAIFunctionClaimExtractor(api_key=explicit_api_key)

    assert extractor.api_key == explicit_api_key
    with pytest.raises(OpenAIConfigurationError, match="OPENAI_API_KEY_NOT_CONFIGURED"):
        extractor.extract("문장")


def test_extractor_posts_json_with_bearer_auth_and_twenty_second_timeout() -> None:
    captured: dict[str, object] = {}

    def transport(request: Request, timeout: float) -> _Response:
        captured.update(request=request, timeout=timeout)
        return _Response(_response())

    claim = OpenAIFunctionClaimExtractor(
        api_key="test-secret",
        model="gpt-5.6-luna",
        transport=transport,
    ).extract("2025년 전국 고용률은 70%였다.")

    request = captured["request"]
    assert isinstance(request, Request)
    assert request.full_url == "https://api.openai.com/v1/responses"
    assert request.method == "POST"
    assert request.get_header("Authorization") == "Bearer test-secret"
    assert request.get_header("Content-type") == "application/json"
    assert json.loads(request.data)["model"] == "gpt-5.6-luna"
    assert captured["timeout"] == 20
    assert claim.indicator == "고용률"


@pytest.mark.parametrize("status", [401, 403])
def test_authentication_http_errors_are_typed(status: int) -> None:
    error = HTTPError(
        "https://api.openai.com/v1/responses",
        status,
        "provider-secret-payload",
        None,
        BytesIO(b'{"error":"provider-secret-payload"}'),
    )

    with pytest.raises(OpenAIAuthenticationError, match="OPENAI_AUTHENTICATION_FAILED"):
        OpenAIFunctionClaimExtractor(
            api_key="test-secret",
            transport=lambda *_args, **_kwargs: (_ for _ in ()).throw(error),
        ).extract("문장")


@pytest.mark.parametrize("status", [408, 409, 429, 500, 503])
def test_retryable_http_errors_are_transient(status: int) -> None:
    error = HTTPError(
        "https://api.openai.com/v1/responses",
        status,
        "provider-secret-payload",
        None,
        BytesIO(b'{"error":"provider-secret-payload"}'),
    )

    with pytest.raises(OpenAITransientError, match="OPENAI_TRANSIENT_FAILURE"):
        OpenAIFunctionClaimExtractor(
            api_key="test-secret",
            transport=lambda *_args, **_kwargs: (_ for _ in ()).throw(error),
        ).extract("문장")


@pytest.mark.parametrize(
    "error",
    [TimeoutError("provider-secret-payload"), socket.timeout("provider-secret-payload"), URLError("offline")],
)
def test_timeout_and_transport_errors_are_transient(error: Exception) -> None:
    with pytest.raises(OpenAITransientError, match="OPENAI_TRANSIENT_FAILURE"):
        OpenAIFunctionClaimExtractor(
            api_key="test-secret",
            transport=lambda *_args, **_kwargs: (_ for _ in ()).throw(error),
        ).extract("문장")


def test_other_http_4xx_is_non_transient() -> None:
    error = HTTPError(
        "https://api.openai.com/v1/responses",
        400,
        "provider-secret-payload",
        None,
        BytesIO(b'{"error":"provider-secret-payload"}'),
    )

    with pytest.raises(OpenAIClaimExtractorError, match="OPENAI_REQUEST_REJECTED") as caught:
        OpenAIFunctionClaimExtractor(
            api_key="test-secret",
            transport=lambda *_args, **_kwargs: (_ for _ in ()).throw(error),
        ).extract("문장")

    assert not isinstance(caught.value, OpenAITransientError)


@pytest.mark.parametrize(
    "failure",
    [
        HTTPError(
            "https://api.openai.com/v1/responses",
            401,
            "provider-secret-payload",
            None,
            BytesIO(b'{"error":"provider-secret-payload"}'),
        ),
        HTTPError(
            "https://api.openai.com/v1/responses",
            500,
            "provider-secret-payload",
            None,
            BytesIO(b'{"error":"provider-secret-payload"}'),
        ),
        TimeoutError("provider-secret-payload"),
    ],
)
def test_transport_error_messages_do_not_expose_secrets_or_provider_payload(failure: Exception) -> None:
    with pytest.raises(OpenAIClaimExtractorError) as caught:
        OpenAIFunctionClaimExtractor(
            api_key="test-secret",
            transport=lambda *_args, **_kwargs: (_ for _ in ()).throw(failure),
        ).extract("문장")

    message = str(caught.value)
    assert "test-secret" not in message
    assert "provider-secret-payload" not in message


@pytest.mark.parametrize(
    "failure",
    [
        HTTPError(
            "https://api.openai.com/v1/responses",
            401,
            "provider-secret-sentinel",
            None,
            BytesIO(b'{"error":"provider-secret-sentinel"}'),
        ),
        URLError("provider-secret-sentinel"),
        TimeoutError("provider-secret-sentinel"),
    ],
)
def test_transport_exceptions_do_not_chain_or_render_provider_details(failure: Exception) -> None:
    with pytest.raises(OpenAIClaimExtractorError) as caught:
        OpenAIFunctionClaimExtractor(
            api_key="test-secret",
            transport=lambda *_args, **_kwargs: (_ for _ in ()).throw(failure),
        ).extract("문장")

    rendered = "".join(traceback.format_exception(caught.type, caught.value, caught.tb))
    assert caught.value.__cause__ is None
    assert "provider-secret-sentinel" not in rendered


def test_malformed_response_json_does_not_chain_or_render_provider_details() -> None:
    class MalformedResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"provider":"provider-secret-sentinel"'

    with pytest.raises(OpenAIContractError) as caught:
        OpenAIFunctionClaimExtractor(
            api_key="test-secret",
            transport=lambda *_args, **_kwargs: MalformedResponse(),
        ).extract("문장")

    rendered = "".join(traceback.format_exception(caught.type, caught.value, caught.tb))
    assert caught.value.__cause__ is None
    assert "provider-secret-sentinel" not in rendered


def test_malformed_function_arguments_do_not_chain_provider_validation_details() -> None:
    payload = _response()
    payload["output"][0]["arguments"] = '{"private":"provider-secret-sentinel"}'

    with pytest.raises(OpenAIContractError) as caught:
        parse_openai_emit_claim_response(payload)

    rendered = "".join(traceback.format_exception(caught.type, caught.value, caught.tb))
    assert caught.value.__cause__ is None
    assert "provider-secret-sentinel" not in rendered



def test_contract_error_does_not_expose_full_provider_payload() -> None:
    provider_payload = {"output": [{"type": "message", "content": "private provider body"}]}

    with pytest.raises(OpenAIContractError) as caught:
        parse_openai_emit_claim_response(provider_payload)

    assert "private provider body" not in str(caught.value)


def test_build_request_defines_complete_threshold_condition_contract() -> None:
    instructions = build_openai_claim_request(
        "지난해 화장품 수출액은 100억달러 이상이었다.",
        "gpt-5.6-luna",
    )["instructions"]

    assert "condition.operator" in instructions
    assert "condition.threshold_value" in instructions
    assert "condition.threshold_unit" in instructions
    assert "GT, GTE, LT, or LTE" in instructions


def test_build_request_defines_complete_rank_condition_contract() -> None:
    instructions = build_openai_claim_request(
        "지난해 대미 자동차 수출액은 품목 중 1위였다.",
        "gpt-5.6-luna",
    )["instructions"]

    assert "condition.rank_value" in instructions
    assert "condition.order" in instructions
    assert "condition.population_scope" in instructions
    assert "DESC or ASC" in instructions

def test_build_request_defines_complete_growth_rate_contract() -> None:
    instructions = build_openai_claim_request(
        "올해 1분기 수출액은 전년 동기보다 6.5% 증가했다.",
        "gpt-5.6-luna",
    )["instructions"]

    assert "GROWTH_RATE comparison.type" in instructions
    assert "YEAR_OVER_YEAR, MONTH_OVER_MONTH, or QUARTER_OVER_QUARTER" in instructions
    assert "condition.direction" in instructions
    assert "INCREASE or DECREASE" in instructions
    assert "single target" in instructions

def test_build_request_defines_complete_difference_contract() -> None:
    instructions = build_openai_claim_request(
        "수출 비중은 19.8%로 전년보다 0.6%포인트 줄었다.",
        "gpt-5.6-luna",
    )["instructions"]

    assert "DIFFERENCE comparison.current_value" in instructions
    assert "comparison.reference_value" in instructions
    assert "comparison.operand_unit" in instructions
    assert "absolute difference" in instructions