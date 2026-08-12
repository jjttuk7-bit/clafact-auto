"""Constrained HCX Function Calling adapter for emitting one Claim object."""

from __future__ import annotations

import json
import os
import uuid
from datetime import date
from typing import Any
from urllib.request import Request, urlopen

from core.claim_output_contract import (
    EMIT_CLAIM_FUNCTION_NAME,
    ClaimOutputPayload,
    emit_claim_tool_definition,
)
from core.hcx_claim_extractor import SYSTEM_PROMPT, _claim_input, _dotenv_value
from schemas.claim import ClaimSchema


FUNCTION_SYSTEM_PROMPT = SYSTEM_PROMPT.replace(
    "Return JSON strictly matching the provided schema. ",
    "Call emit_claim exactly once with arguments strictly matching its schema. ",
)


def build_function_claim_request(
    sentence: str, *, article_published_at: date | None = None
) -> dict[str, object]:
    """Build a Function Calling request that exposes only emit_claim."""
    return {
        "messages": [
            {"role": "system", "content": FUNCTION_SYSTEM_PROMPT},
            {"role": "user", "content": _claim_input(sentence, article_published_at)},
        ],
        "temperature": 0,
        "maxCompletionTokens": 1024,
        "tools": [emit_claim_tool_definition()],
        "toolChoice": {
            "type": "function",
            "function": {"name": EMIT_CLAIM_FUNCTION_NAME},
        },
    }


def parse_emit_claim_tool_call(payload: dict[str, Any]) -> ClaimSchema:
    """Validate one HCX emit_claim envelope without dispatching any function."""
    try:
        tool_calls = payload["result"]["message"]["toolCalls"]
    except (KeyError, TypeError) as error:
        raise ValueError("ONE_TOOL_CALL_REQUIRED") from error
    if not isinstance(tool_calls, list) or len(tool_calls) != 1:
        raise ValueError("ONE_TOOL_CALL_REQUIRED")

    tool_call = tool_calls[0]
    if not isinstance(tool_call, dict) or tool_call.get("type") != "function":
        raise ValueError("EMIT_CLAIM_TOOL_REQUIRED")
    function = tool_call.get("function")
    if not isinstance(function, dict) or function.get("name") != EMIT_CLAIM_FUNCTION_NAME:
        raise ValueError("EMIT_CLAIM_TOOL_REQUIRED")
    arguments = function.get("arguments")
    if not isinstance(arguments, dict):
        raise ValueError("EMIT_CLAIM_ARGUMENTS_OBJECT_REQUIRED")
    return ClaimOutputPayload.model_validate(arguments).to_claim()


class HcxFunctionClaimExtractor:
    """Optional HCX extractor using one forced emit_claim Function Call."""

    def __init__(self, api_key: str | None = None, model: str = "HCX-007") -> None:
        self.api_key = api_key or os.getenv("HCX_API_KEY") or _dotenv_value("HCX_API_KEY")
        self.model = model

    def extract(self, sentence: str, *, article_published_at: date | None = None) -> ClaimSchema:
        if not self.api_key:
            raise RuntimeError("HCX_API_KEY is not configured")

        request = Request(
            f"https://clovastudio.stream.ntruss.com/v3/chat-completions/{self.model}",
            data=json.dumps(build_function_claim_request(sentence, article_published_at=article_published_at)).encode(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "X-NCP-CLOVASTUDIO-REQUEST-ID": str(uuid.uuid4()),
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read())
        return parse_emit_claim_tool_call(payload)