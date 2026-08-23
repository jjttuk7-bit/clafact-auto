"""Bounded issue-group control plane for Registry improvement runs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class IssueGroup(StrEnum):
    CONTEXT = "CONTEXT"
    OFFICIAL_PATH = "OFFICIAL_PATH"
    HARD_GUARD = "HARD_GUARD"
    COORDINATE = "COORDINATE"
    SEMANTIC = "SEMANTIC"
    CALCULATION = "CALCULATION"
    VALUE_PUBLICATION = "VALUE_PUBLICATION"
    REGRESSION = "REGRESSION"
    UNCLASSIFIED = "UNCLASSIFIED"


@dataclass(frozen=True, slots=True)
class ClaimIssueRecord:
    article_id: str
    sentence_id: str
    parent_claim_id: str
    claim_id: str
    source_sentence: str
    current_status: str
    current_reason: str | None
    current_stop_stage: str | None
    primary_group: IssueGroup
    secondary_issues: tuple[str, ...] = ()


_REASON_GROUP: dict[str, IssueGroup] = {
    "CONTEXT_REQUIRED": IssueGroup.CONTEXT,
    "MULTI_CLAIM_SPLIT_REQUIRED": IssueGroup.CONTEXT,
    "STRUCTURAL_HOLD": IssueGroup.CONTEXT,
    "KOSIS_CATALOG_UNAVAILABLE": IssueGroup.OFFICIAL_PATH,
    "KOSIS_METADATA_UNAVAILABLE": IssueGroup.OFFICIAL_PATH,
    "NO_HARD_GUARD_CANDIDATE": IssueGroup.HARD_GUARD,
    "NO_EVIDENCE_COORDINATE_CANDIDATE": IssueGroup.COORDINATE,
    "LOW_SEMANTIC_SCORE": IssueGroup.SEMANTIC,
    "AMBIGUOUS_MARGIN": IssueGroup.SEMANTIC,
    "CONCEPT_NOT_FOUND": IssueGroup.SEMANTIC,
    "CALCULATION_EVIDENCE_PLAN_UNRESOLVED": IssueGroup.CALCULATION,
    "CALCULATION_FAILED": IssueGroup.CALCULATION,
    "FETCH_FAILED": IssueGroup.VALUE_PUBLICATION,
    "AS_OF_UNAVAILABLE": IssueGroup.VALUE_PUBLICATION,
    "PUBLICATION_FETCH_FAILED": IssueGroup.VALUE_PUBLICATION,
}

_REASON_STAGE: dict[str, str] = {
    "CONTEXT_REQUIRED": "CLAIM_PARSE",
    "MULTI_CLAIM_SPLIT_REQUIRED": "CLAIM_SPLIT",
    "STRUCTURAL_HOLD": "CLAIM_PARSE",
    "KOSIS_CATALOG_UNAVAILABLE": "CATALOG_SEARCH",
    "KOSIS_METADATA_UNAVAILABLE": "KOSIS_METADATA",
    "NO_HARD_GUARD_CANDIDATE": "HARD_GUARD",
    "NO_EVIDENCE_COORDINATE_CANDIDATE": "EVIDENCE_CELL",
    "LOW_SEMANTIC_SCORE": "SEMANTIC_MATCH",
    "AMBIGUOUS_MARGIN": "SEMANTIC_MATCH",
    "CONCEPT_NOT_FOUND": "SEMANTIC_MAPPING",
    "CALCULATION_EVIDENCE_PLAN_UNRESOLVED": "CALCULATION",
    "CALCULATION_FAILED": "CALCULATION",
    "FETCH_FAILED": "OFFICIAL_VALUE_FETCH",
    "AS_OF_UNAVAILABLE": "OFFICIAL_VALUE_FETCH",
    "PUBLICATION_FETCH_FAILED": "OFFICIAL_VALUE_FETCH",
}

_STAGE_ORDER = {
    name: index
    for index, name in enumerate(
        (
            "PREPROCESS",
            "SENTENCE_SPLIT",
            "CLAIM_CANDIDATE_SELECTION",
            "CLAIM_SPLIT",
            "CLAIM_PARSE",
            "SEMANTIC_MAPPING",
            "CATALOG_SEARCH",
            "KOSIS_METADATA",
            "HARD_GUARD",
            "SEMANTIC_MATCH",
            "EVIDENCE_CELL",
            "OFFICIAL_VALUE_FETCH",
            "CALCULATION",
            "VERDICT",
        )
    )
}


def classify_claim(row: dict[str, Any]) -> ClaimIssueRecord:
    """Assign one primary issue from the earliest observed failing stage."""

    status, terminal_reason = _terminal(row)
    failures = _observed_failures(row)
    if status == "AUTO":
        group = IssueGroup.REGRESSION
        stop_stage = "VERDICT"
        secondary: tuple[str, ...] = ()
    elif failures:
        ordered = sorted(
            enumerate(failures),
            key=lambda item: (_STAGE_ORDER.get(item[1][0], 10_000), item[0]),
        )
        _, (stop_stage, primary_reason) = ordered[0]
        terminal_reason = primary_reason
        group = _REASON_GROUP.get(primary_reason, IssueGroup.UNCLASSIFIED)
        secondary = tuple(
            f"{stage}:{reason}" for _, (stage, reason) in ordered[1:]
        )
    else:
        group = _REASON_GROUP.get(terminal_reason or "", IssueGroup.UNCLASSIFIED)
        stop_stage = _REASON_STAGE.get(terminal_reason or "")
        secondary = ()

    return ClaimIssueRecord(
        article_id=str(row.get("article_id") or ""),
        sentence_id=str(row.get("sentence_id") or ""),
        parent_claim_id=str(row.get("parent_claim_id") or ""),
        claim_id=str(row.get("claim_id") or ""),
        source_sentence=str(row.get("source_sentence") or ""),
        current_status=status,
        current_reason=terminal_reason,
        current_stop_stage=stop_stage,
        primary_group=group,
        secondary_issues=secondary,
    )


def _terminal(row: dict[str, Any]) -> tuple[str, str | None]:
    resolution = row.get("official_resolution")
    verdict = resolution.get("verdict") if isinstance(resolution, dict) else None
    if isinstance(verdict, dict):
        return (
            str(verdict.get("route_status") or row.get("terminal_status") or "HOLD"),
            _text(verdict.get("reason_code") or row.get("reason_code")),
        )
    return (
        str(row.get("terminal_status") or "HOLD"),
        _text(row.get("reason_code") or row.get("admission_route")),
    )


def _observed_failures(row: dict[str, Any]) -> list[tuple[str, str]]:
    resolution = row.get("official_resolution")
    verdict = resolution.get("verdict") if isinstance(resolution, dict) else None
    trace = verdict.get("execution_trace") if isinstance(verdict, dict) else None
    events = trace.get("events") if isinstance(trace, dict) else None
    failures: list[tuple[str, str]] = []
    for event in events or []:
        if not isinstance(event, dict) or event.get("status") == "PASS":
            continue
        stage = _text(event.get("stage"))
        reason = _text(event.get("reason_code"))
        if stage and reason:
            failures.append((stage, reason))
    return failures


def _text(value: object) -> str | None:
    return str(value) if value is not None and str(value) else None
