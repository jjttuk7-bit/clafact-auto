"""Deterministic numeric-target discovery for multi-Claim Structured Output."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re


from schemas.claim_group import NumericMention

_NUMBER = r"[+\-\u2212]?\d+(?:,\d{3})*(?:\.\d+)?(?:\s*(?:\uc870|\uc5b5|\ub9cc|\ucc9c|\ubc31)\s*\d*(?:,\d{3})*)*"
_UNIT = r"(?:%\ud3ec\uc778\ud2b8|\uff05\ud3ec\uc778\ud2b8|\ud37c\uc13c\ud2b8\ud3ec\uc778\ud2b8|%p|\uff05p|%|\uff05|\u33ca|ha|km\u00b2|\u33a1|\ucc9c\uba85|\ub9cc\uba85|\uba85|\ub300|\uac00\uad6c|\uac74|\ud638|\uac1c|\ucc44|\uacf3|\uc810|\ubc30|\uc704|\ub9cc\ud1a4|\ucc9c\ud1a4|\ud1a4|t|kg|\uc5b5\ub2ec\ub7ec|\ub9cc\ub2ec\ub7ec|\ub2ec\ub7ec|\uc870\uc6d0|\uc5b5\uc6d0|\ub9cc\uc6d0|\uc6d0|\uc5d4|\uc720\ub85c|\ub9ac\ud130|kWh|MW|GW|L)"
_STATISTIC = re.compile(rf"(?<![\d.])(?P<expression>{_NUMBER}\s*{_UNIT})", re.IGNORECASE)
_INDEX_LEVEL = re.compile(
    rf"(?<![\d.])(?P<expression>{_NUMBER}\s*\(\s*\d{{4}}\ub144?\s*[=\uff1d]\s*100\s*\))"
)


@dataclass(frozen=True, slots=True)
class TargetedClaimInput:
    expression: str
    extractor_input: str


def build_targeted_claim_inputs(source_sentence: str) -> list[TargetedClaimInput]:
    """Compatibility wrapper for callers that still request one prompt per number."""
    ordered: list[str] = []
    seen: set[str] = set()
    for mention in discover_numeric_mentions(source_sentence):
        if mention.expression not in seen:
            seen.add(mention.expression)
            ordered.append(mention.expression)
    if len(ordered) < 2: return []
    return [TargetedClaimInput(expression, json.dumps({"source_sentence": source_sentence, "target_numeric_expression": expression, "instruction": "\uc774 \uc218\uce58 \ud558\ub098\ub9cc \ub3c5\ub9bd Claim\uc73c\ub85c 12\uc2ac\ub86f \uad6c\uc870\ud654"}, ensure_ascii=False)) for expression in ordered]


def discover_numeric_mentions(source_sentence: str) -> list[NumericMention]:
    """Find grounded numeric spans without deciding how many Claims they represent."""

    found: list[tuple[int, int, str]] = []
    for pattern in (_STATISTIC, _INDEX_LEVEL):
        for match in pattern.finditer(source_sentence):
            start = match.start("expression")
            end = match.end("expression")
            expression = match.group("expression").replace(" ", "")
            if _looks_like_age_group(source_sentence, end, expression):
                continue
            found.append((start, end, expression))
    mentions: list[NumericMention] = []
    seen_spans: set[tuple[int, int]] = set()
    for start, end, expression in sorted(found):
        if (start, end) in seen_spans:
            continue
        seen_spans.add((start, end))
        mentions.append(NumericMention(
            mention_id=f"n{len(mentions) + 1}",
            expression=expression,
            start=start,
            end=end,
        ))
    return mentions


def _looks_like_age_group(source_sentence: str, end: int, expression: str) -> bool:
    if not re.fullmatch(r"(?:10|20|30|40|50|60|70|80|90)대", expression):
        return False
    following = source_sentence[end:]
    if re.match(
        r"\s*(?:와|과)\s*(?:10|20|30|40|50|60|70|80|90)대", following
    ):
        return True
    return bool(re.match(
        r"\s*(?:는|가|의|에서|중|에게|를|도|부터|까지)?\s*"
        r"(?:청년|남성|여성|인구|취업자|실업자|쉬었음|연령|세대|사람)",
        following,
    ))
