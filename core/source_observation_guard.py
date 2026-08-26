"""Distinguish published observations from forecasts before KOSIS lookup."""

from __future__ import annotations

import re

from schemas.claim import ClaimSchema


_FORECAST = re.compile(
    r"(?:전망(?:했|한|할|된|치)?|예상(?:했|한|할|된)?|예측|내다봤|"
    r"가능(?:하|할|성)|것(?:이)?라고\s*(?:봤|했)|것으로\s*(?:봤|전망|예상)|"
    r"떨어질\s*것|오를\s*것|달성(?:도)?\s*가능|목표(?:로|치)?)"
)
_OBSERVED = re.compile(r"(?:집계됐|집계했다|기록했|나타났|확정됐|발표한|조사한\s*결과)")


def observation_preverification_reason(claim: ClaimSchema) -> str | None:
    """Return a deterministic reason when a direct value is explicitly prospective."""
    if claim.calculation != "DIRECT_VALUE":
        return None
    source = claim.source_sentence
    if _FORECAST.search(source) and not _OBSERVED.search(source):
        return "NON_OBSERVED_FORECAST"
    return None
