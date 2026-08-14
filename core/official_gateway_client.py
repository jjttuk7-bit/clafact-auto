"""Client adapter for a remote direct-KOSIS official evidence Gateway."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from typing import Any
from urllib.request import Request, urlopen

from core.official_evidence_service import OfficialEvidenceResolution
from schemas.claim import ClaimSchema
from schemas.official_gateway import GatewayVerifyResponse

GatewayTransport = Callable[[str, dict[str, object], str], dict[str, object]]


class OfficialGatewayTransportError(RuntimeError):
    """Stable transport error that never includes a key or raw remote body."""


class OfficialGatewayClient:
    """Expose the remote Gateway through the same `resolve` contract as Core."""

    def __init__(
        self,
        verify_url: str,
        *,
        gateway_token: str,
        transport: GatewayTransport | None = None,
    ) -> None:
        self._verify_url = verify_url.rstrip("/")
        self._gateway_token = gateway_token.strip()
        if not self._gateway_token:
            raise ValueError("CLAFACT_GATEWAY_TOKEN is required")
        self._transport = transport or _post_json

    def resolve(self, claim: ClaimSchema, *, article_date: date) -> OfficialEvidenceResolution:
        payload: dict[str, object] = {
            "claim": claim.model_dump(mode="json"),
            "article_date": article_date.isoformat(),
        }
        try:
            response = GatewayVerifyResponse.model_validate(
                self._transport(self._verify_url, payload, self._gateway_token)
            )
        except Exception as error:
            if isinstance(error, OfficialGatewayTransportError):
                raise
            raise OfficialGatewayTransportError("KOSIS_GATEWAY_UNAVAILABLE") from error
        return OfficialEvidenceResolution(
            concept=response.concept,
            candidates=response.candidates,
            verdict=response.verdict,
            catalog_diagnostics=response.catalog_diagnostics,
        )


def _post_json(url: str, payload: dict[str, object], gateway_token: str) -> dict[str, object]:
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-CLAFACT-GATEWAY-TOKEN": gateway_token,
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=75) as response:
            body: Any = json.loads(response.read())
    except Exception as error:
        raise OfficialGatewayTransportError("KOSIS_GATEWAY_UNAVAILABLE") from error
    if not isinstance(body, dict):
        raise OfficialGatewayTransportError("KOSIS_GATEWAY_INVALID_RESPONSE")
    return body
