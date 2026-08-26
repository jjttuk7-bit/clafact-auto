"""Deterministic inventory of every numeric expression in a source sentence."""

from __future__ import annotations

from dataclasses import dataclass
import re


_BASE = r"\d+(?:,\d{3})*(?:\.\d+)?"
_SCALED = rf"{_BASE}(?:\s*(?:조|억|만|천|백)\s*(?:{_BASE})?)*"
_UNIT = (
    r"(?:퍼센트포인트|%포인트|％포인트|%p|％p|퍼센트|%|％|"
    r"개년|년째|년|개월|월|일|분기|주|시간|분|초|세|"
    r"천명|만명|명|가구|건|호|개국|개사|개|채널|채|곳|회|차례|번째|"
    r"만톤|천톤|톤|t|kg|㎏|"
    r"억달러|만달러|달러|조원|억원|만원|원|엔|유로|"
    r"km²|㎢|㎡|ha|헥타르|km|㎞|리터|kWh|MW|GW|L|"
    r"포인트|배|위|점|대)"
)

_DATE = re.compile(r"(?<!\d)\d{4}[-./]\d{1,2}[-./]\d{1,2}(?!\d)")
_RANGE = re.compile(
    rf"(?<!\d)[+\-−]?{_SCALED}\s*(?:~|∼|～|–|—)\s*[+\-−]?{_SCALED}(?:\s*{_UNIT})?(?!\d)",
    re.IGNORECASE,
)
_TRUNCATED = re.compile(rf"(?<!\d)[+\-−]?{_SCALED}\.{{2,}}", re.IGNORECASE)
_MALFORMED_PERCENT = re.compile(rf"(?<!\d)[+\-−]?{_SCALED}\.(?:%|％)", re.IGNORECASE)
_NUMBER = re.compile(
    rf"(?<!\d)[+\-−]?{_SCALED}(?:\s*{_UNIT})?(?!\d)",
    re.IGNORECASE,
)
_LEXICAL = re.compile(
    r"(?<![가-힣])(?:한|두|세|네|석|열|스무)\s*(?:달|해|년|개월|주|시간|명|개|대|배|곳|건|차례|번째)(?![가-힣])|절반"
)


@dataclass(frozen=True, slots=True)
class SourceNumericMention:
    mention_id: str
    expression: str
    start: int
    end: int
    context: str
    role_status: str = "미분류"


def inventory_numeric_mentions(source_sentence: str) -> list[SourceNumericMention]:
    """Return non-overlapping numeric spans in source order without assigning roles."""

    candidates: list[tuple[int, int, int]] = []
    patterns = (_DATE, _RANGE, _TRUNCATED, _MALFORMED_PERCENT, _NUMBER, _LEXICAL)
    for priority, pattern in enumerate(patterns):
        candidates.extend((match.start(), match.end(), priority) for match in pattern.finditer(source_sentence))

    selected: list[tuple[int, int]] = []
    for start, end, _priority in sorted(candidates, key=lambda item: (item[0], -(item[1] - item[0]), item[2])):
        if any(start < chosen_end and end > chosen_start for chosen_start, chosen_end in selected):
            continue
        selected.append((start, end))
    selected.sort()

    mentions: list[SourceNumericMention] = []
    for index, (start, end) in enumerate(selected, start=1):
        context_start = max(0, start - 24)
        context_end = min(len(source_sentence), end + 24)
        mentions.append(
            SourceNumericMention(
                mention_id=f"n{index}",
                expression=source_sentence[start:end],
                start=start,
                end=end,
                context=source_sentence[context_start:context_end],
            )
        )
    return mentions


def digit_positions_not_covered(
    source_sentence: str,
    mentions: list[SourceNumericMention],
) -> list[int]:
    """Return digit indexes that are outside every inventoried mention."""

    covered = {
        index
        for mention in mentions
        for index in range(mention.start, mention.end)
    }
    return [index for index, character in enumerate(source_sentence) if character.isdigit() and index not in covered]
