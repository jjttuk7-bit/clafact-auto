"""Structured KOSIS dimension-member name/code mapping utilities."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any


def build_member_code_map(records: Iterable[dict[str, Any]]) -> dict[str, dict[str, str]]:
    """Build a strict dimension -> member name -> member code mapping from catalog rows."""
    result: dict[str, dict[str, str]] = defaultdict(dict)
    for record in records:
        dimension_id = record.get("dimension_id")
        member_code = record.get("member_code")
        member_name = record.get("member_name")
        if not all(isinstance(value, str) and value.strip() for value in (dimension_id, member_code, member_name)):
            continue
        existing = result[dimension_id].get(member_name)
        if existing is not None and existing != member_code:
            raise ValueError("KOSIS_MEMBER_CODE_CONFLICT")
        result[dimension_id][member_name] = member_code
    return dict(result)


def resolve_member_code(mapping: dict[str, dict[str, str]], dimension_id: str, member_name: str) -> str | None:
    """Resolve a normalized member label only when it maps to one code."""
    target = _normalize(member_name)
    matches = {code for name, code in mapping.get(dimension_id, {}).items() if _normalize(name) == target}
    return next(iter(matches)) if len(matches) == 1 else None


def _normalize(value: str) -> str:
    normalized = value.replace(" ", "").replace("-", "").replace("~", "")
    regional_aliases = {
        "경기도": "경기", "경기": "경기",
        "강원도": "강원", "강원특별자치도": "강원", "강원": "강원",
        "충청북도": "충북", "충북": "충북",
        "충청남도": "충남", "충남": "충남",
        "전북특별자치도": "전북", "전라북도": "전북", "전북": "전북",
        "전라남도": "전남", "전남": "전남",
        "경상북도": "경북", "경북": "경북",
        "경상남도": "경남", "경남": "경남",
        "제주특별자치도": "제주", "제주도": "제주", "제주": "제주",
    }
    return regional_aliases.get(normalized, normalized)
