"""Deterministic corrections for recurring provider grouping patterns."""

from __future__ import annotations

import re

from schemas.claim_group import (
    ClaimGroupingPlan,
    NumericAssignment,
    NumericMention,
    NumericRole,
)


_CROSS_VALUE_CUE = re.compile(r"(?:뛰어넘|웃돌|상회|하회|밑돌)")


def normalize_grouping_plan(
    source_sentence: str,
    mentions: list[NumericMention],
    plan: ClaimGroupingPlan,
) -> ClaimGroupingPlan:
    """Normalize only source-grounded, deterministic role relationships."""

    if plan.status != "READY":
        return plan
    assignments = [_normalize_context(assignment) for assignment in plan.assignments]
    assignments = _promote_change_only_anchors(assignments, plan)
    groups = list(plan.groups)

    merge = _parenthetical_reference_merge(source_sentence, mentions, assignments, plan)
    if merge is not None:
        main_group_id, reference_mention_id, removed_group_id = merge
        assignments = [
            assignment.model_copy(
                update={"role": NumericRole.REFERENCE_VALUE, "group_id": main_group_id}
            )
            if assignment.mention_id == reference_mention_id
            else assignment
            for assignment in assignments
        ]
        groups = [group for group in groups if group.group_id != removed_group_id]

    return plan.model_copy(update={"assignments": assignments, "groups": groups})


def _normalize_context(assignment: NumericAssignment) -> NumericAssignment:
    if assignment.role != NumericRole.CONTEXT_VALUE or assignment.group_id is None:
        return assignment
    return assignment.model_copy(update={"group_id": None})


def _promote_change_only_anchors(
    assignments: list[NumericAssignment],
    plan: ClaimGroupingPlan,
) -> list[NumericAssignment]:
    promoted = list(assignments)
    for group in plan.groups:
        grouped = [item for item in promoted if item.group_id == group.group_id]
        if any(item.role == NumericRole.MAIN_VALUE for item in grouped):
            continue
        promoted = [
            item.model_copy(update={"role": NumericRole.MAIN_VALUE})
            if item.mention_id == group.main_mention_id
            and item.role == NumericRole.CHANGE_VALUE
            else item
            for item in promoted
        ]
    return promoted


def _parenthetical_reference_merge(
    source_sentence: str,
    mentions: list[NumericMention],
    assignments: list[NumericAssignment],
    plan: ClaimGroupingPlan,
) -> tuple[str, str, str] | None:
    grouped = [item for item in assignments if item.group_id is not None]
    if len(plan.groups) != 2 or len(grouped) != 2:
        return None
    mention_by_id = {mention.mention_id: mention for mention in mentions}
    try:
        ordered = sorted(grouped, key=lambda item: mention_by_id[item.mention_id].start)
    except KeyError:
        return None
    main_assignment, reference_assignment = ordered
    if main_assignment.group_id == reference_assignment.group_id:
        return None
    reference = mention_by_id[reference_assignment.mention_id]
    if reference.start == 0 or reference.end >= len(source_sentence):
        return None
    if source_sentence[reference.start - 1] != "(" or source_sentence[reference.end] != ")":
        return None
    suffix = source_sentence[reference.end + 1 : reference.end + 20]
    if _CROSS_VALUE_CUE.search(suffix) is None:
        return None
    return (
        str(main_assignment.group_id),
        reference_assignment.mention_id,
        str(reference_assignment.group_id),
    )
