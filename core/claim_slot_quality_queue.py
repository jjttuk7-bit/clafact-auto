"""Build deterministic reparse work items from slot-quality HOLD results."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def build_slot_quality_reparse_queue(
    results: Iterable[Mapping[str, Any]],
) -> list[dict[str, str | None]]:
    """Return only Claims held by the deterministic slot-quality gate."""
    queue: list[dict[str, str | None]] = []
    for result in results:
        quality = result.get("slot_quality")
        if result.get("reason_code") != "CLAIM_PARSE_UNCERTAIN" or not isinstance(quality, Mapping):
            continue
        queue.append({
            "claim_id": _text(result.get("claim_id")),
            "source_sentence": _text(result.get("source_sentence")),
            "reason_code": _text(quality.get("reason_code")),
            "detected_modifier": _text(quality.get("detected_modifier")),
        })
    return queue


def _text(value: object) -> str | None:
    return value if isinstance(value, str) else None
