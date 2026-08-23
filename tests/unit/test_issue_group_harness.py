from __future__ import annotations

import pytest

from core.issue_group_harness import IssueGroup, classify_claim


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        ("CONTEXT_REQUIRED", IssueGroup.CONTEXT),
        ("KOSIS_CATALOG_UNAVAILABLE", IssueGroup.OFFICIAL_PATH),
        ("KOSIS_METADATA_UNAVAILABLE", IssueGroup.OFFICIAL_PATH),
        ("NO_HARD_GUARD_CANDIDATE", IssueGroup.HARD_GUARD),
        ("NO_EVIDENCE_COORDINATE_CANDIDATE", IssueGroup.COORDINATE),
        ("LOW_SEMANTIC_SCORE", IssueGroup.SEMANTIC),
        ("AMBIGUOUS_MARGIN", IssueGroup.SEMANTIC),
        ("CONCEPT_NOT_FOUND", IssueGroup.SEMANTIC),
        ("CALCULATION_EVIDENCE_PLAN_UNRESOLVED", IssueGroup.CALCULATION),
        ("CALCULATION_FAILED", IssueGroup.CALCULATION),
        ("FETCH_FAILED", IssueGroup.VALUE_PUBLICATION),
        ("AS_OF_UNAVAILABLE", IssueGroup.VALUE_PUBLICATION),
        ("PUBLICATION_FETCH_FAILED", IssueGroup.VALUE_PUBLICATION),
    ],
)
def test_classify_claim_maps_known_reason_to_one_primary_group(
    reason: str,
    expected: IssueGroup,
) -> None:
    classified = classify_claim(_row(reason=reason))

    assert classified.primary_group is expected
    assert classified.current_reason == reason


def test_classify_claim_routes_auto_to_regression() -> None:
    classified = classify_claim(_row(reason="WITHIN_TOLERANCE", status="AUTO"))

    assert classified.primary_group is IssueGroup.REGRESSION


def test_classify_claim_does_not_guess_unknown_reason() -> None:
    classified = classify_claim(_row(reason="NEW_UNKNOWN_REASON"))

    assert classified.primary_group is IssueGroup.UNCLASSIFIED


def test_classify_claim_uses_earliest_failed_stage_and_keeps_later_failures() -> None:
    row = _row(reason="FETCH_FAILED")
    row["official_resolution"] = {
        "verdict": {
            "route_status": "HOLD",
            "reason_code": "FETCH_FAILED",
            "execution_trace": {
                "events": [
                    {"stage": "SEMANTIC_MAPPING", "status": "PASS", "reason_code": None},
                    {"stage": "HARD_GUARD", "status": "HOLD", "reason_code": "NO_HARD_GUARD_CANDIDATE"},
                    {"stage": "OFFICIAL_VALUE_FETCH", "status": "HOLD", "reason_code": "FETCH_FAILED"},
                ]
            },
        }
    }

    classified = classify_claim(row)

    assert classified.primary_group is IssueGroup.HARD_GUARD
    assert classified.current_stop_stage == "HARD_GUARD"
    assert classified.secondary_issues == ("OFFICIAL_VALUE_FETCH:FETCH_FAILED",)


def _row(*, reason: str, status: str = "HOLD") -> dict[str, object]:
    return {
        "article_id": "A-001",
        "sentence_id": "S-001",
        "parent_claim_id": "P-001",
        "claim_id": "C-001",
        "source_sentence": "취업자는 10만 명 증가했다.",
        "terminal_status": status,
        "reason_code": reason,
        "claim": {"claim_id": "C-001", "indicator": "취업자"},
        "slot_audit": {"eligible_for_official_search": True, "entries": []},
        "stage_results": [],
        "official_resolution": None,
    }
