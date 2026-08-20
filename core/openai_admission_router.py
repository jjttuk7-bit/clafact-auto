"""Strict OpenAI Structured Output adapter for Claim Admission only."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Callable
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, ValidationError

from core.openai_function_claim_extractor import (
    OPENAI_RESPONSES_URL,
    OPENAI_TIMEOUT_SECONDS,
    OpenAIAuthenticationError,
    OpenAIClaimExtractorError,
    OpenAIConfigurationError,
    OpenAIContractError,
    OpenAITransientError,
    _OPENAI_API_KEY_OMITTED,
    _dotenv_value,
)
from schemas.claim import ClaimSchema
from schemas.claim_admission import AdmissionDecision, AdmissionLabel


ADMISSION_FUNCTION_NAME = "route_claim_admission"
_INSTRUCTIONS = (
    "Classify one Korean numerical news sentence before KOSIS verification. "
    "Return exactly one label: KOSIS_PIPELINE_ELIGIBLE only for one present factual "
    "statistics claim suitable for 12-slot KOSIS processing; CONTEXT_REQUIRED when "
    "title/article context is necessary; MULTI_CLAIM_SPLIT_REQUIRED for multiple "
    "independent claims; NON_KOSIS_OR_PRIVATE for foreign, company, private, or "
    "non-KOSIS statistics; FORECAST_OPINION_UNVERIFIABLE for forecast/evaluation; "
    "NOT_A_VERIFIABLE_CLAIM for policy, definition, or non-factual numeric prose. "
    "Use MULTI_CLAIM_SPLIT_REQUIRED only for independent verifiable assertions; do not split a simple comparison baseline from its metric. "
    "Never fetch, infer, or create KOSIS values, dates, evidence, or verdicts."
)


class _AdmissionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    label: AdmissionLabel
    reason_code: str

    def decision(self) -> AdmissionDecision:
        return AdmissionDecision(label=self.label, reason_code=self.reason_code)


def build_openai_admission_request(
    claim: ClaimSchema, model: str, *, article_context: str | None = None
) -> dict[str, object]:
    """Build a narrow request containing source text and already-extracted slots only."""
    return {
        "model": model,
        "instructions": _INSTRUCTIONS,
        "input": json.dumps({
            "source_sentence": claim.source_sentence,
            "slots": claim.model_dump(exclude={"claim_id", "source_sentence"}, mode="json"),
            "article_context": article_context,
        }, ensure_ascii=False),
        "tools": [_tool_definition()],
        "tool_choice": {"type": "function", "name": ADMISSION_FUNCTION_NAME},
        "parallel_tool_calls": False,
    }


def parse_openai_admission_response(payload: object) -> AdmissionDecision:
    if not isinstance(payload, dict) or not isinstance(payload.get("output"), list):
        raise OpenAIContractError("ONE_ADMISSION_CALL_REQUIRED")
    calls = [item for item in payload["output"] if isinstance(item, dict) and item.get("type") == "function_call"]
    if len(calls) != 1 or calls[0].get("name") != ADMISSION_FUNCTION_NAME:
        raise OpenAIContractError("ONE_ADMISSION_CALL_REQUIRED")
    arguments = calls[0].get("arguments")
    if not isinstance(arguments, str):
        raise OpenAIContractError("ADMISSION_ARGUMENTS_JSON_REQUIRED")
    try:
        return _AdmissionPayload.model_validate(json.loads(arguments)).decision()
    except (json.JSONDecodeError, ValidationError, TypeError, ValueError):
        raise OpenAIContractError("INVALID_ADMISSION_ARGUMENTS") from None


class OpenAIAdmissionRouter:
    """Use OpenAI only for the admission label; official verification remains local."""

    def __init__(self, api_key: str | None | object = _OPENAI_API_KEY_OMITTED, model: str = "gpt-5.6-luna", transport: Callable[..., Any] | None = None) -> None:
        self.api_key = (_dotenv_value("OPENAI_API_KEY") if api_key is _OPENAI_API_KEY_OMITTED else api_key)
        self.model = model
        self._transport = transport or urlopen

    def route(self, claim: ClaimSchema, *, article_context: str | None = None) -> AdmissionDecision:
        if not self.api_key:
            raise OpenAIConfigurationError("OPENAI_API_KEY_NOT_CONFIGURED")
        request = Request(
            OPENAI_RESPONSES_URL,
            data=json.dumps(build_openai_admission_request(claim, self.model, article_context=article_context)).encode(),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self._transport(request, timeout=OPENAI_TIMEOUT_SECONDS) as response:
                body = response.read()
        except Exception as error:
            raise _translate_error(error) from None
        try:
            decision = parse_openai_admission_response(json.loads(body))
            if decision.label == "KOSIS_PIPELINE_ELIGIBLE" and not _has_required_kosis_slots(claim):
                return AdmissionDecision(
                    label="CONTEXT_REQUIRED", reason_code="MISSING_SLOT_CONTEXT"
                )
            return decision
        except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
            raise OpenAIContractError("INVALID_OPENAI_RESPONSE_JSON") from None


def _tool_definition() -> dict[str, Any]:
    return {
        "type": "function", "name": ADMISSION_FUNCTION_NAME, "strict": True,
        "description": "Route one candidate to its pre-KOSIS admission label.",
        "parameters": {"type": "object", "properties": {
            "label": {"type": "string", "enum": list(AdmissionLabel.__args__)},
            "reason_code": {"type": "string"},
        }, "required": ["label", "reason_code"], "additionalProperties": False},
    }


def _translate_error(error: Exception) -> OpenAIClaimExtractorError:
    if isinstance(error, (TimeoutError, ConnectionError)):
        return OpenAITransientError("OPENAI_TRANSIENT_FAILURE")
    # Keep provider response bodies out of errors. HTTP classification is delegated to
    # the existing claim extractor in production retries; all other failures are safe.
    return OpenAIClaimExtractorError("OPENAI_ADMISSION_REQUEST_FAILED")


def _has_required_kosis_slots(claim: ClaimSchema) -> bool:
    return all((
        claim.parse_status == "AUTO_OK",
        claim.indicator,
        claim.value is not None,
        claim.unit,
        claim.time,
        claim.calculation,
    ))
