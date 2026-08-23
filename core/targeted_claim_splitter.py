"""Deterministic numeric-target discovery for multi-Claim Structured Output."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re


_NUMBER = r"\d+(?:,\d{3})*(?:\.\d+)?(?:\uc870|\uc5b5|\ub9cc|\ucc9c)?\d*(?:,\d{3})*"
_UNIT = r"(?:%\ud3ec\uc778\ud2b8|\ud37c\uc13c\ud2b8\ud3ec\uc778\ud2b8|%p|%|\u33ca|ha|km\u00b2|\u33a1|\ucc9c\uba85|\ub9cc\uba85|\uba85|\uac00\uad6c|\uac74|\ud638|\uac1c|\ucc44|\uacf3|\uc810|\ubc30|\uc704|\ub9cc\ud1a4|\ucc9c\ud1a4|\ud1a4|t|kg|\uc5b5\ub2ec\ub7ec|\ub9cc\ub2ec\ub7ec|\ub2ec\ub7ec|\uc870\uc6d0|\uc5b5\uc6d0|\ub9cc\uc6d0|\uc6d0|\uc5d4|\uc720\ub85c|\ub9ac\ud130|kWh|MW|GW|L)"
_STATISTIC = re.compile(rf"(?<![\d.])(?P<expression>{_NUMBER}\s*{_UNIT})", re.IGNORECASE)
_INDEX_LEVEL = re.compile(
    rf"(?<![\d.])(?P<expression>{_NUMBER}\s*\(\s*\d{{4}}\ub144?\s*[=\uff1d]\s*100\s*\))"
)


@dataclass(frozen=True, slots=True)
class TargetedClaimInput:
    expression: str
    extractor_input: str


def build_targeted_claim_inputs(source_sentence: str) -> list[TargetedClaimInput]:
    """Return ordered target prompts only when a sentence contains multiple statistics."""
    found = [(match.start("expression"), match.group("expression").replace(" ", "")) for pattern in (_STATISTIC, _INDEX_LEVEL) for match in pattern.finditer(source_sentence)]
    ordered, seen = [], set()
    for _, expression in sorted(found):
        if expression not in seen: seen.add(expression); ordered.append(expression)
    if len(ordered) < 2: return []
    return [TargetedClaimInput(expression, json.dumps({"source_sentence": source_sentence, "target_numeric_expression": expression, "instruction": "\uc774 \uc218\uce58 \ud558\ub098\ub9cc \ub3c5\ub9bd Claim\uc73c\ub85c 12\uc2ac\ub86f \uad6c\uc870\ud654"}, ensure_ascii=False)) for expression in ordered]
