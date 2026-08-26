from __future__ import annotations

import json
from datetime import date

from core.admission_recovery_v3 import recover_registry_record_v3
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


SOURCE = (
    "\uc11d\uc720\ud654\ud559 \uc218\ucd9c\uc740 480\uc5b5 \ub2ec\ub7ec\ub85c "
    "\uc218\ucd9c\ubb3c\ub7c9\uc774 \ud655\ub300\ub418\uba74\uc11c 5% \uc99d\uac00\ud588\ub2e4."
)


class _ContextTimeExtractor:
    def __init__(self, *, missing_slot: str = "time") -> None:
        self.missing_slot = missing_slot
        self.calls: list[dict[str, object]] = []

    def extract(self, source_sentence: str, *, article_published_at=None) -> ClaimSchema:
        payload = json.loads(source_sentence)
        self.calls.append(payload)
        has_context = bool(payload.get("article_context"))
        missing_time = self.missing_slot in {"time", "indicator_time_freeform"} and not has_context
        missing_value = self.missing_slot == "value"
        return ClaimSchema(
            claim_id="temporary",
            source_sentence=source_sentence,
            indicator=None if self.missing_slot == "indicator_time_freeform" and not has_context else "export value",
            value=None if missing_value else 480.0,
            unit="USD 100m",
            time=None if missing_time else "2024",
            frequency="annual",
            calculation="DIRECT_VALUE",
            parse_status="HOLD" if missing_time or missing_value else "AUTO_OK",
            parse_reason=(
                ("문맥에 지표와 기준시점이 생략됨" if self.missing_slot == "indicator_time_freeform" else f"MISSING_REQUIRED_SLOTS:{self.missing_slot}")
                if missing_time or missing_value
                else "time recovered from article context"
            ),
        )


class _Service:
    def resolve(self, claim, *, article_date):
        return {"route_status": "AUTO"}


def _record(reason: str) -> ClaimRegistryRecord:
    return ClaimRegistryRecord(
        article_id="A1",
        sentence_id="2",
        article_published_at=date(2025, 1, 1),
        source_ref="registry",
        claim=ClaimSchema(
            claim_id="parent",
            source_sentence=SOURCE,
            parse_status="HOLD",
            parse_reason=reason,
        ),
    )


def test_v3_retries_missing_time_with_article_context_before_structural_hold() -> None:
    extractor = _ContextTimeExtractor()

    result = recover_registry_record_v3(
        _record("MISSING_REQUIRED_SLOTS:time"),
        extractor=extractor,
        official_service=_Service(),
        article_context="2024 annual export results\n" + SOURCE,
    )

    child = result.entries[0]
    assert len(extractor.calls) == 4
    assert extractor.calls[1]["target_already_split"] is True
    assert child.admission_route == "KOSIS_PIPELINE_ELIGIBLE"
    assert child.record.claim.time == "2024"
    assert child.record.slot_enrichment["article_context_used"] is True
    assert child.record.slot_enrichment["context_enriched_slots"] == ["time"]


def test_v3_does_not_retry_non_contextual_value_gap_with_article_context() -> None:
    extractor = _ContextTimeExtractor(missing_slot="value")

    result = recover_registry_record_v3(
        _record("MISSING_REQUIRED_SLOTS:value"),
        extractor=extractor,
        official_service=_Service(),
        article_context="2024 annual export results",
    )

    assert len(extractor.calls) == 2
    assert result.entries[0].admission_route == "STRUCTURAL_HOLD"
    assert result.entries[0].record.slot_enrichment["article_context_used"] is False

def test_v3_retries_target_fragment_with_value_and_unit_but_freeform_missing_context() -> None:
    extractor = _ContextTimeExtractor(missing_slot="indicator_time_freeform")

    result = recover_registry_record_v3(
        _record("MULTI_CLAIM_SPLIT_REQUIRED"),
        extractor=extractor,
        official_service=_Service(),
        article_context="2024 annual export results\n" + SOURCE,
    )

    child = result.entries[0]
    assert len(extractor.calls) == 4
    assert child.admission_route == "KOSIS_PIPELINE_ELIGIBLE"
    assert child.record.claim.indicator == "export value"
    assert child.record.claim.time == "2024"
    assert child.record.slot_enrichment["article_context_used"] is True

def test_v3_retries_single_numeric_fragment_with_freeform_missing_context() -> None:
    extractor = _ContextTimeExtractor(missing_slot="indicator_time_freeform")
    record = ClaimRegistryRecord(
        article_id="A2",
        sentence_id="2",
        article_published_at=date(2025, 1, 1),
        source_ref="registry",
        claim=ClaimSchema(
            claim_id="child-fragment",
            source_sentence="대졸 이상은 480억 달러였다.",
            value=480.0,
            unit="USD 100m",
            parse_status="HOLD",
            parse_reason="수치와 대상은 있지만 지표와 기준시점이 문맥에 생략됨",
        ),
    )

    result = recover_registry_record_v3(
        record,
        extractor=extractor,
        official_service=_Service(),
        article_context="2024년 석유화학 수출 중 대졸 이상은 480억 달러였다.",
    )

    child = result.entries[0]
    assert child.admission_route == "KOSIS_PIPELINE_ELIGIBLE"
    assert child.record.claim.indicator == "export value"
    assert child.record.claim.time == "2024"
    assert child.record.slot_enrichment["article_context_used"] is True
