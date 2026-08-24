"""Deterministic corrections for recurring provider grouping patterns."""

from __future__ import annotations

import re

from schemas.claim_group import (
    ClaimGroup,
    ClaimGroupingPlan,
    NumericAssignment,
    NumericMention,
    NumericRole,
)


_CROSS_VALUE_CUE = re.compile(r"(?:뛰어넘|웃돌|상회|하회|밑돌)")
_PERIOD_BEFORE_VALUE = re.compile(r"(?P<period>\d{4}년|\d{1,2}월|[1-4]분기)\s*\(\s*$")
_SERIES_PERIOD_BEFORE_VALUE = re.compile(r"(?P<period>\d{4}년|\d{1,2}월|[1-4]분기)\s*$")
_SHARE_OWNER_BEFORE = re.compile(r"의\s*$")
_SHARE_ASSERTION_AFTER = re.compile(r"^\s*(?:가량|정도)?(?:을|를)?\s*(?:맡|차지)")
_TREND_SERIES_CUE = re.compile(r"(?:\d+\s*년\s*연속|연속.{0,12}(?:줄|늘|오르|내리|증가|감소))")
_COORDINATED_NOUNS = re.compile(r"[가-힣A-Za-z·]+(?:과|와)\s*[가-힣A-Za-z·]+")
_CHANGE_ASSERTION_AFTER = re.compile(r"^\s*(?:이상|넘게|가량|정도)?\s*(?:줄|감소|늘|증가|오르|내리)")


def build_source_anchored_grouping_plan(
    source_sentence: str,
    mentions: list[NumericMention],
) -> ClaimGroupingPlan | None:
    """Recover only an explicit change-plus-owned-share pair after provider failure."""

    if len(mentions) != 2:
        return None
    change_mentions = [
        mention
        for mention in mentions
        if _is_explicit_change_assertion(source_sentence, mention)
    ]
    share_mentions = [
        mention
        for mention in mentions
        if _is_explicit_share_assertion(source_sentence, mention)
    ]
    if len(change_mentions) != 1 or len(share_mentions) != 1:
        return None
    if change_mentions[0].mention_id == share_mentions[0].mention_id:
        return None
    ordered = sorted(mentions, key=lambda mention: mention.start)
    return ClaimGroupingPlan(
        status="READY",
        assignments=[
            NumericAssignment(
                mention_id=mention.mention_id,
                role=NumericRole.MAIN_VALUE,
                group_id=f"g{index}",
            )
            for index, mention in enumerate(ordered, start=1)
        ],
        groups=[
            ClaimGroup(
                group_id=f"g{index}",
                main_mention_id=mention.mention_id,
                indicator_hint=None,
            )
            for index, mention in enumerate(ordered, start=1)
        ],
    )


def _is_explicit_change_assertion(
    source_sentence: str,
    mention: NumericMention,
) -> bool:
    normalized = mention.expression.replace("％", "%")
    if "%p" not in normalized and "%포인트" not in normalized:
        return False
    suffix = source_sentence[mention.end:mention.end + 24]
    return _CHANGE_ASSERTION_AFTER.search(suffix) is not None


def normalize_grouping_plan(
    source_sentence: str,
    mentions: list[NumericMention],
    plan: ClaimGroupingPlan,
) -> ClaimGroupingPlan:
    """Normalize only source-grounded, deterministic role relationships."""

    if plan.status != "READY":
        return plan
    if _has_ambiguous_coordinated_each(source_sentence, mentions):
        return ClaimGroupingPlan(
            status="HUMAN_REVIEW",
            reason="GROUPING_COORDINATED_EACH_AMBIGUOUS",
            assignments=[],
            groups=[],
        )
    assignments = [_normalize_context(assignment) for assignment in plan.assignments]
    assignments = _promote_change_only_anchors(assignments, plan)
    groups = list(plan.groups)
    assignments, groups = _recover_source_anchored_missing_mentions(
        source_sentence, mentions, assignments, groups
    )
    assignments = _mark_earlier_duplicate_as_context(
        source_sentence, mentions, assignments
    )
    assignments, groups = _normalize_historical_series(
        source_sentence, mentions, assignments, groups
    )

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

    assignments, groups = _split_distinct_period_values(
        source_sentence, mentions, assignments, groups
    )
    mention_by_id = {mention.mention_id: mention for mention in mentions}
    assignments.sort(key=lambda item: mention_by_id[item.mention_id].start)
    groups.sort(key=lambda item: mention_by_id[item.main_mention_id].start)
    return plan.model_copy(update={"assignments": assignments, "groups": groups})


