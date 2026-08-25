from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

import pytest

import core.unified_claim_pipeline as pipeline
from core.operational_error import OperationalStageError
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


class _Extractor:
    def extract(self, source_sentence: str, *, article_published_at: date | None = None) -> ClaimSchema:
        if source_sentence.startswith("{"):
            source_sentence = json.loads(source_sentence)["article_context"]
        if source_sentence.startswith("고용동향 발표."):
            return ClaimSchema(
                claim_id="temporary",
                source_sentence=source_sentence,
                indicator="고용률",
                value=60,
                unit="%",
                time="2024년 12월",
                frequency="월",
                region="전국",
                calculation="DIRECT_VALUE",
                parse_status="AUTO_OK",
            )
        if "지난달" in source_sentence:
            return ClaimSchema(
                claim_id="temporary",
                source_sentence=source_sentence,
                parse_status="HOLD",
                parse_reason="지난달 기준 시점에 기사 문맥이 필요함",
            )
        year = "2023년" if "2023" in source_sentence else "2024년"
        value = 60 if "60%" in source_sentence else 61
        return ClaimSchema(
            claim_id="temporary",
            source_sentence=source_sentence,
            indicator="고용률",
            value=value,
            unit="%",
            time=year,
            frequency="년",
            calculation="DIRECT_VALUE",
            parse_status="AUTO_OK",
        )


@dataclass
class _Verdict:
    route_status: str = "AUTO"
    reason_code: str | None = None

    def model_dump(self, *, mode: str) -> dict[str, object]:
        return {"route_status": self.route_status, "reason_code": self.reason_code}


@dataclass
class _Resolution:
    verdict: _Verdict
    concept: None = None
    candidates: tuple[()] = ()


class _OfficialService:
    def __init__(self) -> None:
        self.claims: list[ClaimSchema] = []

    def resolve(self, claim: ClaimSchema, *, article_date: date) -> _Resolution:
        self.claims.append(claim)
        return _Resolution(_Verdict())


def test_article_multi_claims_all_reenter_the_same_official_service() -> None:
    service = _OfficialService()

    result = pipeline.verify_article(
        "2023년 고용률은 60%였고 2024년 고용률은 61%였다.",
        article_published_at=date(2025, 1, 10),
        extractor=_Extractor(),
        official_service=service,
    )

    assert len(result.entries) == 2
    assert len(service.claims) == 2
    assert {entry.terminal_status for entry in result.entries} == {"AUTO"}
    assert all(entry.recovery_action == "DIRECT" for entry in result.entries)


def test_context_required_claim_reparses_article_context_and_reenters_official_service() -> None:
    service = _OfficialService()

    result = pipeline.verify_article(
        "고용동향 발표. 지난달 고용률은 60%였다.",
        article_published_at=date(2025, 1, 10),
        extractor=_Extractor(),
        official_service=service,
    )

    assert len(result.entries) == 1
    assert result.entries[0].recovery_action == "CONTEXT_REPARSE"
    assert result.entries[0].terminal_status == "AUTO"
    assert len(service.claims) == 1


def test_registry_record_uses_the_same_pipeline_entry_contract_as_article() -> None:
    service = _OfficialService()
    claim = ClaimSchema(
        claim_id="registry-claim",
        source_sentence="2024년 고용률은 60%였다.",
        indicator="고용률",
        value=60,
        unit="%",
        time="2024년",
        frequency="년",
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )
    record = ClaimRegistryRecord(
        article_id="article-1",
        sentence_id="1",
        article_published_at=date(2025, 1, 10),
        source_ref="test",
        claim=claim,
    )

    entries = pipeline.verify_registry_record(
        record,
        extractor=_Extractor(),
        official_service=service,
        article_context="기사 본문",
    )

    assert len(entries) == 1
    assert isinstance(entries[0], pipeline.PipelineEntry)
    assert entries[0].claim.claim_id == "registry-claim"
    assert entries[0].terminal_status == "AUTO"
    assert service.claims == [claim]


def test_registry_stored_slots_mode_never_calls_structured_extractor() -> None:
    service = _OfficialService()

    class _ForbiddenExtractor:
        def extract(self, source_sentence: str, **kwargs) -> ClaimSchema:
            raise AssertionError("external structured extraction must stay disabled")

    claim = ClaimSchema(
        claim_id="stored-claim",
        source_sentence="2024년 고용률은 60%였다.",
        indicator="고용률",
        value=60,
        unit="%",
        time="2024년",
        frequency="년",
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )
    record = ClaimRegistryRecord(
        article_id="article-safe",
        sentence_id="1",
        article_published_at=date(2025, 1, 10),
        source_ref="test",
        claim=claim,
    )

    entries = pipeline.verify_registry_record(
        record,
        extractor=_ForbiddenExtractor(),
        official_service=service,
        article_context="전송하면 안 되는 기사 본문",
        allow_structured_recovery=False,
    )

    assert len(entries) == 1
    assert entries[0].claim is claim
    assert entries[0].recovery_action == "DIRECT"
    assert entries[0].terminal_status == "AUTO"
    assert service.claims == [claim]


