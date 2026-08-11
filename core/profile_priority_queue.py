"""Build deterministic review queues for unregistered verification profiles."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

_REQUIRED_KOSIS_METADATA = ["TABLE", "ITEM", "DIMENSIONS", "UNIT", "PUBLICATION_POLICY"]
_CORE_SLOTS = ("indicator", "calculation", "frequency", "time", "unit")


def build_profile_priority_queue(
    e2e_rows: Iterable[Mapping[str, Any]], derived_rows: Iterable[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Group PROFILE_NOT_FOUND records into auditable KOSIS research priorities."""
    derived_by_key = {
        (str(row["article_id"]), str(row["sentence_id"])): row
        for row in derived_rows
    }
    groups: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for result in e2e_rows:
        if result.get("reason_code") != "PROFILE_NOT_FOUND":
            continue
        key = (str(result["article_id"]), str(result["sentence_id"]))
        row = derived_by_key.get(key)
        if row is None:
            continue
        claim = row["claim"]
        group_key = (
            str(claim.get("indicator") or "UNRESOLVED"),
            str(claim.get("calculation") or "UNRESOLVED"),
            str(claim.get("frequency") or "UNRESOLVED"),
        )
        groups[group_key].append(claim)

    queue: list[dict[str, Any]] = []
    for (indicator, calculation, frequency), claims in groups.items():
        missing_slots = sorted(
            {slot for claim in claims for slot in _CORE_SLOTS if claim.get(slot) is None}
        )
        queue.append(
            {
                "indicator": indicator,
                "calculation": calculation,
                "frequency": frequency,
                "claim_count": len(claims),
                "claim_ids": sorted(str(claim["claim_id"]) for claim in claims),
                "unresolved_claim_slots": missing_slots,
                "required_kosis_metadata": list(_REQUIRED_KOSIS_METADATA),
            }
        )

    queue.sort(key=lambda row: (-int(row["claim_count"]), row["indicator"], row["calculation"], row["frequency"]))
    for rank, row in enumerate(queue, start=1):
        row["priority_rank"] = rank
    return queue
