"""Deterministic pre-KOSIS admission routing for numeric candidates."""

from __future__ import annotations

import re

from core.claim_splitter import detect_structural_multi_claim
from schemas.claim import ClaimSchema
from schemas.claim_admission import AdmissionDecision


_FORECAST = re.compile(r"전망|예상|가능성|것으로 보|내다봤|계획|예정|공약")
_NOT_A_CLAIM = re.compile(r"지급한다|지원한다|받는다|정의|뜻한다|말한다|기준을 발표")
_NON_KOSIS = re.compile(
    r"현대차|기아|삼성|업비트|테슬라|메르세데스|한국GM|한국수입자동차협회|협회"
)
_MULTI_CONNECTOR = re.compile(r"(?:이고|이며|각각|동시에|뿐 아니라)")
_NUMBER = re.compile(r"\d+(?:[,.]\d+)*(?:%|%p|명|원|건|배|억|만|천|ha|대)?")


def route_claim_admission(claim: ClaimSchema) -> AdmissionDecision:
    """Classify a candidate before any KOSIS API request is attempted."""
    sentence = claim.source_sentence.strip()
    if _NOT_A_CLAIM.search(sentence):
        return AdmissionDecision(
            label="NOT_A_VERIFIABLE_CLAIM", reason_code="POLICY_OR_DEFINITION"
        )
    if _FORECAST.search(sentence):
        return AdmissionDecision(
            label="FORECAST_OPINION_UNVERIFIABLE", reason_code="FORECAST_OR_OPINION"
        )
    if _NON_KOSIS.search(sentence):
        return AdmissionDecision(
            label="NON_KOSIS_OR_PRIVATE", reason_code="PRIVATE_OR_COMPANY_SOURCE"
        )
    if detect_structural_multi_claim(sentence):
        return AdmissionDecision(
            label="MULTI_CLAIM_SPLIT_REQUIRED", reason_code="STRUCTURAL_MULTI_CLAIM"
        )
    if _is_multi_numeric_claim(sentence):
        return AdmissionDecision(
            label="MULTI_CLAIM_SPLIT_REQUIRED", reason_code="MULTIPLE_NUMERIC_CLAUSES"
        )
    if claim.parse_status != "AUTO_OK":
        return AdmissionDecision(label="CONTEXT_REQUIRED", reason_code="PARSE_UNCERTAIN")
    if not claim.time:
        return AdmissionDecision(label="CONTEXT_REQUIRED", reason_code="MISSING_TIME_CONTEXT")
    if not all((claim.indicator, claim.value is not None, claim.unit, claim.calculation)):
        return AdmissionDecision(label="CONTEXT_REQUIRED", reason_code="MISSING_SLOT_CONTEXT")
    return AdmissionDecision(
        label="KOSIS_PIPELINE_ELIGIBLE", reason_code="SINGLE_STATISTICAL_CLAIM"
    )


def _is_multi_numeric_claim(sentence: str) -> bool:
    return bool(_MULTI_CONNECTOR.search(sentence)) and len(_NUMBER.findall(sentence)) >= 2


