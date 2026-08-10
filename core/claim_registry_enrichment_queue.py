"""Create explicit, non-generative work queues for ClaimSchema slot completion."""

from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Any

_REQUIRED_VERIFICATION_SLOTS = (
    "indicator",
    "value",
    "unit",
    "time",
    "comparison",
    "calculation",
)


def build_enrichment_queue(
    records: Iterable[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Classify records that need structured reparse or semantic slot completion."""
    queue: list[dict[str, Any]] = []
    total_records = 0
    for record in records:
        total_records += 1
        claim = record["claim"]
        missing_slots = [
            slot for slot in _REQUIRED_VERIFICATION_SLOTS if claim.get(slot) is None
        ]
        parse_status = claim.get("parse_status")
        if parse_status != "AUTO_OK":
            work_type = "STRUCTURED_REPARSE_OR_REVIEW"
        elif missing_slots:
            work_type = "SEMANTIC_SLOT_ENRICHMENT"
        else:
            continue
        queue.append(
            {
                "article_id": str(record["article_id"]),
                "sentence_id": str(record["sentence_id"]),
                "parse_status": parse_status,
                "work_type": work_type,
                "missing_slots": missing_slots,
            }
        )

    return queue, {
        "total_records": total_records,
        "queued_records": len(queue),
        "work_type_counts": dict(
            sorted(Counter(item["work_type"] for item in queue).items())
        ),
    }
