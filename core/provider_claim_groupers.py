"""Network adapters for provider-constrained numeric role grouping."""

from __future__ import annotations

import json
import socket
import uuid
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core.hcx_claim_grouper import (
    build_hcx_grouping_request,
    parse_hcx_grouping_content,
)
from core.openai_claim_grouper import (
    build_openai_grouping_request,
    parse_openai_grouping_response,
)
from schemas.claim_group import ClaimGroupingPlan, NumericMention


Transport = Callable[..., Any]


class OpenAIClaimGrouper:
    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        transport: Transport | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self._transport = transport or urlopen

    def group_claims(
        self,
        source_sentence: str,
        mentions: list[NumericMention],
    ) -> ClaimGroupingPlan:
        from core.openai_function_claim_extractor import (
            OPENAI_RESPONSES_URL,
            OPENAI_TIMEOUT_SECONDS,
            OpenAIConfigurationError,
            OpenAIContractError,
            OpenAITransientError,
            OpenAIFunctionClaimExtractor,
        )

        if not self.api_key:
            raise OpenAIConfigurationError("OPENAI_API_KEY_NOT_CONFIGURED")
        request = Request(
            OPENAI_RESPONSES_URL,
            data=json.dumps(
                build_openai_grouping_request(
                    source_sentence, mentions, self.model
                )
            ).encode(),
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
            OpenAIFunctionClaimExtractor._raise_http_error(error)
            raise AssertionError("unreachable")
        except (TimeoutError, socket.timeout, URLError, ConnectionError):
            raise OpenAITransientError("OPENAI_TRANSIENT_FAILURE") from None
        try:
            payload = json.loads(response_body)
        except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
            raise OpenAIContractError("INVALID_OPENAI_RESPONSE_JSON") from None
        return parse_openai_grouping_response(payload)


class HcxClaimGrouper:
    def __init__(
        self,
        *,
        api_key: str | None,
        model: str = "HCX-007",
        transport: Transport | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self._transport = transport or urlopen

    def group_claims(
        self,
        source_sentence: str,
        mentions: list[NumericMention],
    ) -> ClaimGroupingPlan:
        if not self.api_key:
            raise RuntimeError("HCX_API_KEY is not configured")
        request = Request(
            f"https://clovastudio.stream.ntruss.com/v3/chat-completions/{self.model}",
            data=json.dumps(
                build_hcx_grouping_request(source_sentence, mentions)
            ).encode(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "X-NCP-CLOVASTUDIO-REQUEST-ID": str(uuid.uuid4()),
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with self._transport(request, timeout=20) as response:
            payload = json.loads(response.read())
        return parse_hcx_grouping_content(
            payload["result"]["message"]["content"]
        )
