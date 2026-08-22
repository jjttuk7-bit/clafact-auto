"""Inspect every semantic Claim slot before official lookup."""

from __future__ import annotations

import re
from typing import Mapping

from schemas.claim import ClaimSchema
from schemas.slot_audit import (
    SlotAuditEntrySchema,
    SlotAuditSchema,
    SlotName,
    SlotValueStatus,
)


SLOT_ORDER: tuple[SlotName, ...] = (
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
)

_COMMON_REQUIRED: set[SlotName] = {
    "indicator",
    "value",
    "unit",
    "time",
    "calculation",
}


def audit_claim_slots(
    claim: ClaimSchema,
    *,
    provenance: Mapping[str, SlotValueStatus] | None = None,
) -> SlotAuditSchema:
    """Return twelve entries and stable reasons without mutating the Claim."""

    provenance = provenance or {}
    required = _required_slots(claim.calculation)
    entries: list[SlotAuditEntrySchema] = []
    for slot in SLOT_ORDER:
        value = getattr(claim, slot)
        status = provenance.get(slot)
        if status is None:
            if _is_missing(value):
                inferred = _infer_frequency(claim.time) if slot == "frequency" else None
                if inferred is not None:
                    value = inferred
                    status = "NORMALIZED"
                else:
                    status = "MISSING" if slot in required else "NOT_APPLICABLE"
            else:
                status = "SOURCE"
        entries.append(
            SlotAuditEntrySchema(
                slot=slot,
                value=value,
                status=status,
                required=slot in required,
            )
        )

    conflicts = [entry.slot for entry in entries if entry.status == "CONFLICT"]
    missing = [
        entry.slot
        for entry in entries
        if entry.required and entry.status == "MISSING"
    ]
    reasons = tuple(
        [f"SLOT_CONFLICT:{slot}" for slot in conflicts]
        + ([f"MISSING_REQUIRED_SLOTS:{','.join(missing)}"] if missing else [])
    )
    return SlotAuditSchema(
        entries=tuple(entries),
        eligible_for_official_search=not conflicts and not missing,
        reason_codes=reasons,
    )


def _required_slots(calculation: str | None) -> set[SlotName]:
    required = set(_COMMON_REQUIRED)
    kind = str(calculation or "").strip().upper()
    if kind in {"GROWTH_RATE", "DIFFERENCE"}:
        required.update(("comparison", "condition"))
    elif kind in {"SHARE", "RATIO", "MULTIPLE"}:
        required.add("comparison")
    elif kind == "RANK":
        required.update(("dimension", "condition"))
    elif kind == "THRESHOLD":
        required.add("condition")
    return required


def _is_missing(value: object) -> bool:
    return value is None or value == "" or value == {} or value == []


def _infer_frequency(time_value: str | None) -> str | None:
    if not time_value:
        return None
    compact = time_value.replace(" ", "")
    if re.search(r"\d{4}년\d{1,2}월", compact):
        return "월"
    if re.search(r"\d{4}년(?:[1-4]분기|상반기|하반기)", compact):
        return "분기" if "분기" in compact else "반기"
    if re.fullmatch(r"\d{4}년?", compact):
        return "년"
    return None
