"""Deterministic human-review queue for ambiguous comparison claims."""

from copy import deepcopy
from typing import Any, Iterable


def build_review_queue(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return only claims explicitly held for ambiguous comparison."""
    queue: list[dict[str, Any]] = []
    for record in records:
        claim = record.get("claim", {})
        if claim.get("parse_reason") != "AMBIGUOUS_COMPARISON":
            continue
        queue.append({"source_key": _source_key(record), "source_sentence": claim.get("source_sentence"), "comparison": claim.get("comparison"), "calculation": claim.get("calculation"), "missing_fields": ["comparison", "calculation"]})
    return queue


def apply_review_decisions(records: Iterable[dict[str, Any]], decisions: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply explicit approved decisions into a new stream; never mutate input."""
    indexed = {_source_key(record): record for record in records}
    decision_map: dict[str, dict[str, Any]] = {}
    for decision in decisions:
        key = decision.get("source_key")
        if key not in indexed:
            raise ValueError("Unknown review source key")
        if key in decision_map:
            raise ValueError("Duplicate review decision")
        if decision.get("status") not in {"APPROVED", "REJECTED"}:
            raise ValueError("Invalid review decision status")
        if decision["status"] == "APPROVED" and (not decision.get("comparison") or not decision.get("calculation")):
            raise ValueError("Approved decision requires comparison and calculation")
        decision_map[key] = decision
    result = deepcopy(list(indexed.values()))
    for record in result:
        decision = decision_map.get(_source_key(record))
        if decision and decision["status"] == "APPROVED":
            claim = record["claim"]
            claim["comparison"] = decision["comparison"]
            claim["calculation"] = decision["calculation"]
            claim["parse_status"] = "AUTO_OK"
            claim["parse_reason"] = None
    return result


def _source_key(record: dict[str, Any]) -> str:
    return f"{record['article_id']}:{record['sentence_id']}"
