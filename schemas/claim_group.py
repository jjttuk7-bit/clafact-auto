"""Strict contracts for assigning numeric mentions to independent Claim groups."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class NumericRole(StrEnum):
    MAIN_VALUE = "MAIN_VALUE"
    REFERENCE_VALUE = "REFERENCE_VALUE"
    CHANGE_VALUE = "CHANGE_VALUE"
    EQUIVALENT_VALUE = "EQUIVALENT_VALUE"
    CONTEXT_VALUE = "CONTEXT_VALUE"


class NumericMention(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mention_id: str = Field(pattern=r"^n[1-9]\d*$")
    expression: str = Field(min_length=1)
    start: int = Field(ge=0)
    end: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_span(self) -> "NumericMention":
        if self.end <= self.start:
            raise ValueError("NUMERIC_MENTION_SPAN_INVALID")
        return self


class NumericAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mention_id: str = Field(pattern=r"^n[1-9]\d*$")
    role: NumericRole
    group_id: str | None = Field(default=None, pattern=r"^g[1-9]\d*$")


class ClaimGroup(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    group_id: str = Field(pattern=r"^g[1-9]\d*$")
    main_mention_id: str = Field(pattern=r"^n[1-9]\d*$")
    indicator_hint: str | None = None


class ClaimGroupingPlan(BaseModel):
    """One provider proposal; deterministic validation still runs afterward."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["READY", "HUMAN_REVIEW"]
    reason: str | None = None
    assignments: list[NumericAssignment]
    groups: list[ClaimGroup]

    @model_validator(mode="after")
    def validate_group_contract(self) -> "ClaimGroupingPlan":
        if self.status == "HUMAN_REVIEW":
            if self.groups:
                raise ValueError("HUMAN_REVIEW_CANNOT_CONTAIN_GROUPS")
            if not self.reason:
                raise ValueError("HUMAN_REVIEW_REASON_REQUIRED")
            return self
        if self.reason:
            raise ValueError("READY_CANNOT_CONTAIN_REVIEW_REASON")
        if not self.groups:
            raise ValueError("READY_GROUP_REQUIRED")
        group_ids = [group.group_id for group in self.groups]
        if len(group_ids) != len(set(group_ids)):
            raise ValueError("DUPLICATE_GROUP_ID")
        for group in self.groups:
            group_assignments = [
                assignment
                for assignment in self.assignments
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
            if len(main_values) > 1:
                raise ValueError("ONE_MAIN_VALUE_PER_GROUP_REQUIRED")
            if not any(
                anchor.role
                in {NumericRole.MAIN_VALUE, NumericRole.CHANGE_VALUE}
                for anchor in anchors
            ):
                raise ValueError("GROUP_MAIN_MENTION_MISMATCH")
            if main_values and main_values[0].mention_id != group.main_mention_id:
                raise ValueError("GROUP_MAIN_MENTION_MISMATCH")
        return self