def _has_ambiguous_coordinated_each(
    source_sentence: str,
    mentions: list[NumericMention],
) -> bool:
    each_position = source_sentence.find("각각")
    if each_position < 0:
        return False
    values_after_each = [mention for mention in mentions if mention.start > each_position]
    if len(values_after_each) != 1:
        return False
    prefix = source_sentence[max(0, each_position - 48):each_position]
    return _COORDINATED_NOUNS.search(prefix) is not None


def _normalize_historical_series(
    source_sentence: str,
    mentions: list[NumericMention],
    assignments: list[NumericAssignment],
    groups: list[ClaimGroup],
) -> tuple[list[NumericAssignment], list[ClaimGroup]]:
    if len(groups) != 1 or len(mentions) < 2:
        return assignments, groups
    if _TREND_SERIES_CUE.search(source_sentence) is None:
        return assignments, groups
    anchors = [_series_period_anchor(source_sentence, mention) for mention in mentions]
    if not all(anchors) or len(set(anchors)) != len(mentions):
        return assignments, groups
    assigned_ids = {assignment.mention_id for assignment in assignments}
    if assigned_ids != {mention.mention_id for mention in mentions}:
        return assignments, groups
    ordered = sorted(mentions, key=lambda mention: mention.start)
    group_id = groups[0].group_id
    latest_id = ordered[-1].mention_id
    normalized_assignments = [
        NumericAssignment(
            mention_id=mention.mention_id,
            role=(
                NumericRole.MAIN_VALUE
                if mention.mention_id == latest_id
                else NumericRole.REFERENCE_VALUE
            ),
            group_id=group_id,
        )
        for mention in ordered
    ]
    normalized_group = groups[0].model_copy(update={"main_mention_id": latest_id})
    return normalized_assignments, [normalized_group]


def _series_period_anchor(
    source_sentence: str,
    mention: NumericMention,
) -> str | None:
    prefix = source_sentence[max(0, mention.start - 16):mention.start]
    match = _SERIES_PERIOD_BEFORE_VALUE.search(prefix)
    return match.group("period") if match is not None else None


def _recover_source_anchored_missing_mentions(
    source_sentence: str,
    mentions: list[NumericMention],
    assignments: list[NumericAssignment],
    groups: list[ClaimGroup],
) -> tuple[list[NumericAssignment], list[ClaimGroup]]:
    assigned_ids = {assignment.mention_id for assignment in assignments}
    missing = [mention for mention in mentions if mention.mention_id not in assigned_ids]
    if not missing:
        return assignments, groups

    period_anchors = {
        mention.mention_id: _period_anchor(source_sentence, mention)
        for mention in mentions
    }
    if all(period_anchors.values()) and len(set(period_anchors.values())) == len(mentions):
        indicator_hint = groups[0].indicator_hint if groups else None
        ordered = sorted(mentions, key=lambda mention: mention.start)
        rebuilt_assignments = [
            NumericAssignment(
                mention_id=mention.mention_id,
                role=NumericRole.MAIN_VALUE,
                group_id=f"g{index}",
            )
            for index, mention in enumerate(ordered, start=1)
        ]
        rebuilt_groups = [
            ClaimGroup(
                group_id=f"g{index}",
                main_mention_id=mention.mention_id,
                indicator_hint=indicator_hint,
            )
            for index, mention in enumerate(ordered, start=1)
        ]
        return rebuilt_assignments, rebuilt_groups

    updated_assignments = list(assignments)
    updated_groups = list(groups)
    next_group_number = _next_group_number(updated_groups)
    for mention in missing:
        if not _is_explicit_share_assertion(source_sentence, mention):
            continue
        group_id = f"g{next_group_number}"
        next_group_number += 1
        updated_assignments.append(NumericAssignment(
            mention_id=mention.mention_id,
            role=NumericRole.MAIN_VALUE,
            group_id=group_id,
        ))
        updated_groups.append(ClaimGroup(
            group_id=group_id,
            main_mention_id=mention.mention_id,
            indicator_hint=None,
        ))
    return updated_assignments, updated_groups


