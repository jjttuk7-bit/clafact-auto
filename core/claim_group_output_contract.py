"""Provider-facing strict output contract for numeric role grouping."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from schemas.claim_group import (
    ClaimGroupingPlan,
    NumericAssignment,
    NumericRole,
    ClaimGroup,
)


class GroupingAssignmentPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mention_id: str
    role: NumericRole
    group_id: str


class GroupingGroupPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_id: str
    main_mention_id: str
    indicator_hint: str


class ClaimGroupingOutputPayload(BaseModel):
    """All fields are required so provider strict-schema modes can enforce them."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["READY", "HUMAN_REVIEW"]
    reason: str
    assignments: list[GroupingAssignmentPayload]
    groups: list[GroupingGroupPayload]

    def to_plan(self) -> ClaimGroupingPlan:
        return ClaimGroupingPlan(
            status=self.status,
            reason=self.reason.strip() or None,
            assignments=[
                NumericAssignment(
                    mention_id=assignment.mention_id,
                    role=assignment.role,
                    group_id=assignment.group_id.strip() or None,
                )
                for assignment in self.assignments
            ],
            groups=[
                ClaimGroup(
                    group_id=group.group_id,
                    main_mention_id=group.main_mention_id,
                    indicator_hint=group.indicator_hint.strip() or None,
                )
                for group in self.groups
            ],
        )


def claim_grouping_json_schema() -> dict[str, object]:
    return ClaimGroupingOutputPayload.model_json_schema()
