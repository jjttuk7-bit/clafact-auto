"""Read period-specific values from official release HWPX tables.

The resolver is intentionally independent of Claim IDs and KOSIS table IDs.
It selects a value only from the release table's indicator/dimension labels and
the exact reference-period column, and fails closed when different values fit.
"""

from __future__ import annotations

import io
import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from typing import Iterable

from schemas.claim import ClaimSchema


@dataclass(frozen=True, slots=True)
class OfficialReleaseTable:
    rows: tuple[tuple[str, ...], ...]


def extract_hwpx_tables(raw: bytes) -> list[OfficialReleaseTable]:
    """Return cell-preserving tables from an HWPX package."""
    tables: list[OfficialReleaseTable] = []
    try:
        package = zipfile.ZipFile(io.BytesIO(raw))
    except (OSError, ValueError, zipfile.BadZipFile):
        return tables
    for name in package.namelist():
        if not re.search(r"(?:^|/)section\d+\.xml$", name, re.IGNORECASE):
            continue
        try:
            root = ET.fromstring(package.read(name))
        except (ET.ParseError, KeyError, OSError):
            continue
        for element in root.iter():
            if _local_name(element.tag) != "tbl":
                continue
            rows: list[tuple[str, ...]] = []
            for row in element.iter():
                if _local_name(row.tag) != "tr":
                    continue
                cells = tuple(
                    _clean("".join(cell.itertext()))
                    for cell in row.iter()
                    if _local_name(cell.tag) == "tc"
                )
                if cells:
                    rows.append(cells)
            if rows:
                tables.append(OfficialReleaseTable(tuple(rows)))
    return tables


def resolve_direct_value(
    claim: ClaimSchema,
    tables: Iterable[OfficialReleaseTable],
    *,
    reference_period: str,
) -> float | None:
    """Resolve exactly one official value by table labels and period column."""
    values: set[float] = set()
    for table in tables:
        rows = table.rows
        if not rows:
            continue
        unit = _table_unit(rows)
        scale, family = _unit_scale(unit)
        claim_scale, claim_family = _unit_scale(claim.unit or "")
        if not family or not claim_family or family != claim_family:
            continue
        period_columns = _period_columns(rows, reference_period)
        if not period_columns:
            continue
        title = " ".join(cell for row in rows[:3] for cell in row)
        for row in rows:
            if not row or not _row_matches(claim, title, row[0]):
                continue
            for column in period_columns:
                if column >= len(row):
                    continue
                numeric = _cell_number(row[column])
                if numeric is not None:
                    values.add(numeric * scale / claim_scale)
    return next(iter(values)) if len(values) == 1 else None


def _row_matches(claim: ClaimSchema, title: str, row_label: str) -> bool:
    context = _normalize(title + " " + row_label)
    indicator_terms = _meaningful_terms(claim.indicator or "")
    if indicator_terms and not all(_normalize(term) in context for term in indicator_terms):
        return False

    age = _explicit_age(claim)
    if age is not None and not _age_matches(age, title + " " + row_label):
        return False
    region = _explicit_region(claim.region)
    if region and _normalize(region) not in context:
        return False

    title_has_indicator = bool(indicator_terms) and all(
        _normalize(term) in _normalize(title) for term in indicator_terms
    )
    row_has_indicator = bool(indicator_terms) and all(
        _normalize(term) in _normalize(row_label) for term in indicator_terms
    )
    has_explicit_axis = age is not None or bool(region)
    if row_has_indicator or has_explicit_axis:
        return True
    return title_has_indicator and _is_total(row_label)


def _period_columns(rows: tuple[tuple[str, ...], ...], period: str) -> set[int]:
    target = _period_key(period)
    if target is None:
        return set()
    matches: set[int] = set()
    for row in rows[:8]:
        for index in range(len(row)):
            if re.search(r"20\d{2}", row[index]) is None:
                continue
            fragments = [row[index]]
            for width in (1, 2, 3):
                if index + width <= len(row):
                    key = _period_key(" ".join(fragments))
                    if key == target:
                        matches.add(index)
                if index + width < len(row):
                    fragments.append(row[index + width])
    return matches


def _period_key(value: str) -> str | None:
    text = str(value or "").strip().upper()
    if match := re.search(r"(?P<year>20\d{2})\D{0,4}(?P<month>0?[1-9]|1[0-2])(?:\D|$)", text):
        return f"{match.group('year')}-{int(match.group('month')):02d}"
    if match := re.search(r"(?P<year>20\d{2})\D{0,4}(?P<quarter>[1-4])\s*(?:/\s*4|Q|분기)", text):
        return f"{match.group('year')}-Q{match.group('quarter')}"
    if match := re.fullmatch(r"\D*(20\d{2})\D*", text):
        return match.group(1)
    return None


def _table_unit(rows: tuple[tuple[str, ...], ...]) -> str:
    for row in rows[:5]:
        for cell in row:
            if "단위" in cell:
                return cell
    return ""


def _unit_scale(value: str) -> tuple[float, str]:
    compact = _normalize(value)
    aliases = (
        ("십억달러", 1e9, "달러"), ("억달러", 1e8, "달러"),
        ("만달러", 1e4, "달러"), ("천불", 1e3, "달러"), ("달러", 1.0, "달러"),
        ("조원", 1e12, "원"), ("억원", 1e8, "원"), ("만원", 1e4, "원"),
        ("천원", 1e3, "원"), ("원", 1.0, "원"),
        ("천명", 1e3, "명"), ("만명", 1e4, "명"), ("명", 1.0, "명"),
        ("퍼센트", 1.0, "%"), ("％", 1.0, "%"), ("%", 1.0, "%"),
        ("천가구", 1e3, "가구"), ("가구", 1.0, "가구"),
        ("천건", 1e3, "건"), ("건", 1.0, "건"),
    )
    for token, scale, family in aliases:
        if token in compact:
            return scale, family
    return 1.0, ""


def _cell_number(value: str) -> float | None:
    text = str(value or "").strip().replace(",", "").replace("−", "-")
    if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", text):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _meaningful_terms(indicator: str) -> tuple[str, ...]:
    stop = {"수", "비율", "인구", "금액", "규모", "전체", "총", "현황", "통계값"}
    terms = [
        token for token in re.findall(r"[A-Za-z가-힣]+", indicator)
        if len(token) >= 2 and token not in stop
    ]
    return tuple(dict.fromkeys(terms))


def _explicit_age(claim: ClaimSchema) -> int | None:
    text = " ".join(str(value or "") for value in (claim.population, claim.dimension, claim.indicator))
    if match := re.search(r"(?<!\d)(\d{2})\s*대", text):
        return int(match.group(1))
    if match := re.search(r"(?<!\d)(\d{1,2})\s*(?:~|～|−|-)\s*\d{1,2}\s*세", text):
        return int(match.group(1))
    return None


def _age_matches(age: int, value: str) -> bool:
    compact = _normalize(value)
    if f"{age}대" in compact:
        return True
    for start, end in re.findall(r"(\d{1,2})(?:~|～|−|-)(\d{1,2})세?", value):
        if int(start) <= age <= int(end):
            return True
    return False


def _explicit_region(value: str | None) -> str:
    text = str(value or "").strip()
    return "" if _normalize(text) in {"", "전국", "대한민국", "한국"} else text


def _is_total(value: str) -> bool:
    compact = _normalize(value)
    return compact in {"", "전체", "계", "총계", "전국"}


def _normalize(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣%％~～−-]", "", str(value or "")).casefold()


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