def _period_anchor(source_sentence: str, mention: NumericMention) -> str | None:
    prefix = source_sentence[max(0, mention.start - 16):mention.start]
    match = _PERIOD_BEFORE_VALUE.search(prefix)
    return match.group("period") if match is not None else None


def _is_explicit_share_assertion(
    source_sentence: str,
    mention: NumericMention,
) -> bool:
    if "%" not in mention.expression and "％" not in mention.expression:
        return False
    prefix = source_sentence[max(0, mention.start - 40):mention.start]
    suffix = source_sentence[mention.end:mention.end + 24]
    return (
        _SHARE_OWNER_BEFORE.search(prefix) is not None
        and _SHARE_ASSERTION_AFTER.search(suffix) is not None
    )


def _mark_earlier_duplicate_as_context(
    source_sentence: str,
    mentions: list[NumericMention],
    assignments: list[NumericAssignment],
) -> list[NumericAssignment]:
    assignment_by_id = {assignment.mention_id: assignment for assignment in assignments}
    by_expression: dict[str, list[NumericMention]] = {}
    for mention in mentions:
        by_expression.setdefault(mention.expression, []).append(mention)
    context_ids: set[str] = set()
    for duplicates in by_expression.values():
        if len(duplicates) < 2:
            continue
        ordered = sorted(duplicates, key=lambda mention: mention.start)
        later = ordered[-1]
        if later.start - ordered[0].end < 8:
            continue
        after_later = source_sentence[later.end:later.end + 8]
        if re.match(r"^\s*\(\s*(?:약\s*)?", after_later) is None:
            continue
        closing = source_sentence.find(")", later.end)
        if closing < 0:
            continue
        has_equivalent = any(
            mention.start > later.end and mention.end <= closing
            and mention.expression != later.expression
            for mention in mentions
        )
        if not has_equivalent:
            continue
        context_ids.update(mention.mention_id for mention in ordered[:-1])
    return [
        assignment.model_copy(update={
            "role": NumericRole.CONTEXT_VALUE,
            "group_id": None,
        })
        if assignment.mention_id in context_ids
        and assignment.mention_id in assignment_by_id
        else assignment
        for assignment in assignments
    ]


def _next_group_number(groups: list[ClaimGroup]) -> int:
    return max((int(group.group_id[1:]) for group in groups), default=0) + 1


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


def _split_distinct_period_values(
    source_sentence: str,
    mentions: list[NumericMention],
    assignments: list[NumericAssignment],
    groups: list[ClaimGroup],
) -> tuple[list[NumericAssignment], list[ClaimGroup]]:
    mention_by_id = {mention.mention_id: mention for mention in mentions}
    next_group_number = _next_group_number(groups)
    updated_assignments = list(assignments)
    updated_groups = list(groups)
    for group in list(groups):
        grouped = [
            assignment
            for assignment in updated_assignments
            if assignment.group_id == group.group_id
        ]
        if len(grouped) < 2:
            continue
        anchored: list[tuple[NumericAssignment, NumericMention, str]] = []
        for assignment in grouped:
            mention = mention_by_id.get(assignment.mention_id)
            if mention is None:
                anchored = []
                break
            prefix = source_sentence[max(0, mention.start - 16):mention.start]
            match = _PERIOD_BEFORE_VALUE.search(prefix)
            if match is None:
                anchored = []
                break
            anchored.append((assignment, mention, match.group("period")))
        if len(anchored) < 2 or len({item[2] for item in anchored}) != len(anchored):
            continue
        ordered = sorted(anchored, key=lambda item: item[1].start)
        replacement_groups: list[ClaimGroup] = []
        replacement_ids: dict[str, str] = {}
        for index, (assignment, _, _) in enumerate(ordered):
            if index == 0:
                group_id = group.group_id
            else:
                group_id = f"g{next_group_number}"
                next_group_number += 1
            replacement_ids[assignment.mention_id] = group_id
            replacement_groups.append(ClaimGroup(
                group_id=group_id,
                main_mention_id=assignment.mention_id,
                indicator_hint=group.indicator_hint,
            ))
        updated_assignments = [
            assignment.model_copy(update={
                "role": NumericRole.MAIN_VALUE,
                "group_id": replacement_ids[assignment.mention_id],
            })
            if assignment.mention_id in replacement_ids
            else assignment
            for assignment in updated_assignments
        ]
        position = updated_groups.index(group)
        updated_groups[position:position + 1] = replacement_groups
    return updated_assignments, updated_groups
