from datetime import date
import json

from core.admission_recovery_v3 import recover_registry_record_v3
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


class _Extractor:
    def __init__(self): self.inputs = []
    def extract(self, text: str, **kwargs):
        self.inputs.append(text)
        payload = json.loads(text)
        expression = payload["target_numeric_expression"]
        is_rate = expression == "83.5%"
        if "article_context" not in payload:
            return ClaimSchema(
                claim_id="first", source_sentence=text, indicator="\uace0\uc6a9\ub960",
                value=83.5 if is_rate else 1.1,
                unit="%" if is_rate else "%\ud3ec\uc778\ud2b8",
                calculation="DIRECT_VALUE" if is_rate else "DIFFERENCE",
                parse_status="HOLD", parse_reason="CLAIM_PARSE_UNCERTAIN",
            )
        return ClaimSchema(
            claim_id="second", source_sentence=text, indicator="\uace0\uc6a9\ub960",
            value=83.5 if is_rate else 1.1,
            unit="%" if is_rate else "%\ud3ec\uc778\ud2b8",
            time="2024\ub144 \ud558\ubc18\uae30", region="\uc6b8\ub989\uad70", frequency="\ubc18\uae30",
            calculation="DIRECT_VALUE" if is_rate else "DIFFERENCE",
            comparison=(None if is_rate else {
                "type": "YEAR_OVER_YEAR", "current_value": "83.5",
                "reference_value": "82.4", "operand_unit": "%",
            }),
            condition=None if is_rate else {"direction": "INCREASE"},
            parse_status="AUTO_OK",
        )


class _Official:
    def __init__(self): self.claims = []
    def resolve(self, claim, *, article_date): self.claims.append((claim, article_date)); return {"route": "AUTO"}


def test_multi_claim_context_is_a_second_pass_only_for_unresolved_targets() -> None:
    claim = ClaimSchema(
        claim_id="parent",
        source_sentence="\uc6b8\ub989\uad70 \uace0\uc6a9\ub960\uc740 83.5%\ub85c 1.1%\ud3ec\uc778\ud2b8 \uc0c1\uc2b9\ud588\ub2e4.",
        indicator="\uace0\uc6a9\ub960", value=83.5, unit="%", calculation="DIRECT_VALUE",
        parse_status="HOLD", parse_reason="MULTI_CLAIM_SPLIT_REQUIRED",
    )
    record = ClaimRegistryRecord(article_id="A1", sentence_id="1", claim=claim, article_published_at=date(2025, 2, 21), source_ref="test")
    extractor, official = _Extractor(), _Official()
    result = recover_registry_record_v3(
        record, extractor=extractor, official_service=official,
        article_context="\uae30\uc0ac \ubcf8\ubb38\uc5d0\uc11c \uc9c0\uc5ed\uc740 \uc6b8\ub989\uad70\uc774\ub2e4.",
    )
    assert len(result.entries) == 2
    assert len(extractor.inputs) == 4
    assert all(entry.admission_route == "KOSIS_PIPELINE_ELIGIBLE" for entry in result.entries)
    assert all(entry.record.slot_enrichment["article_context_used"] for entry in result.entries)
    assert len(official.claims) == 2
