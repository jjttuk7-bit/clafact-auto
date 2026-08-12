"""OpenAI Responses API adapter for one strict emit_claim function call."""

from __future__ import annotations

import json
import os
import socket
from datetime import date
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import ValidationError

from core.claim_output_contract import EMIT_CLAIM_FUNCTION_NAME
from core.openai_claim_contract import (
    OpenAIClaimToolPayload,
    openai_emit_claim_tool_definition,
)
from schemas.claim import ClaimSchema


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
OPENAI_TIMEOUT_SECONDS = 20

OPENAI_CLAIM_INSTRUCTIONS = (
    "Extract exactly one Korean numerical news claim. Call emit_claim exactly once; "
    "never fetch or invent KOSIS values. Fill these 12 semantic slots only when stated "
    "or directly inferable: indicator, value, unit, time, frequency, region, population, "
    "dimension, comparison, calculation, condition, source_hint. "
    "The time slot is the claim target time; put historical benchmarks in "
    "comparison.reference_period. Preserve relative target time when article_published_at "
    "is supplied; Python resolves it. Put item, age, sex, industry, product, and trade-partner "
    "qualifiers in dimension or population, not indicator. "
    "Set calculation to DIRECT_VALUE, GROWTH_RATE, DIFFERENCE, SHARE, PART_TO_WHOLE, MULTIPLE, RANK, or THRESHOLD. "
    "For GROWTH_RATE comparison.type must be YEAR_OVER_YEAR, MONTH_OVER_MONTH, or "
    "QUARTER_OVER_QUARTER; condition.direction must be INCREASE or DECREASE. Emit a single target; "
    "split or HOLD sentences containing multiple independently verifiable rates. "
    "For DIFFERENCE comparison.current_value and comparison.reference_value must be numeric; "
    "set comparison.operand_unit and make value their absolute difference. "
    "For THRESHOLD set condition.operator to GT, GTE, LT, or LTE; set numeric "
    "condition.threshold_value and matching condition.threshold_unit. "
    "For RANK set condition.rank_value, condition.order as DESC or ASC, and "
    "condition.population_scope; require exactly one ranked item. "
    "Use AUTO_OK only for one clear factual claim with sufficient slots; otherwise use HOLD or HUMAN_REVIEW."
)
Transport = Callable[..., Any]
_OPENAI_API_KEY_OMITTED = object()


class OpenAIClaimExtractorError(RuntimeError):
    """Base error for OpenAI claim extraction failures."""


class OpenAIConfigurationError(OpenAIClaimExtractorError):
    """Raised when required OpenAI configuration is absent."""


class OpenAIAuthenticationError(OpenAIClaimExtractorError):
    """Raised when OpenAI rejects the configured credentials."""


class OpenAITransientError(OpenAIClaimExtractorError):
    """Raised for retryable OpenAI or network failures."""


class OpenAIContractError(OpenAIClaimExtractorError):
    """Raised when a provider response violates the strict claim contract."""


def build_openai_claim_request(
    sentence: str, model: str, *, article_published_at: date | None = None
) -> dict[str, object]:
    """Build a Responses API request exposing only the strict emit_claim tool."""
    claim_input = (
        json.dumps({"source_sentence": sentence, "article_published_at": article_published_at.isoformat()}, ensure_ascii=False)
        if article_published_at is not None
        else sentence
    )
    return {
        "model": model,
        "instructions": OPENAI_CLAIM_INSTRUCTIONS,
        "input": claim_input,
        "tools": [openai_emit_claim_tool_definition()],
        "tool_choice": {
            "type": "function",
            "name": EMIT_CLAIM_FUNCTION_NAME,
        },
        "parallel_tool_calls": False,
    }


def parse_openai_emit_claim_response(payload: object) -> ClaimSchema:
    """Validate exactly one emit_claim output item and its JSON arguments."""
    if not isinstance(payload, dict):
        raise OpenAIContractError("ONE_EMIT_CLAIM_CALL_REQUIRED")

    output = payload.get("output")
    if not isinstance(output, list):
        raise OpenAIContractError("ONE_EMIT_CLAIM_CALL_REQUIRED")

    function_calls = [
        item
        for item in output
        if isinstance(item, dict) and item.get("type") == "function_call"
    ]
    if len(function_calls) != 1:
        raise OpenAIContractError("ONE_EMIT_CLAIM_CALL_REQUIRED")

    function_call = function_calls[0]
    if function_call.get("name") != EMIT_CLAIM_FUNCTION_NAME:
        raise OpenAIContractError("ONE_EMIT_CLAIM_CALL_REQUIRED")

    arguments_json = function_call.get("arguments")
    if not isinstance(arguments_json, str):
        raise OpenAIContractError("EMIT_CLAIM_ARGUMENTS_JSON_REQUIRED")

    try:
        arguments = json.loads(arguments_json)
        return OpenAIClaimToolPayload.model_validate(arguments).to_claim()
    except (json.JSONDecodeError, ValidationError, ValueError, TypeError):
        raise OpenAIContractError("INVALID_EMIT_CLAIM_ARGUMENTS") from None


class OpenAIFunctionClaimExtractor:
    """Extract one ClaimSchema through the OpenAI Responses API."""

    def __init__(
        self,
        api_key: str | None | object = _OPENAI_API_KEY_OMITTED,
        model: str = "gpt-5.6-luna",
        transport: Transport | None = None,
    ) -> None:
        if api_key is _OPENAI_API_KEY_OMITTED:
            self.api_key: str | None = os.getenv("OPENAI_API_KEY") or _dotenv_value("OPENAI_API_KEY")
        else:
            assert api_key is None or isinstance(api_key, str)
            self.api_key = api_key
        self.model = model
        self._transport = transport or urlopen

    def extract(self, sentence: str, *, article_published_at: date | None = None) -> ClaimSchema:
        if not self.api_key:
            raise OpenAIConfigurationError("OPENAI_API_KEY_NOT_CONFIGURED")

        request = Request(
            OPENAI_RESPONSES_URL,
            data=json.dumps(build_openai_claim_request(sentence, self.model, article_published_at=article_published_at)).encode(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with self._transport(request, timeout=OPENAI_TIMEOUT_SECONDS) as response:
                response_body = response.read()
        except HTTPError as error:
            self._raise_http_error(error)
        except (TimeoutError, socket.timeout, URLError, ConnectionError):
            raise OpenAITransientError("OPENAI_TRANSIENT_FAILURE") from None

        try:
            payload = json.loads(response_body)
        except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
            raise OpenAIContractError("INVALID_OPENAI_RESPONSE_JSON") from None
        return parse_openai_emit_claim_response(payload)

    @staticmethod
    def _raise_http_error(error: HTTPError) -> None:
        if error.code in {401, 403}:
            raise OpenAIAuthenticationError("OPENAI_AUTHENTICATION_FAILED") from None
        if error.code in {408, 409, 429} or error.code >= 500:
            raise OpenAITransientError("OPENAI_TRANSIENT_FAILURE") from None
        if 400 <= error.code < 500:
            raise OpenAIClaimExtractorError("OPENAI_REQUEST_REJECTED") from None
        raise OpenAIClaimExtractorError("OPENAI_HTTP_FAILURE") from None


def _dotenv_value(name: str) -> str | None:
    """Read one unquoted key from a local .env file without exposing its value."""
    try:
        lines = Path(".env").read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return None

    for line in lines:
        if line.startswith(name + "="):
            return line.split("=", 1)[1].strip() or None
    return None
