"""Deterministic splitting for source-backed record comparison Claims."""

from hashlib import sha256

from schemas.claim import ClaimSchema


_RECORD_TYPES = {"RECORD_HIGH", "RECORD_LOW"}
_RECORD_REPARSE_REASONS = {"RECORD_COMPARISON_REQUIRES_SEPARATE_CLAIM"}
_RECORD_SIGNALS = {
    "RECORD_HIGH": (
        "\uc5ed\ub300 \ucd5c\ub300", "\uc5ed\ub300 \ucd5c\uace0", "\uc0ac\uc0c1 \ucd5c\ub300", "\uc0ac\uc0c1 \ucd5c\uace0",
        "\ucd5c\ub300\uce58", "\ucd5c\uace0\uce58", "record high",
    ),
    "RECORD_LOW": (
        "\uc5ed\ub300 \ucd5c\uc800", "\uc5ed\ub300 \ucd5c\uc18c", "\uc0ac\uc0c1 \ucd5c\uc800", "\uc0ac\uc0c1 \ucd5c\uc18c",
        "\ucd5c\uc800\uce58", "\ucd5c\uc18c\uce58", "record low",
    ),
}


def split_record_comparison_claim(claim: ClaimSchema) -> list[ClaimSchema]:
    """Split a numeric level from its record assertion without resampling."""
    comparison_type = str((claim.comparison or {}).get("type", "")).strip().upper()
    if comparison_type not in _RECORD_TYPES:
        return [claim]
    if claim.parse_status != "AUTO_OK" and claim.parse_reason not in _RECORD_REPARSE_REASONS:
        return [claim]
    source = claim.source_sentence.casefold()
    if not any(signal in source for signal in _RECORD_SIGNALS[comparison_type]):
        return [claim]
    if claim.value is None or not claim.unit or not claim.time or not claim.indicator:
        return [claim]

    common = {"parse_status": "AUTO_OK", "parse_reason": None}
    direct = claim.model_copy(update={
        **common,
        "claim_id": _child_id(claim, "DIRECT_VALUE"),
        "calculation": "DIRECT_VALUE",
        "comparison": None,
    })
    record = claim.model_copy(update={
        **common,
        "claim_id": _child_id(claim, comparison_type),
        "calculation": comparison_type,
        "comparison": {**(claim.comparison or {}), "type": comparison_type},
    })
    return [direct, record]


def _child_id(claim: ClaimSchema, role: str) -> str:
    identity = f"{claim.claim_id}\n{claim.source_sentence}\n{role}"
    return f"claim_{sha256(identity.encode('utf-8')).hexdigest()[:16]}"
