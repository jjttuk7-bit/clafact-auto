import json

from core.source_target_grounding import build_target_grounding, merge_target_grounding
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


def _row(*, status: str = "TARGET_SELECTED") -> dict[str, str]:
    source = "20대 인구는 2020년 703만명이다."
    mentions = [
        {"mention_id": "n1", "expression": "20대", "start": 0, "end": 3, "context": source},
        {"mention_id": "n2", "expression": "2020년", "start": 8, "end": 13, "context": source},
        {"mention_id": "n3", "expression": "703만명", "start": 14, "end": 19, "context": source},
    ]
    roles = [
        {"mention_id": "n1", "expression": "20대", "role": "연령", "reason_code": "AGE_GROUP_CONTEXT", "auto_target_eligible": False},
        {"mention_id": "n2", "expression": "2020년", "role": "기간", "reason_code": "PERIOD_CONTEXT", "auto_target_eligible": False},
        {"mention_id": "n3", "expression": "703만명", "role": "대상값", "reason_code": "SOURCE_GROUNDED_MAIN", "auto_target_eligible": True},
    ]
    return {
        "Claim번호": "A02624_7",
        "원문": source,
        "원문수치목록JSON": json.dumps(mentions, ensure_ascii=False),
        "숫자역할목록JSON": json.dumps(roles, ensure_ascii=False),
        "자동대상표현": "703만명" if status == "TARGET_SELECTED" else "",
        "자동대상역할": "대상값" if status == "TARGET_SELECTED" else "",
        "대상연결상태": status,
    }


def test_builds_exact_source_grounding_with_span_and_enrichment() -> None:
    result = build_target_grounding(_row())

    assert result.status == "SOURCE_GROUNDED"
    assert result.expression == "703만명"
    assert (result.start, result.end) == (14, 19)
    assert result.slot_enrichment_patch["target_numeric_expression"] == "703만명"


def test_maps_unselected_states_to_preverification_reasons() -> None:
    statuses = {
        "TARGET_BLOCKED_BY_CONTEXT_ROLE": "TARGET_CONTEXT_ROLE_CONFLICT",
        "NO_TARGET_MATCH": "TARGET_NOT_FOUND_IN_SOURCE",
        "AMBIGUOUS_TARGET_MATCH": "TARGET_AMBIGUOUS_IN_SOURCE",
    }

    for source_status, expected in statuses.items():
        result = build_target_grounding(_row(status=source_status))
        assert result.status == expected
        assert result.reason_code == expected
        assert result.expression == ""


def test_merges_grounding_without_losing_existing_enrichment() -> None:
    record = ClaimRegistryRecord(
        article_id="A02624",
        sentence_id="7",
        source_ref="frozen",
        claim=ClaimSchema(
            claim_id="A02624_7",
            source_sentence=_row()["원문"],
            indicator="인구",
            value=7_030_000,
            unit="명",
            time="2020",
            frequency="Y",
            calculation="DIRECT_VALUE",
            parse_status="AUTO_OK",
        ),
        slot_enrichment={"existing": "kept"},
    )

    merged = merge_target_grounding(record, build_target_grounding(_row()))

    assert merged.slot_enrichment["existing"] == "kept"
    assert merged.slot_enrichment["target_numeric_expression"] == "703만명"
