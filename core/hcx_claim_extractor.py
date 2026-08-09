"""HCX structured JSON claim extraction."""

import json
import os
import re
import uuid
from urllib.request import Request, urlopen

from schemas.claim import ClaimSchema


SYSTEM_PROMPT = (
    "You extract one Korean numerical news claim. Return JSON strictly matching the provided schema. "
    "For a single clear historical level, set calculation DIRECT_VALUE. "
    "For an explicit year-on-year or same-month-last-year percentage change, set calculation GROWTH_RATE. "
    "For a sentence containing 복수 independent indicator/value claims, set parse_status HUMAN_REVIEW; do not choose one. "
    "Use HUMAN_REVIEW only for forecast, ambiguity, or genuinely missing essential context. "
    "Populate indicator, value, unit, time, frequency, and region when stated."
)


class HcxClaimExtractor:
    def __init__(self, api_key: str | None = None, model: str = "HCX-007") -> None:
        self.api_key = api_key or os.getenv("HCX_API_KEY") or _dotenv_value("HCX_API_KEY")
        self.model = model

    def extract(self, sentence: str) -> ClaimSchema:
        if not self.api_key:
            raise RuntimeError("HCX_API_KEY is not configured")

        body = {
            "messages": [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {"role": "user", "content": sentence},
            ],
            "temperature": 0,
            "maxCompletionTokens": 1024,
            "thinking": {"effort": "none"},
            "responseFormat": {
                "type": "json",
                "schema": {
                    "type": "object",
                    "properties": {
                        "claim_id": {"type": "string"},
                        "source_sentence": {"type": "string"},
                        "indicator": {"type": "string"},
                        "value": {"type": "number"},
                        "unit": {"type": "string"},
                        "time": {"type": "string"},
                        "frequency": {"type": "string"},
                        "region": {"type": "string"},
                        "population": {"type": "string"},
                        "calculation": {"type": "string"},
                        "source_hint": {"type": "string"},
                        "parse_status": {"type": "string", "enum": ["AUTO_OK", "HOLD", "HUMAN_REVIEW"]},
                        "parse_reason": {"type": "string"},
                    },
                    "required": ["claim_id", "source_sentence", "parse_status"],
                },
            },
        }
        request = Request(
            f"https://clovastudio.stream.ntruss.com/v3/chat-completions/{self.model}",
            data=json.dumps(body).encode(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "X-NCP-CLOVASTUDIO-REQUEST-ID": str(uuid.uuid4()),
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read())

        content = payload["result"]["message"]["content"].strip()
        content = content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        claim = ClaimSchema.model_validate_json(content)
        blank_fields = {
            key: None
            for key, value in claim.model_dump().items()
            if value == "" and key not in {"claim_id", "source_sentence", "parse_status"}
        }
        if claim.frequency and claim.frequency.casefold() not in {"monthly", "month", "yearly", "year", "annual", "월", "년", "분기"}:
            blank_fields["frequency"] = None
        normalized_frequency = _frequency_from_time(claim.time)
        if (claim.frequency is None or "frequency" in blank_fields) and normalized_frequency:
            blank_fields["frequency"] = normalized_frequency
        return claim.model_copy(update=blank_fields)


def _dotenv_value(name: str) -> str | None:
    try:
        for line in open(".env", encoding="utf-8"):
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip() or None
    except FileNotFoundError:
        pass
    return None

def _frequency_from_time(value: str | None) -> str | None:
    """Derive only an explicit period frequency from the structured time slot."""
    if not value:
        return None
    if re.search(r"\d{4}\s*년\s*\d{1,2}\s*월", value):
        return "월"
    if re.search(r"\d{4}\s*년\s*\d\s*분기", value):
        return "분기"
    if re.search(r"\d{4}\s*년", value):
        return "년"
    return None
