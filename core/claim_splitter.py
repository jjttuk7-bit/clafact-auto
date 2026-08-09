"""Deterministic splitting of sentences containing multiple numeric claims."""

from __future__ import annotations

import re


_CLAUSE_SEPARATOR = re.compile(r"\s*(?:,(?!\d)|(?:였|었|이)고|그리고)\s*")
_NUMBER = re.compile(r"\d+(?:[,.]\d+)*(?:%|명|원|건|배|억|만|천)?")


def split_complex_claim(sentence: str) -> list[str]:
    """Split only numeric clauses; leave singular claims exactly intact."""
    normalized = sentence.strip()
    if len(_NUMBER.findall(normalized)) < 2:
        return [normalized]

    clauses = [clause.strip() for clause in _CLAUSE_SEPARATOR.split(normalized) if clause.strip()]
    if len(clauses) < 2 or not all(_NUMBER.search(clause) for clause in clauses):
        return [normalized]
    return clauses

