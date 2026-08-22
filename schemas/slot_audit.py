"""Auditable status for all twelve semantic Claim slots."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


SlotName = Literal[
    "indicator",
    "value",
    "unit",
    "time",
    "frequency",
    "region",
    "population",
    "dimension",
    "comparison",
    "calculation",
    "condition",
    "source_hint",
]

SlotValueStatus = Literal[
    "SOURCE",
    "CONTEXT",
    "NORMALIZED",
    "MISSING",
    "CONFLICT",
    "NOT_APPLICABLE",
]


class SlotAuditEntrySchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    slot: SlotName
    value: Any | None = None
    status: SlotValueStatus
    required: bool


class SlotAuditSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    entries: tuple[SlotAuditEntrySchema, ...]
    eligible_for_official_search: bool
    reason_codes: tuple[str, ...] = ()

    def by_slot(self, slot: SlotName) -> SlotAuditEntrySchema:
        for entry in self.entries:
            if entry.slot == slot:
                return entry
        raise KeyError(slot)
