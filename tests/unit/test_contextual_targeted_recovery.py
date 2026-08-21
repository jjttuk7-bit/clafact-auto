from datetime import date

from core.admission_recovery_v3 import recover_registry_record_v3
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


class _Extractor:
    def __init__(self): self.inputs = []
    def extract(self, text: str, **kwargs):
        self.inputs.append(text)
        if "article_context" not in text:
            return ClaimSchema(claim_id="first", source_sentence=text, indicator="고용률", value=83.5, unit="%", calculation="DIRECT_VALUE", parse_status="HOLD", parse_reason="CLAIM_PARSE_UNCERTAIN")
        return ClaimSchema(claim_id="second", source_sentence=text, indicator="고용률", value=83.5, unit="%", time="2024년 하반기", region="울릉군", frequency="반기", calculation="DIRECT_VALUE", parse_status="AUTO_OK")


class _Official:
    def __init__(self): self.claims = []
    def resolve(self, claim, *, article_date): self.claims.append((claim, article_date)); return {"route": "AUTO"}


def test_multi_claim_context_is_a_second_pass_only_for_unresolved_targets() -> None:
    claim = ClaimSchema(claim_id="parent", source_sentence="울릉군 고용률은 83.5%로 1.1%포인트 상승했다.", indicator="고용률", value=83.5, unit="%", calculation="DIRECT_VALUE", parse_status="HOLD", parse_reason="MULTI_CLAIM_SPLIT_REQUIRED")
    record = ClaimRegistryRecord(article_id="A1", sentence_id="1", claim=claim, article_published_at=date(2025, 2, 21), source_ref="test")
    extractor, official = _Extractor(), _Official()
    result = recover_registry_record_v3(record, extractor=extractor, official_service=official, article_context="기사 본문에서 지역은 울릉군이다.")
    assert len(result.entries) == 2
    assert len(extractor.inputs) == 4
    assert all(entry.admission_route == "KOSIS_PIPELINE_ELIGIBLE" for entry in result.entries)
    assert all(entry.record.slot_enrichment["article_context_used"] for entry in result.entries)
    assert len(official.claims) == 2
