"""Recover article-time Claim evidence from an already verified official release.

This is a narrow, deterministic alternative after KOSIS value retrieval has
already produced ``AS_OF_UNAVAILABLE``.  It never invents an official value:
the value must be stated in the trusted, period-specific publication itself.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timezone
from html import unescape
from typing import Any, Callable
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from core.kosis_openapi_transport import create_kosis_tls_context
from core.verdict_engine import make_verdict
from schemas.claim import ClaimSchema
from schemas.verdict import OfficialValueProvenanceSchema, VerdictSchema


_TAGS = re.compile(r"<[^>]+>")
_NUMBER = r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
_TRUSTED_HOSTS = ("kostat.go.kr", "mods.go.kr")


def _default_opener(request: object, *, timeout: float):
    return urlopen(request, timeout=timeout, context=create_kosis_tls_context())


class OfficialPublicationClaimVerifier:
    """Use a KOSTAT/MODS release only when every Claim guard is explicit."""

    def __init__(
        self,
        *,
        opener: Callable[..., Any] = _default_opener,
        timeout_seconds: int = 15,
    ) -> None:
        self._opener = opener
        self._timeout_seconds = max(1, timeout_seconds)

    def recover(
        self,
        claim: ClaimSchema,
        verdict: VerdictSchema,
        *,
        article_date: date,
    ) -> VerdictSchema:
        if not _eligible(claim, verdict):
            return verdict
        publication_provenance = _select_publication(claim, verdict, article_date)
        if publication_provenance is None:
            return verdict
        publication = publication_provenance.publication
        assert publication is not None
        if not _trusted(publication.source_url):
            return verdict
        try:
            request = Request(
                publication.source_url,
                headers={
                    "Accept": "text/html,application/xhtml+xml",
                    "User-Agent": "CLAFACT-AUTO/0.1",
                },
            )
            with self._opener(request, timeout=self._timeout_seconds) as response:
                raw = response.read()
        except (OSError, RuntimeError, TypeError, ValueError):
            return verdict
        if not raw:
            return verdict
        text = _document_text(raw)
        expected_period = _monthly_period(claim.time)
        if expected_period is None or not _document_has_period(text, expected_period):
            return verdict
        official_value = _published_growth_rate(claim, text)
        if official_value is None:
            return verdict

        content_hash = hashlib.sha256(raw).hexdigest()
        retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        document_publication = publication.model_copy(update={
            "source_url": publication.source_url,
            "retrieved_at": retrieved_at,
            "content_hash": content_hash,
            "reference_period": expected_period,
        })
        document_provenance = OfficialValueProvenanceSchema(
            evidence_key=f"OFFICIAL_PUBLICATION_CLAIM:{expected_period}",
            source="OFFICIAL_DOCUMENT",
            source_url=publication.source_url,
            retrieved_at=retrieved_at,
            content_hash=content_hash,
            publication=document_publication,
        )
        trace = verdict.execution_trace
        if trace is not None:
            trace = (
                trace.pass_stage("OFFICIAL_AUTHOR_SEARCH", output_ref=publication.source_url)
                .pass_stage("OFFICIAL_AUTHOR_FETCH", output_ref=content_hash)
                .pass_stage("CALCULATION")
                .pass_stage("VERDICT")
                .model_copy(update={"route_status": "AUTO"})
            )
        recovered = make_verdict(
            claim.claim_id,
            claim.value,
            [official_value],
            official_value,
            tolerance=_claim_tolerance(claim),
            trace=trace,
        )
        return recovered.model_copy(update={
            "evidence_cells": verdict.evidence_cells,
            "official_value_provenance": [
                *verdict.official_value_provenance,
                document_provenance,
            ],
        })


def _eligible(claim: ClaimSchema, verdict: VerdictSchema) -> bool:
    return (
        verdict.route_status == "HOLD"
        and verdict.reason_code == "AS_OF_UNAVAILABLE"
        and claim.calculation == "GROWTH_RATE"
        and claim.value is not None
        and (claim.unit or "").strip() in {"%", "％", "퍼센트"}
        and _comparison_type(claim) == "YEAR_OVER_YEAR"
    )


def _select_publication(
    claim: ClaimSchema, verdict: VerdictSchema, article_date: date
) -> OfficialValueProvenanceSchema | None:
    expected = _monthly_period(claim.time)
    matches = []
    for provenance in verdict.official_value_provenance:
        publication = provenance.publication
        if (
            publication is not None
            and publication.status == "VERIFIED"
            and publication.published_at is not None
            and publication.published_at <= article_date
            and _monthly_period(publication.reference_period) == expected
        ):
            matches.append(provenance)
    urls = {item.publication.source_url for item in matches if item.publication is not None}
    return matches[0] if len(urls) == 1 else None


def _published_growth_rate(claim: ClaimSchema, text: str) -> float | None:
    indicator = _normalized(claim.indicator or "")
    if not indicator:
        return None
    comparison_pattern = r"전년\s*동월\s*대비"
    direction = _direction(claim)
    if direction is None:
        return None
    direction_word = "증가" if direction == "INCREASE" else "감소"
    normalized_text = re.sub(r"\s+", " ", text)
    clauses = re.split(r"(?<=[!?。])|(?<=\.)\s+|(?:\s[-·•]\s)", normalized_text)
    values: list[float] = []
    for clause in clauses:
        if indicator not in _normalized(clause):
            continue
        pattern = re.compile(
            rf"{comparison_pattern}\s*(?:약\s*)?(?P<value>{_NUMBER})\s*[％%]\s*{direction_word}"
        )
        found = pattern.search(clause)
        if found is not None:
            values.append(float(found.group("value").replace(",", "")))
    unique = sorted(set(values))
    return unique[0] if len(unique) == 1 else None


def _comparison_type(claim: ClaimSchema) -> str | None:
    comparison = claim.comparison if isinstance(claim.comparison, dict) else {}
    value = str(comparison.get("type") or "")
    normalized = re.sub(r"[\s_-]+", "", value).casefold()
    if normalized in {"yearoveryear", "전년대비", "전년동월대비", "전년동월비", "전년비"}:
        return "YEAR_OVER_YEAR"
    return None


def _direction(claim: ClaimSchema) -> str | None:
    condition = claim.condition if isinstance(claim.condition, dict) else {}
    direction = str(condition.get("direction") or "").upper()
    if direction in {"INCREASE", "DECREASE"}:
        return direction
    if "증가" in claim.source_sentence or "늘" in claim.source_sentence:
        return "INCREASE"
    if "감소" in claim.source_sentence or "줄" in claim.source_sentence:
        return "DECREASE"
    return None


def _monthly_period(value: str | None) -> str | None:
    text = str(value or "").strip()
    match = re.search(r"(?P<year>\d{4})\s*(?:년|[-./])\s*(?P<month>\d{1,2})(?:\s*월)?", text)
    if match is None:
        return None
    month = int(match.group("month"))
    if not 1 <= month <= 12:
        return None
    return f"{match.group('year')}-{month:02d}"


def _document_has_period(text: str, period: str) -> bool:
    year, month = period.split("-")
    return re.search(rf"{year}\s*년?\s*{int(month)}\s*월", text) is not None


def _trusted(url: str) -> bool:
    host = (urlparse(url).hostname or "").casefold()
    return any(host == allowed or host.endswith("." + allowed) for allowed in _TRUSTED_HOSTS)


def _document_text(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="replace")
    return re.sub(r"\s+", " ", unescape(_TAGS.sub(" ", text))).strip()


def _normalized(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣%]", "", value).casefold()


def _claim_tolerance(claim: ClaimSchema) -> float:
    source = claim.source_sentence
    target = float(claim.value or 0.0)
    decimals = []
    for match in re.finditer(rf"(?P<value>{_NUMBER})\s*[％%]", source):
        value_text = match.group("value").replace(",", "")
        if abs(float(value_text) - target) <= max(1e-12, abs(target) * 1e-9):
            decimals.append(len(value_text.partition(".")[2]))
    return 0.5 * (10 ** -max(decimals)) if decimals else 0.01
