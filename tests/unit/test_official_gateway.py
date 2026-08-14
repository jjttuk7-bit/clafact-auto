from datetime import date

import pytest
from pydantic import ValidationError

from schemas.claim import ClaimSchema


def test_gateway_request_accepts_structured_claim_and_article_date() -> None:
    from schemas.official_gateway import GatewayVerifyRequest

    request = GatewayVerifyRequest(
        claim=ClaimSchema(
            claim_id="claim-1",
            source_sentence="2024년 취업자 수는 2800만명이었다.",
            indicator="취업자 수",
            parse_status="AUTO_OK",
        ),
        article_date=date(2025, 1, 16),
    )

    assert request.article_date == date(2025, 1, 16)
    assert request.claim.claim_id == "claim-1"


def test_gateway_request_rejects_credentials() -> None:
    from schemas.official_gateway import GatewayVerifyRequest

    with pytest.raises(ValidationError):
        GatewayVerifyRequest.model_validate(
            {
                "claim": {"claim_id": "claim-1", "source_sentence": "문장", "parse_status": "AUTO_OK"},
                "article_date": "2025-01-16",
                "kosis_api_key": "must-not-be-accepted",
            }
        )


def test_gateway_module_exports_deployable_fastapi_app() -> None:
    from gateway.official_gateway_app import app

    assert app.title == "CLAFACT-AUTO Official KOSIS Gateway"