"""Deterministic numeric-target discovery for multi-Claim Structured Output."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re


from schemas.claim_group import NumericMention

_NUMBER = r"[+\-\u2212]?\d+(?:,\d{3})*(?:\.\d+)?(?:\s*(?:조|억|만|천|백)\s*\d*(?:,\d{3})*)*"
_UNIT = r"(?:%포인트|％포인트|퍼센트포인트|%p|％p|%|％|㏊|ha|km²|㎡|천명|만명|명|대|가구|건|호|개(?!월)|채|곳|점|배|위|만톤|천톤|톤|t|kg|억달러|만달러|달러|조원|억원|만원|원|엔|유로|리터|kWh|MW|GW|L)"
_STATISTIC = re.compile(rf"(?<![\d.])(?P<expression>{_NUMBER}\s*{_UNIT})", re.IGNORECASE)
_INDEX_LEVEL = re.compile(
    rf"(?<![\d.])(?P<expression>{_NUMBER}\s*\(\s*\d{{4}}년?\s*[=＝]\s*100\s*\))"
)
_PLAIN_INDEX_LEVEL = re.compile(
    r"(?<![\d.])(?P<expression>[+\-\u2212]?\d{2,3}\.\d+)(?![\d%％])"
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
    if len(ordered) < 2:
        return []
    return [
        TargetedClaimInput(
            expression,
            json.dumps(
                {
                    "source_sentence": source_sentence,
                    "target_numeric_expression": expression,
                    "instruction": "이 수치 하나만 독립 Claim으로 12슬롯 구조화",
                },
                ensure_ascii=False,
            ),
        )
        for expression in ordered
    ]


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
    for match in _PLAIN_INDEX_LEVEL.finditer(source_sentence):
        start = match.start("expression")
        end = match.end("expression")
        if any(
            start >= prior_start and end <= prior_end
            for prior_start, prior_end, _ in found
        ):
            continue
        prefix = source_sentence[max(0, start - 32):start]
        if "지수" not in prefix:
            continue
        found.append((start, end, match.group("expression")))
    mentions: list[NumericMention] = []
    seen_spans: set[tuple[int, int]] = set()
    for start, end, expression in sorted(found):
        if (start, end) in seen_spans:
            continue
        seen_spans.add((start, end))
        mentions.append(
            NumericMention(
                mention_id=f"n{len(mentions) + 1}",
                expression=expression,
                start=start,
                end=end,
            )
        )
    return mentions


def _looks_like_age_group(source_sentence: str, end: int, expression: str) -> bool:
    if not re.fullmatch(r"(?:10|20|30|40|50|60|70|80|90)대", expression):
        return False
    following = source_sentence[end:]
    if re.match(
        r"\s*(?:와|과)\s*(?:10|20|30|40|50|60|70|80|90)대", following
    ):
        return True
    return bool(
        re.match(
            r"\s*(?:는|가|의|에서|중|에게|를|도|부터|까지)?\s*"
            r"(?:청년|남성|여성|인구|취업자|실업자|쉬었음|연령|세대|사람)",
            following,
        )
    )
