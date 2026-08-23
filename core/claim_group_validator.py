"""Fail-closed validation for provider-proposed numeric Claim groups."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from schemas.claim_group import (
    ClaimGroupingPlan,
    NumericMention,
    NumericRole,
)


@dataclass(frozen=True, slots=True)
class ValidatedClaimGroup:
    group_id: str
    main_mention_id: str
    main_expression: str
    numeric_roles: tuple[tuple[str, str], ...]
    numeric_assignments: tuple[tuple[str, str, str], ...]


@dataclass(frozen=True, slots=True)
class GroupValidationResult:
    valid: bool
    groups: tuple[ValidatedClaimGroup, ...]
    reason_code: str | None = None


def validate_grouping_plan(
    mentions: list[NumericMention],
    plan: ClaimGroupingPlan,
) -> GroupValidationResult:
    """Accept only a complete, non-duplicated assignment over grounded mentions."""

    if plan.status != "READY":
        return _failure("GROUPING_AMBIGUOUS")

    mention_by_id = {mention.mention_id: mention for mention in mentions}
    assignment_ids = [assignment.mention_id for assignment in plan.assignments]
    assignment_counts = Counter(assignment_ids)
    if any(count > 1 for count in assignment_counts.values()):
        return _failure("GROUPING_DUPLICATE_ASSIGNMENT")

    discovered_ids = set(mention_by_id)
    assigned_ids = set(assignment_ids)
    if assigned_ids - discovered_ids:
        return _failure("GROUPING_UNKNOWN_MENTION")
    if discovered_ids - assigned_ids:
        return _failure("GROUPING_MENTION_MISSING")

    known_groups = {group.group_id for group in plan.groups}
    for assignment in plan.assignments:
        if assignment.role != NumericRole.CONTEXT_VALUE and assignment.group_id is None:
            return _failure("GROUPING_MAIN_VALUE_INVALID")
        if assignment.group_id is not None and assignment.group_id not in known_groups:
            return _failure("GROUPING_MAIN_VALUE_INVALID")

    validated: list[ValidatedClaimGroup] = []
    for group in plan.groups:
        group_assignments = [
            assignment
            for assignment in plan.assignments
            if assignment.group_id == group.group_id
        ]
        anchors = [
            assignment
            for assignment in group_assignments
            if assignment.mention_id == group.main_mention_id
        ]
        main_values = [
            assignment
            for assignment in group_assignments
            if assignment.role == NumericRole.MAIN_VALUE
        ]
        if (
            len(main_values) > 1
            or len(anchors) != 1
            or anchors[0].role
            not in {NumericRole.MAIN_VALUE, NumericRole.CHANGE_VALUE}
            or (
                bool(main_values)
                and main_values[0].mention_id != group.main_mention_id
            )
        ):
            return _failure("GROUPING_MAIN_VALUE_INVALID")
        main = mention_by_id.get(group.main_mention_id)
        if main is None:
            return _failure("GROUPING_UNKNOWN_MENTION")
        roles = tuple(
            (
                mention_by_id[assignment.mention_id].expression,
                assignment.role.value,
            )
            for assignment in group_assignments
        )
        numeric_assignments = tuple(
            (
                assignment.mention_id,
                mention_by_id[assignment.mention_id].expression,
                assignment.role.value,
            )
            for assignment in group_assignments
        )
        validated.append(
            ValidatedClaimGroup(
                group_id=group.group_id,
                main_mention_id=group.main_mention_id,
                main_expression=main.expression,
                numeric_roles=roles,
                numeric_assignments=numeric_assignments,
            )
        )
    return GroupValidationResult(valid=True, groups=tuple(validated))


def _failure(reason_code: str) -> GroupValidationResult:
    return GroupValidationResult(valid=False, groups=(), reason_code=reason_code)
