"""Distinguish published observations from forecasts before KOSIS lookup."""

from __future__ import annotations

import re

from schemas.claim import ClaimSchema


_FORECAST = re.compile(
    r"(?:전망(?:했|한|할|된|치)?|예상(?:했|한|할|된)?|예측|내다봤|"
    r"가능(?:하|할|성)|것(?:이)?라고\s*(?:봤|했)|것으로\s*(?:봤|전망|예상)|"
    r"떨어질\s*것|오를\s*것|것이라고\s*발표|달성(?:도)?\s*가능|목표(?:로|치)?)"
)
_OBSERVED = re.compile(r"(?:집계됐|집계했다|기록했|나타났|확정됐|발표한|조사한\s*결과)")
_PRIVATE_TRANSACTION = re.compile(
    r"(?:계약(?:액|금액)?|자본금).{0,40}(?:따냈|체결|맺|설립|규모)|"
    r"(?:따냈|체결|맺|설립|규모).{0,40}(?:계약(?:액|금액)?|자본금)"
)
_PRODUCT_PRICE = re.compile(r"(?:판매\s*가격|출고가|제품\s*가격|모델\s*가격)")
_POLICY_THRESHOLD = re.compile(r"(?:지정\s*기준|적용\s*기준|상한(?:액)?|하한(?:액)?|기준\s*금액|법인차.{0,30}표지판|해야\s*한다)")


def observation_preverification_reason(claim: ClaimSchema) -> str | None:
    """Return a deterministic reason when a direct value is explicitly prospective."""
    if claim.calculation != "DIRECT_VALUE":
        return None
    source = claim.source_sentence
    fields = f"{claim.indicator or ''} {source}"
    if _PRIVATE_TRANSACTION.search(fields):
        return "NON_STATISTICAL_PRIVATE_TRANSACTION"
    if _PRODUCT_PRICE.search(fields) and not _OBSERVED.search(source):
        return "NON_STATISTICAL_PRODUCT_PRICE"
    if _POLICY_THRESHOLD.search(fields) and not _OBSERVED.search(source):
        return "NON_STATISTICAL_POLICY_THRESHOLD"
    if _FORECAST.search(source) and not _OBSERVED.search(source):
        return "NON_OBSERVED_FORECAST"
    return None
