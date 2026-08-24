"""Fail-closed guards for statistical targets inherited from prior context."""

from __future__ import annotations

from typing import Any


_GENERIC_TARGETS = {"", "전체", "계", "총계"}


def context_target_unresolved(source_text: str, claim: Any) -> bool:
    """Return true when a sentence-initial 'also' Claim omits its target."""
    normalized_text = "".join(str(source_text or "").split())
    indicator = "".join(str(getattr(claim, "indicator", "") or "").split())
    if not indicator or not normalized_text.startswith(f"{indicator}도"):
        return False
    target_values = (
        getattr(claim, "population", None),
        getattr(claim, "region", None),
        getattr(claim, "dimension", None),
    )
    explicit_targets = {
        "".join(token.split())
        for value in target_values
        for token in _target_tokens(value)
        if "".join(token.split()) not in _GENERIC_TARGETS
    }
    return not any(token and token in normalized_text for token in explicit_targets)


def _target_tokens(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    if isinstance(value, dict):
        return tuple(
            token
            for nested in value.values()
            for token in _target_tokens(nested)
        )
    if isinstance(value, (list, tuple, set)):
        return tuple(token for nested in value for token in _target_tokens(nested))
    return (str(value).strip(),)