def test_sentence_only_continuation_never_reaches_official_service_without_target() -> None:
    service = _OfficialService()

    class _ContextlessAutoExtractor:
        def extract(self, source_sentence: str, **kwargs) -> ClaimSchema:
            return ClaimSchema(
                claim_id="temporary",
                source_sentence="고용률도 2011년 36.8%에서 지난달 48.3%로 불었다.",
                indicator="고용률",
                value=48.3,
                unit="%",
                time="2025년 5월",
                frequency="월",
                population="전체",
                comparison={"type": "INCREASE", "reference_period": "2011"},
                calculation="DIRECT_VALUE",
                parse_status="AUTO_OK",
            )

    result = pipeline.verify_article(
        "고용률도 2011년 36.8%에서 지난달 48.3%로 불었다.",
        article_published_at=date(2025, 6, 12),
        extractor=_ContextlessAutoExtractor(),
        official_service=service,
    )

    assert len(result.entries) == 1
    assert result.entries[0].terminal_status == "HUMAN_REVIEW"
    assert result.entries[0].admission_route == "CONTEXT_REQUIRED"
    assert result.entries[0].reason_code == "CONTEXT_TARGET_UNRESOLVED"
    assert service.claims == []


def test_article_extractor_failure_is_wrapped_as_claim_parse_operational_error() -> None:
    class FailingExtractor:
        def extract(self, source_sentence: str, **kwargs) -> ClaimSchema:
            raise RuntimeError("provider unavailable")

    with pytest.raises(OperationalStageError) as caught:
        pipeline.verify_article(
            "2024년 고용률은 60%였다.",
            article_published_at=date(2025, 1, 10),
            extractor=FailingExtractor(),
            official_service=_OfficialService(),
        )

    assert caught.value.stage == "CLAIM_PARSE"
    assert caught.value.diagnostic_id

class _TradeMissingTimeExtractor:
    def extract(self, source_sentence: str, **kwargs) -> ClaimSchema:
        return ClaimSchema(
            claim_id="trade-cumulative",
            source_sentence="연간 누계 무역 수지는 10억5600만달러 적자다.",
            indicator="무역 수지",
            value=1_056_000_000,
            unit="달러",
            time=None,
            frequency=None,
            calculation="DIRECT_VALUE",
            parse_status="HOLD",
            parse_reason="MISSING_REQUIRED_SLOTS:time",
        )


def test_dashboard_trade_cumulative_recovers_period_before_admission_hold() -> None:
    service = _OfficialService()

    result = pipeline.verify_article(
        "연간 누계 무역 수지는 10억5600만달러 적자다.",
        article_published_at=date(2025, 2, 21),
        extractor=_TradeMissingTimeExtractor(),
        official_service=service,
    )

    assert result.entries[0].claim.time == "2025-01-01/2025-02-20"
    assert result.entries[0].claim.frequency == "CUMULATIVE_PERIOD"
    assert result.entries[0].claim.parse_status == "AUTO_OK"
    assert result.entries[0].claim.parse_reason is None
    assert len(service.claims) == 1
    assert service.claims[0].time == "2025-01-01/2025-02-20"


class _AgeRoleMistakeExtractor:
    def extract(
        self,
        source_sentence: str,
        *,
        article_published_at: date | None = None,
    ) -> ClaimSchema:
        return ClaimSchema(
            claim_id="temporary",
            source_sentence=source_sentence,
            indicator="총인구",
            value=20,
            unit="대",
            time="2020년",
            frequency="년",
            calculation="DIRECT_VALUE",
            parse_status="AUTO_OK",
        )


def test_dashboard_shared_pipeline_blocks_age_role_before_official_lookup() -> None:
    from core.canonical_pipeline import CanonicalPipeline
    from core.dashboard_acceptance import verify_dashboard_article

    service = _OfficialService()
    runtime = CanonicalPipeline(
        extractor=_AgeRoleMistakeExtractor(),
        official_service=service,
    )

    result = verify_dashboard_article(
        runtime,
        "20대 인구는 2020년 703만명을 기록했다.",
        article_published_at=date(2025, 1, 1),
    )

    assert len(result.entries) == 1
    assert result.entries[0].claim.parse_status == "HOLD"
    assert result.entries[0].reason_code == "TARGET_NUMERIC_ROLE_CONFLICT:AGE_GROUP"
    assert service.claims == []
