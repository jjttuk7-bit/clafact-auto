from __future__ import annotations

import json
from datetime import date

from core.admission_recovery_v3 import recover_registry_record_v3
from schemas.claim import ClaimSchema
from schemas.claim_group import ClaimGroupingPlan
from schemas.claim_registry import ClaimRegistryRecord


class _GroupingExtractor:
    def __init__(self, plan: ClaimGroupingPlan) -> None:
        self.plan = plan
        self.group_calls = 0

    def group_claims(self, source_sentence, mentions):
        self.group_calls += 1
        return self.plan

    def extract(self, source_sentence: str, *, article_published_at=None) -> ClaimSchema:
        payload = json.loads(source_sentence)
        expression = payload["target_numeric_expression"]
        if expression == "60%":
            indicator, value, unit = "고용률", 60.0, "%"
        elif expression == "58%":
            indicator, value, unit = "실업률", 58.0, "%"
        else:
            indicator, value, unit = "취업자 수", 100000.0, "명"
        return ClaimSchema(
            claim_id="temporary",
            source_sentence=source_sentence,
            indicator=indicator,
            value=value,
            unit=unit,
            time="2025년 1월",
            frequency="월",
            calculation="DIRECT_VALUE",
            parse_status="AUTO_OK",
        )


class _Service:
    def __init__(self) -> None:
        self.claims: list[ClaimSchema] = []

    def resolve(self, claim, *, article_date):
        self.claims.append(claim)
        return {"route_status": "AUTO"}


def _record(source: str) -> ClaimRegistryRecord:
    return ClaimRegistryRecord(
        article_id="A1",
        sentence_id="1",
        article_published_at=date(2025, 2, 1),
        source_ref="registry",
        claim=ClaimSchema(
            claim_id="parent",
            source_sentence=source,
            parse_status="HOLD",
            parse_reason="MULTI_CLAIM_SPLIT_REQUIRED",
        ),
    )


def _ready_plan(assignments: list[dict], groups: list[dict]) -> ClaimGroupingPlan:
    return ClaimGroupingPlan.model_validate(
        {
            "status": "READY",
            "assignments": assignments,
            "groups": groups,
        }
    )


def test_comparison_numbers_form_one_child_with_role_audit() -> None:
    source = "고용률은 60%로 전년 58%보다 2%포인트 올랐다."
    extractor = _GroupingExtractor(
        _ready_plan(
            [
                {"mention_id": "n1", "role": "MAIN_VALUE", "group_id": "g1"},
                {"mention_id": "n2", "role": "REFERENCE_VALUE", "group_id": "g1"},
                {"mention_id": "n3", "role": "CHANGE_VALUE", "group_id": "g1"},
            ],
            [{"group_id": "g1", "main_mention_id": "n1"}],
        )
    )
    service = _Service()

    result = recover_registry_record_v3(
        _record(source), extractor=extractor, official_service=service
    )

    assert result.recovery_action == "MULTI_CLAIM_SPLIT"
    assert len(result.entries) == 1
    assert result.entries[0].record.slot_enrichment["numeric_roles"] == {
        "60%": "MAIN_VALUE",
        "58%": "REFERENCE_VALUE",
        "2%포인트": "CHANGE_VALUE",
    }
    assert len(service.claims) == 1


def test_two_independent_indicators_form_two_children() -> None:
    source = "고용률은 60%이고 실업률은 58%였다."
    extractor = _GroupingExtractor(
        _ready_plan(
            [
                {"mention_id": "n1", "role": "MAIN_VALUE", "group_id": "g1"},
                {"mention_id": "n2", "role": "MAIN_VALUE", "group_id": "g2"},
            ],
            [
                {"group_id": "g1", "main_mention_id": "n1"},
                {"group_id": "g2", "main_mention_id": "n2"},
            ],
        )
    )
    service = _Service()

    result = recover_registry_record_v3(
        _record(source), extractor=extractor, official_service=service
    )

    assert len(result.entries) == 2
    assert len({entry.record.claim.claim_id for entry in result.entries}) == 2
    assert len(service.claims) == 2


def test_ambiguous_grouping_never_calls_official_service() -> None:
    source = "고용률은 60%이고 실업률은 58%였다."
    extractor = _GroupingExtractor(
        ClaimGroupingPlan.model_validate(
            {
                "status": "HUMAN_REVIEW",
                "reason": "두 수치의 관계를 확정할 수 없음",
                "assignments": [],
                "groups": [],
            }
        )
    )
    service = _Service()

    result = recover_registry_record_v3(
        _record(source), extractor=extractor, official_service=service
    )

    assert len(result.entries) == 1
    assert result.entries[0].admission_route == "STRUCTURAL_HOLD"
    assert result.entries[0].record.claim.parse_reason == "GROUPING_AMBIGUOUS"
    assert service.claims == []


class _FailingGroupExtractor:
    def group_claims(self, source_sentence, mentions):
        raise RuntimeError("provider output invalid")

    def extract(self, source_sentence: str, *, article_published_at=None) -> ClaimSchema:
        payload = json.loads(source_sentence)
        expression = payload["target_numeric_expression"]
        if expression == "9%p":
            indicator, value, unit = "중국·홍콩 수출 비율 감소폭", 9.0, "%포인트"
        else:
            indicator, value, unit = "반도체 수출 비중", 20.0, "%"
        return ClaimSchema(
            claim_id="temporary",
            source_sentence=source_sentence,
            indicator=indicator,
            value=value,
            unit=unit,
            time="2025년",
            frequency="연",
            calculation="DIRECT_VALUE",
            comparison={"type": "NONE"},
            parse_status="AUTO_OK",
        )


def test_provider_grouping_failure_uses_only_source_anchored_fallback() -> None:
    source = (
        "반도체 수출의 중국 비율이 9%p 이상 줄어 "
        "우리나라 수출의 20%가량을 맡고 있는 핵심 품목의 지형이 변했다."
    )
    service = _Service()

    result = recover_registry_record_v3(
        _record(source), extractor=_FailingGroupExtractor(), official_service=service
    )

    assert len(result.entries) == 2
    assert [
        entry.record.slot_enrichment["target_numeric_expression"]
        for entry in result.entries
    ] == ["9%p", "20%"]


def test_provider_grouping_failure_without_source_cues_still_fails_closed() -> None:
    source = "관련 비율은 9%와 20%로 알려졌다."

    try:
        recover_registry_record_v3(
            _record(source), extractor=_FailingGroupExtractor(), official_service=_Service()
        )
    except Exception as error:
        assert error.__class__.__name__ == "OperationalStageError"
    else:
        raise AssertionError("ambiguous provider failure must not be recovered")
