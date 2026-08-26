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
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from core.kosis_openapi_transport import create_kosis_tls_context
from core.official_release_table import extract_hwpx_tables, resolve_direct_value
from core.verdict_engine import make_verdict
from core.trade_publication_verifier import TradePublicationVerifier
from schemas.claim import ClaimSchema
from schemas.verdict import OfficialValueProvenanceSchema, VerdictSchema


_TAGS = re.compile(r"<[^>]+>")
_NUMBER = r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
_TRUSTED_HOSTS = ("kostat.go.kr", "mods.go.kr")
_HWPX_LINK = re.compile(
    r"href=[\"'](?P<href>[^\"']+)[\"'][^>]*>(?P<label>.*?)</a>",
    re.IGNORECASE | re.DOTALL,
)


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
        self._trade_verifier = TradePublicationVerifier(fetch=self._fetch_trade_document, timeout_seconds=timeout_seconds)

    def _fetch_trade_document(self, url: str, timeout: float) -> bytes:
        request = Request(url, headers={"User-Agent": "CLAFACT-AUTO/0.1"})
        with self._opener(request, timeout=timeout) as response:
            return response.read()


    def recover(
        self,
        claim: ClaimSchema,
        verdict: VerdictSchema,
        *,
        article_date: date,
    ) -> VerdictSchema:
        trade_recovered = self._trade_verifier.recover(claim, verdict, article_date=article_date)
        if trade_recovered is not verdict:
            return trade_recovered

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
        expected_period = _reference_period(claim.time)
        if expected_period is None or not _document_has_period(text, expected_period):
            return verdict
        evidence_url = publication.source_url
        evidence_raw = raw
        if claim.calculation == "DIRECT_VALUE":
            direct = self._published_direct_value(
                claim, raw, page_url=publication.source_url,
                reference_period=expected_period,
            )
            if direct is None:
                return verdict
            official_value, evidence_url, evidence_raw = direct
        else:
            official_value = _published_growth_rate(claim, text)
        if official_value is None:
            return verdict

        content_hash = hashlib.sha256(evidence_raw).hexdigest()
        retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        document_publication = publication.model_copy(update={
            "source_url": evidence_url,
            "retrieved_at": retrieved_at,
            "content_hash": content_hash,
            "reference_period": expected_period,
        })
        document_provenance = OfficialValueProvenanceSchema(
            evidence_key=f"OFFICIAL_PUBLICATION_CLAIM:{expected_period}",
            source="OFFICIAL_DOCUMENT",
            source_url=evidence_url,
            retrieved_at=retrieved_at,
            content_hash=content_hash,
            publication=document_publication,
        )
        trace = verdict.execution_trace
        if trace is not None:
            trace = (
                trace.pass_stage("OFFICIAL_AUTHOR_SEARCH", output_ref=evidence_url)
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

    def _published_direct_value(
        self,
        claim: ClaimSchema,
        page_raw: bytes,
        *,
        page_url: str,
        reference_period: str,
    ) -> tuple[float, str, bytes] | None:
        matches: list[tuple[float, str, bytes]] = []
        for attachment_url in _official_hwpx_links(page_raw, page_url):
            try:
                request = Request(
                    attachment_url,
                    headers={
                        "Accept": "application/octet-stream",
                        "User-Agent": "CLAFACT-AUTO/0.1",
                    },
                )
                with self._opener(request, timeout=self._timeout_seconds) as response:
                    raw = response.read()
            except (OSError, RuntimeError, TypeError, ValueError):
                continue
            value = resolve_direct_value(
                claim,
                extract_hwpx_tables(raw),
                reference_period=reference_period,
            )
            if value is not None:
                matches.append((value, attachment_url, raw))
        if len({value for value, _url, _raw in matches}) != 1:
            return None
        return matches[0]


def _eligible(claim: ClaimSchema, verdict: VerdictSchema) -> bool:
    common = (
        verdict.route_status == "HOLD"
        and verdict.reason_code == "AS_OF_UNAVAILABLE"
        and claim.value is not None
    )
    if claim.calculation == "DIRECT_VALUE":
        return common
    return (
        common
        and claim.calculation == "GROWTH_RATE"
        and (claim.unit or "").strip() in {"%", "％", "퍼센트"}
        and _comparison_type(claim) == "YEAR_OVER_YEAR"
    )


def _select_publication(
    claim: ClaimSchema, verdict: VerdictSchema, article_date: date
) -> OfficialValueProvenanceSchema | None:
    expected = _reference_period(claim.time)
    matches = []
    for provenance in verdict.official_value_provenance:
        publication = provenance.publication
        if (
            publication is not None
            and publication.status == "VERIFIED"
            and publication.published_at is not None
            and publication.published_at <= article_date
            and _reference_period(publication.reference_period) == expected
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


def _reference_period(value: str | None) -> str | None:
    text = str(value or "").strip().upper()
    if monthly := _monthly_period(text):
        return monthly
    if match := re.search(r"(?P<year>\d{4})\s*(?:년|[-./])?\s*(?:Q\s*)?(?P<quarter>[1-4])\s*(?:분기|/\s*4|Q)", text):
        return f"{match.group('year')}-Q{match.group('quarter')}"
    if match := re.fullmatch(r"\s*(\d{4})\s*(?:년)?\s*", text):
        return match.group(1)
    return None


def _document_has_period(text: str, period: str) -> bool:
    if re.fullmatch(r"\d{4}-\d{2}", period):
        year, month = period.split("-")
        return re.search(rf"{year}\s*년?\s*{int(month)}\s*월", text) is not None
    if match := re.fullmatch(r"(\d{4})-Q([1-4])", period):
        return re.search(rf"{match.group(1)}\s*년?\s*{match.group(2)}\s*(?:분기|/\s*4)", text) is not None
    return bool(re.fullmatch(r"\d{4}", period) and re.search(rf"{period}\s*년", text))


def _trusted(url: str) -> bool:
    host = (urlparse(url).hostname or "").casefold()
    return any(host == allowed or host.endswith("." + allowed) for allowed in _TRUSTED_HOSTS)


def _document_text(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="replace")
    return re.sub(r"\s+", " ", unescape(_TAGS.sub(" ", text))).strip()


def _normalized(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣%]", "", value).casefold()



def _official_hwpx_links(page_raw: bytes, page_url: str) -> list[str]:
    page = page_raw.decode("utf-8", errors="replace")
    links: list[str] = []
    for match in _HWPX_LINK.finditer(page):
        href = unescape(match.group("href"))
        label = _document_text(match.group("label").encode("utf-8"))
        if ".hwpx" not in (href + " " + label).casefold():
            continue
        url = urljoin(page_url, href)
        if _trusted(url) and url not in links:
            links.append(url)
    return links

def _claim_tolerance(claim: ClaimSchema) -> float:
    source = claim.source_sentence
    target = float(claim.value or 0.0)
    decimals = []
    for match in re.finditer(rf"(?P<value>{_NUMBER})\s*[％%]", source):
        value_text = match.group("value").replace(",", "")
        if abs(float(value_text) - target) <= max(1e-12, abs(target) * 1e-9):
            decimals.append(len(value_text.partition(".")[2]))
    return 0.5 * (10 ** -max(decimals)) if decimals else 0.01
