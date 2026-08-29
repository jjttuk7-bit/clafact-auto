"""Fail-closed deterministic roles for inventoried source numbers."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re

from core.source_numeric_inventory import SourceNumericMention


_ROLE_CODE = {
    "대상값": "MAIN_VALUE",
    "증감값": "CHANGE_VALUE",
    "비교값": "REFERENCE_VALUE",
    "환산값": "EQUIVALENT_VALUE",
    "기간": "PERIOD",
    "기준연도": "BASE_YEAR",
    "기준값": "BASE_VALUE",
    "연령": "AGE_GROUP",
    "순위": "RANK",
    "맥락값": "CONTEXT_VALUE",
    "제외": "EXCLUDED",
}
_PROTECTED_ROLES = {"기간", "기준연도", "기준값", "연령", "순위", "환산값", "제외"}
_CURRENCY_UNITS = {"원", "달러", "엔", "유로"}
_CHANGE_TERMS = ("증가", "감소", "늘", "줄", "상승", "하락", "오르", "내리", "확대", "축소", "급증", "급감")
_AGE_SUBJECTS = ("인구", "취업자", "실업자", "근로자", "청년", "남성", "여성", "연령", "세대", "사람")
_NUMBER = re.compile(r"[+\-−]?\d+(?:,\d{3})*(?:\.\d+)?(?:(?:조|억|만|천|백)\d*(?:,\d{3})*(?:\.\d+)?)*(?:조|억|만|천|백)?")
_SCALES = {"조": 1e12, "억": 1e8, "만": 1e4, "천": 1e3, "백": 1e2}


@dataclass(frozen=True, slots=True)
class NumericRoleAssignment:
    mention_id: str
    expression: str
    role: str
    role_code: str
    reason_code: str
    reason_easy: str
    auto_target_eligible: bool
    exclusion_reason: str
    confidence: str
    normalized_values: tuple[float, ...]
    detected_unit: str


@dataclass(frozen=True, slots=True)
class NumericRoleClassification:
    assignments: tuple[NumericRoleAssignment, ...]
    target_status: str


def classify_numeric_roles(
    *,
    source_sentence: str,
    mentions: list[SourceNumericMention],
    claim_value: float | None,
    claim_unit: str,
    indicator: str,
) -> NumericRoleClassification:
    prepared = [(_numeric_values(m.expression), _detected_unit_in_context(source_sentence, m, indicator)) for m in mentions]
    preliminary: dict[int, tuple[str, str, str, str]] = {}

    for index, mention in enumerate(mentions):
        expression = mention.expression
        before = source_sentence[max(0, mention.start - 16):mention.start]
        after = source_sentence[mention.end:min(len(source_sentence), mention.end + 20)]
        unit = prepared[index][1]
        if "..." in expression or ".%" in expression or ".％" in expression:
            preliminary[index] = ("제외", "SOURCE_TEXT_MALFORMED", "원문이 잘리거나 숫자 표기가 깨져 자동 검증에 사용할 수 없음", "HIGH")
        elif _is_model_or_ordinal(expression, before, after):
            preliminary[index] = ("제외", "MODEL_OR_ORDINAL_CONTEXT", "제품명·기수·서수에 포함된 맥락 숫자", "HIGH")
        elif re.fullmatch(r"\d{4}년", expression.replace(" ", "")) and re.match(r"\s*[=＝]\s*100", after):
            preliminary[index] = ("기준연도", "INDEX_BASE_YEAR", "지수의 기준연도", "HIGH")
        elif expression.replace(" ", "") == "100" and re.search(r"\d{4}년?\s*[=＝]\s*$", before):
            preliminary[index] = ("기준값", "INDEX_BASE_VALUE", "지수 기준값 100", "HIGH")
        elif _is_age_group(expression, before, after):
            preliminary[index] = ("연령", "AGE_GROUP_CONTEXT", "연령대를 나타내는 숫자", "HIGH")
        elif unit == "위" or re.search(r"(?:상위|하위|순위)\s*$", before):
            preliminary[index] = ("순위", "RANK_CONTEXT", "순위 또는 상·하위 범위를 나타내는 숫자", "HIGH")
        elif re.search(r"\d{4}년\s*\(\s*$", before) and re.match(r"\s*\)\s*(?:의|보다|대비)", after):
            preliminary[index] = ("비교값", "PARENTHETICAL_HISTORICAL_REFERENCE", "연도 뒤 괄호에 제시된 과거 비교값", "HIGH")
        elif unit in {"년", "월", "일", "분기", "개월", "달", "주", "시간"}:
            preliminary[index] = ("기간", "PERIOD_CONTEXT", "기준시점 또는 지속기간을 나타내는 숫자", "HIGH")

    for index, mention in enumerate(mentions):
        if index in preliminary:
            continue
        unit = prepared[index][1]
        before = source_sentence[max(0, mention.start - 8):mention.start]
        if unit in _CURRENCY_UNITS and re.search(r"(?:\(|약\s*|한화\s*|환산\s*)$", before):
            earlier_currency = any(prepared[other][1] in _CURRENCY_UNITS for other in range(index))
            if earlier_currency:
                preliminary[index] = ("환산값", "CURRENCY_EQUIVALENT", "앞선 금액을 다른 통화로 환산한 값", "HIGH")

    expected_value, expected_unit = _claim_base_value(claim_value, claim_unit)
    matching_all = [
        index
        for index, (values, unit) in enumerate(prepared)
        if expected_value is not None
        and _units_compatible(unit, expected_unit)
        and any(_numbers_equal(abs(value), abs(expected_value)) for value in values)
    ]
    eligible_matches = [index for index in matching_all if index not in preliminary]
    selected: int | None = None
    target_status = "NO_TARGET_MATCH"
    if eligible_matches:
        scored = [(index, _indicator_score(source_sentence, mentions[index], indicator)) for index in eligible_matches]
        best_score = max(score for _, score in scored)
        best = [index for index, score in scored if score == best_score]
        if len(best) == 1:
            selected = best[0]
            target_status = "TARGET_SELECTED"
        else:
            target_status = "AMBIGUOUS_TARGET_MATCH"
    elif matching_all:
        target_status = "TARGET_BLOCKED_BY_CONTEXT_ROLE"

    assignments: list[NumericRoleAssignment] = []
    for index, mention in enumerate(mentions):
        values, unit = prepared[index]
        if index in preliminary:
            role, reason, easy, confidence = preliminary[index]
            assignments.append(_assignment(mention, role, reason, easy, False, reason, confidence, values, unit))
            continue
        if index == selected:
            if _has_change_predicate(source_sentence, mention):
                assignments.append(_assignment(mention, "증감값", "SOURCE_GROUNDED_CHANGE", "증가·감소 문법에 직접 연결된 기사 수치", True, "", "HIGH", values, unit))
            else:
                assignments.append(_assignment(mention, "대상값", "SOURCE_GROUNDED_MAIN", "저장 기사값·단위와 원문 표현이 일치함", True, "", "HIGH", values, unit))
            continue
        if index in eligible_matches:
            reason = "AMBIGUOUS_TARGET_MATCH" if selected is None else "OTHER_SAME_VALUE_MENTION"
            assignments.append(_assignment(mention, "맥락값", reason, "같은 값 후보가 여러 개이거나 다른 지표의 값", False, reason, "LOW", values, unit))
        elif _is_reference_context(source_sentence, mention):
            assignments.append(_assignment(mention, "비교값", "REFERENCE_CONTEXT", "이전·당초·비교 기준으로 제시된 값", False, "REFERENCE_VALUE_NOT_AUTO_TARGET", "MEDIUM", values, unit))
        elif _has_change_predicate(source_sentence, mention):
            assignments.append(_assignment(mention, "증감값", "OTHER_CHANGE_CONTEXT", "증가·감소 문법에 연결됐지만 현재 저장 기사값과 다름", False, "OTHER_CLAIM_CHANGE_VALUE", "MEDIUM", values, unit))
        else:
            assignments.append(_assignment(mention, "맥락값", "NOT_SELECTED_AS_TARGET", "현재 Claim의 자동 대상값으로 확정되지 않은 맥락 수치", False, "NOT_SELECTED_AS_TARGET", "MEDIUM", values, unit))
    return NumericRoleClassification(assignments=tuple(assignments), target_status=target_status)


def _assignment(mention: SourceNumericMention, role: str, reason: str, easy: str, eligible: bool, exclusion: str, confidence: str, values: tuple[float, ...], unit: str) -> NumericRoleAssignment:
    return NumericRoleAssignment(mention.mention_id, mention.expression, role, _ROLE_CODE[role], reason, easy, eligible, exclusion, confidence, values, unit)


def _numeric_values(expression: str) -> tuple[float, ...]:
    parts = re.split(r"[~∼～–—]", expression.replace(" ", ""))
    values: list[float] = []
    for part in parts:
        match = _NUMBER.search(part.replace("−", "-"))
        if match:
            values.append(_parse_scaled_number(match.group()))
    return tuple(values)


def _parse_scaled_number(raw: str) -> float:
    compact = raw.replace(",", "").replace("−", "-")
    sign = -1.0 if compact.startswith("-") else 1.0
    compact = compact.lstrip("+-")
    if not any(marker in compact for marker in _SCALES):
        return sign * float(compact)
    total = 0.0
    remainder = compact
    for marker, scale in (("조", 1e12), ("억", 1e8), ("만", 1e4), ("천", 1e3), ("백", 1e2)):
        if marker in remainder:
            group, remainder = remainder.split(marker, 1)
            total += (float(group) if group else 1.0) * scale
    total += float(remainder) if remainder else 0.0
    return sign * total



def _detected_unit_in_context(source: str, mention: SourceNumericMention, indicator: str = "") -> str:
    unit = _detected_unit(mention.expression)
    if unit:
        return unit
    after = source[mention.end:min(len(source), mention.end + 30)]
    if re.match(r"\s*\(\s*\d{4}년?\s*[=＝]\s*100\s*\)", after):
        return "index"
    before = re.sub(r"\s+", "", source[max(0, mention.start - 40):mention.start])
    compact_indicator = re.sub(r"\s+", "", indicator or "")
    if "지수" in compact_indicator and re.search(
        re.escape(compact_indicator) + r"(?:는|은|이|가|:)$", before
    ):
        return "index"
    return ""

def _detected_unit(expression: str) -> str:
    compact = expression.replace(" ", "").casefold()
    if re.search(r"\(\d{4}년?\s*[=＝]\s*100\)", compact):
        return "index"
    aliases = (("%포인트", "%p"), ("％포인트", "%p"), ("퍼센트포인트", "%p"), ("%p", "%p"), ("％p", "%p"), ("%", "%"), ("％", "%"), ("달러", "달러"), ("유로", "유로"), ("억원", "원"), ("만원", "원"), ("조원", "원"), ("원", "원"), ("천명", "명"), ("만명", "명"), ("명", "명"), ("개월", "개월"), ("분기", "분기"), ("가구", "가구"), ("채널", "개"), ("곳", "곳"), ("개", "개"), ("대", "대"), ("년", "년"), ("월", "월"), ("일", "일"), ("달", "달"), ("주", "주"), ("시간", "시간"), ("위", "위"), ("배", "배"), ("호", "호"), ("건", "건"), ("톤", "톤"), ("t", "t"), ("ha", "ha"), ("엔", "엔"))
    for suffix, unit in aliases:
        if compact.endswith(suffix):
            return unit
    return ""


def _claim_base_value(value: float | None, unit: str) -> tuple[float | None, str]:
    if value is None:
        return None, ""
    compact = (unit or "").replace(" ", "").casefold()
    if compact.startswith("지수"):
        return float(value), "index"
    if compact in {"billionusd", "billiondollars", "십억usd"}:
        return float(value) * 1e9, "달러"
    if "/" in compact:
        compact = compact.split("/", 1)[0]
    aliases = {"%포인트": "%p", "퍼센트포인트": "%p", "%p": "%p", "십억달러": "달러", "천불": "달러", "usd": "달러", "미국달러": "달러"}
    scale = 1.0
    for prefix, factor in (("십억", 1e9), ("조", 1e12), ("억", 1e8), ("만", 1e4), ("천", 1e3)):
        if compact.startswith(prefix) and len(compact) > len(prefix):
            scale = factor
            compact = compact[len(prefix):]
            break
    return float(value) * scale, aliases.get(compact, compact)


def _units_compatible(left: str, right: str) -> bool:
    return bool(left and right and left == right)


def _numbers_equal(left: float, right: float) -> bool:
    return abs(left - right) <= max(1e-9, abs(right) * 1e-9)


def _is_age_group(expression: str, before: str, after: str) -> bool:
    if not re.fullmatch(r"(?:10|20|30|40|50|60|70|80|90)대", expression.replace(" ", "")):
        return False
    subjects = "|".join(_AGE_SUBJECTS)
    return bool(re.match(rf"\s*(?:는|은|이|가|의|에서|중|에게|를|도)?\s*(?:{subjects})", after) or re.search(rf"(?:{subjects})\s*$", before))


def _is_model_or_ordinal(expression: str, before: str, after: str) -> bool:
    if not re.fullmatch(r"\d+(?:\.\d+)?", expression.replace(" ", "")):
        return False
    return bool((before.endswith(".") and before[-2:-1].isalpha()) or re.match(r"\s*(?:맥스|기|세대|호기)", after))


def _indicator_score(source: str, mention: SourceNumericMention, indicator: str) -> int:
    indicator = (indicator or "").strip()
    positions: list[int] = []
    start = 0
    while indicator and (found := source.find(indicator, start)) >= 0:
        positions.append(found)
        start = found + 1
    if not positions:
        return 0
    return 10_000 - min(abs(mention.start - (position + len(indicator))) for position in positions)


def _has_change_predicate(source: str, mention: SourceNumericMention) -> bool:
    tail = source[mention.end:min(len(source), mention.end + 35)]
    positions = [tail.find(term) for term in _CHANGE_TERMS if term in tail]
    if not positions:
        return False
    nearest = min(positions)
    prefix = tail[:nearest]
    if nearest > 20:
        return False
    if re.search(r"\d|[.;]", prefix):
        return False
    if re.search(r"(?:기록한?\s*후|이후|뒤)", prefix):
        return False
    return True


def _is_reference_context(source: str, mention: SourceNumericMention) -> bool:
    context = source[max(0, mention.start - 18):min(len(source), mention.end + 18)]
    return bool(re.search(r"당초|계획|전년|작년|이전|종전|기존|보다|에서", context))
