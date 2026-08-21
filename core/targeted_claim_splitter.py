"""Deterministic numeric-target discovery for multi-Claim Structured Output."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re


_NUMBER = r"\d+(?:,\d{3})*(?:\.\d+)?(?:조|억|만|천)?\d*(?:,\d{3})*"
_UNIT = r"(?:%포인트|퍼센트포인트|%p|%|㏊|ha|km²|㎡|천명|만명|명|가구|건|호|개|채|곳|점|배|위|만톤|천톤|톤|t|kg|억달러|만달러|달러|조원|억원|만원|원|엔|유로|리터|kWh|MW|GW|L)"
_STATISTIC = re.compile(rf"(?<![\d.])(?P<expression>{_NUMBER}\s*{_UNIT})", re.IGNORECASE)
_INDEX_LEVEL = re.compile(rf"(?<![\d.])(?P<expression>{_NUMBER})(?=\s*\(\s*\d{{4}}년\s*=\s*100\s*\))")


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
    return [TargetedClaimInput(expression, json.dumps({"source_sentence": source_sentence, "target_numeric_expression": expression, "instruction": "이 수치 하나만 독립 Claim으로 12슬롯 구조화"}, ensure_ascii=False)) for expression in ordered]
