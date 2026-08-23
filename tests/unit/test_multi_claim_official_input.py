from datetime import date

import pytest

from core.multi_claim_official_input import build_eligible_child_registry
from schemas.claim import ClaimSchema
from schemas.claim_registry import ClaimRegistryRecord


def _parent(claim_id: str = "parent-1") -> ClaimRegistryRecord:
    return ClaimRegistryRecord(
        article_id="article-1",
        sentence_id="7",
        article_published_at=date(2025, 2, 15),
        source_ref="gold",
        source_metadata={"url": "https://news.example/1"},
        claim=ClaimSchema(
            claim_id=claim_id,
            source_sentence="고용률은 60%, 실업률은 3%였다.",
            parse_status="HOLD",
            parse_reason="MULTI_CLAIM_SPLIT_REQUIRED",
        ),
    )


def _child(claim_id: str, indicator: str, route: str) -> dict[str, object]:
    claim = ClaimSchema(
        claim_id=claim_id,
        source_sentence="고용률은 60%, 실업률은 3%였다.",
        indicator=indicator,
        value=60.0,
        unit="%",
        time="2025-01",
        frequency="월",
        calculation="DIRECT_VALUE",
        parse_status="AUTO_OK",
    )
    return {
        "claim_id": claim_id,
        "admission_route": route,
        "claim": claim.model_dump(mode="json"),
        "recovery_audit": {"parent_claim_id": "parent-1"},
    }


def test_builds_registry_only_from_official_search_eligible_children() -> None:
    group_results = [
        {
            "claim_id": "parent-1",
            "children": [
                _child("child-1", "고용률", "KOSIS_PIPELINE_ELIGIBLE"),
                _child("child-2", "실업률", "STRUCTURAL_HOLD"),
            ],
        }
    ]

    records = build_eligible_child_registry([_parent()], group_results)

    assert len(records) == 1
    assert records[0].claim.claim_id == "child-1"
    assert records[0].article_published_at == date(2025, 2, 15)
    assert records[0].sentence_id == "7:multi:1"
    assert records[0].source_metadata["parent_claim_id"] == "parent-1"
    assert records[0].slot_enrichment == {"parent_claim_id": "parent-1"}


def test_refuses_eligible_child_when_parent_provenance_is_missing() -> None:
    group_results = [
        {
            "claim_id": "missing-parent",
            "children": [_child("child-1", "고용률", "KOSIS_PIPELINE_ELIGIBLE")],
        }
    ]

    with pytest.raises(ValueError, match="PARENT_REGISTRY_RECORD_NOT_FOUND"):
        build_eligible_child_registry([_parent()], group_results)


def test_refuses_duplicate_child_claim_ids() -> None:
    child = _child("child-1", "고용률", "KOSIS_PIPELINE_ELIGIBLE")
    group_results = [
        {"claim_id": "parent-1", "children": [child, child]},
    ]

    with pytest.raises(ValueError, match="DUPLICATE_ELIGIBLE_CHILD_CLAIM_ID"):
        build_eligible_child_registry([_parent()], group_results)
