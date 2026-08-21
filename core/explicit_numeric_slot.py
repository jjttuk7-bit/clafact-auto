"""Conservative extraction of one explicit numeric claim value."""
from __future__ import annotations
import re

_TOKEN = re.compile(r"(?P<n>\d+(?:[,.]\d+)?)(?:(?P<scale>만|억|천)(?P<tail>\d+(?:[,.]\d+)?)?)?(?P<u>%|%p|명|원|건|배|ha|㏊)")

def extract_explicit_numeric_slot(sentence: str) -> tuple[float, str, str] | None:
    tokens = list(_TOKEN.finditer(sentence))
    if not tokens:
        return None
    token = tokens[-1] if '%' in tokens[-1].group('u') else tokens[0]
    value = float(token.group('n').replace(',', ''))
    scale = token.group('scale')
    if scale == '만': value = value * 10_000 + float(token.group('tail') or 0)
    elif scale == '천': value *= 1_000
    elif scale == '억': value *= 100_000_000
    unit = 'ha' if token.group('u') == '㏊' else token.group('u')
    if unit in {'%', '%p'} and any(word in sentence for word in ('전년', '전월', '작년', '대비', '보다')):
        calculation = 'GROWTH_RATE'
    elif any(word in sentence for word in ('증가', '감소', '늘었', '줄었')):
        calculation = 'DIFFERENCE'
    else:
        calculation = 'DIRECT_VALUE'
    return value, unit, calculation