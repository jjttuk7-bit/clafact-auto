"""KOSIS-afterward, configuration-routed official-author fallback values."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from core.claim_dimensions import normalized_dimension_members
from core.official_author_registry import OfficialAuthorSourceRegistry
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema
from schemas.official_author import OfficialAuthorEvidenceSchema


@dataclass(frozen=True, slots=True)
class OfficialAuthorFallbackValue:
    """One directly stated, auditable official-author value."""

    value: float
    evidence: OfficialAuthorEvidenceSchema


class OfficialAuthorFallback(Protocol):
    """Resolve a value only after the KOSIS route has genuinely failed."""

    def fetch(
        self, *, claim: ClaimSchema, concept: StandardConceptSchema, article_date: date
    ) -> OfficialAuthorFallbackValue | None: ...


@dataclass(frozen=True, slots=True)
class OfficialAuthorRouteContext:
    """Configuration-owned structured routing fields, never article text/IDs."""

    source_authority: str
    statistical_domain: str
    concept_terms: tuple[str, ...]


class ConfiguredOfficialAuthorFallback:
    """Route only configured semantic concepts to their injected provider adapter."""

    def __init__(
        self,
        *,
        registry: OfficialAuthorSourceRegistry,
        route_contexts: dict[str, OfficialAuthorRouteContext],
    ) -> None:
        self._registry = registry
        self._route_contexts = dict(route_contexts)

    def fetch(
        self, *, claim: ClaimSchema, concept: StandardConceptSchema, article_date: date
    ) -> OfficialAuthorFallbackValue | None:
        context = self._route_contexts.get(concept.standard_key)
        if context is None:
            return None
        registration = self._registry.resolve(
            source_authority=context.source_authority,
            statistical_domain=context.statistical_domain,
            indicator_search_terms=context.concept_terms,
        )
        if registration is None:
            return None
        fetch = getattr(registration.adapter, "fetch", None)
        if not callable(fetch):
            return None
        result = fetch(
            claim=claim,
            concept=concept,
            indicator_search_terms=registration.indicator_search_terms,
            article_date=article_date,
        )
        return result if isinstance(result, OfficialAuthorFallbackValue) else None


class KostatOfficialReleaseAdapter:
    """Direct Statistics Korea release adapter for a configured registry route."""

    def __init__(self, *, release_search: object, document_fetcher: object) -> None:
        self._release_search = release_search
        self._document_fetcher = document_fetcher

    def fetch(
        self, *, claim: ClaimSchema, concept: StandardConceptSchema,
        indicator_search_terms: tuple[str, ...], article_date: date,
    ) -> OfficialAuthorFallbackValue | None:
        if not claim.indicator or not claim.time or not claim.unit or not _national_scope(claim.region):
            return None
        period = _annual_period(claim.time)
        if period is None:
            return None
        find = getattr(self._release_search, "find", None)
        fetch_document = getattr(self._document_fetcher, "fetch_document", None)
        if not callable(find) or not callable(fetch_document):
            return None
        release_indicator = _release_search_name(claim)
        release = find(release_indicator, period, None, None)
        release_url = getattr(release, "source_url", None)
        if not release_url:
            return None
        document = fetch_document(release_url=release_url, article_date=article_date)
        if document is None:
            return None
        from core.kosis_publication import extract_official_release_value
        from core.kostat_release_value_fetcher import extract_unambiguous_release_value, _extract_pdf_text, _scope_matches

        text = _extract_pdf_text(document.document_bytes)
        direct_value = extract_official_release_value(
            text or "", period=period, indicator=release_indicator, unit=claim.unit,
        )
        document_scope = _document_scope_for_value(
            text or "", period=period, indicator=release_indicator, value=direct_value, unit=claim.unit,
        )
        if direct_value is None or not _scope_matches(claim.region, document_scope):
            return None
        value = extract_unambiguous_release_value(
            document, period=period, indicator=release_indicator, unit=claim.unit,
            claim_scope=claim.region, document_scope=document_scope,
        )
        if value is None or not text:
            return None
        snippet = _extraction_snippet(text, release_indicator, value, claim.unit)
        if snippet is None:
            return None
        return OfficialAuthorFallbackValue(
            value=value,
            evidence=OfficialAuthorEvidenceSchema(
                source_url=document.source_url, published_at=document.published_at,
                document_hash=document.document_hash, extraction_snippet=snippet,
                extraction_context=f"KOSTAT national release; concept={concept.standard_key}; period={period}",
            ),
        )


def _release_search_name(claim: ClaimSchema) -> str:
    """Add one configured crop dimension to the official release search name."""
    indicator = (claim.indicator or "").strip()
    crop_values = [
        value for key, values in normalized_dimension_members(claim.dimension).items()
        if key.strip().casefold() in {"\uc791\ubb3c", "crop", "crop_type"}
        for value in values
    ]
    unique = list(dict.fromkeys(value.strip() for value in crop_values if value.strip()))
    if len(unique) != 1 or unique[0] in indicator:
        return indicator
    return f"{unique[0]} {indicator}"


def _annual_period(value: str) -> str | None:
    import re
    match = re.fullmatch(r"\s*(20\d{2})\s*(?:\ub144)?\s*", value)
    return match.group(1) if match else None


def _national_scope(value: str | None) -> bool:
    return (value or "").strip().casefold() in {"\uc804\uad6d", "\ud55c\uad6d", "\ub300\ud55c\ubbfc\uad6d", "national"}


def _extraction_snippet(text: str, indicator: str, value: float, unit: str) -> str | None:
    import re
    number = f"{value:,.10g}".rstrip("0").rstrip(".")
    match = re.search(
        rf"[^\n]{{0,100}}{re.escape(indicator)}[^\n]{{0,120}}{re.escape(number)}[^\n]{{0,30}}{re.escape(unit)}[^\n]{{0,100}}",
        text,
    )
    return match.group(0).strip() if match else None


def _document_scope_for_value(
    text: str, *, period: str, indicator: str, value: float | None, unit: str,
) -> str | None:
    """Accept scope only when explicitly bound to the extracted value context."""
    import re
    if value is None:
        return None
    number = re.escape(f"{value:,.10g}".rstrip("0").rstrip("."))
    compact_indicator = r"\s*".join(re.escape(part) for part in indicator.split() if part)
    unit_pattern = r"(?:ha|\ud5e5\ud0c0\ub974)" if unit.casefold() in {"ha", "\ud5e5\ud0c0\ub974"} else re.escape(unit)
    match = re.search(
        rf"{re.escape(period)}\s*\ub144.{{0,100}}?{compact_indicator}.{{0,140}}?{number}\s*{unit_pattern}",
        text, re.IGNORECASE | re.DOTALL,
    )
    if match is None:
        return None
    context = text[max(0, match.start() - 160): match.end()]
    scopes: set[str] = set()
    if "\ubd81\ud55c" in context:
        scopes.add("\ubd81\ud55c")
    if re.search(r"\uc804\uad6d\s*(?:\uc804\uccb4|\uae30\uc900|\ud569\uacc4)?", context):
        scopes.add("national")
    for scope in ("\uc804\ub77c\ub0a8\ub3c4", "\uc804\ub77c\ubd81\ub3c4", "\uacbd\uc0c1\ub0a8\ub3c4", "\uacbd\uc0c1\ubd81\ub3c4", "\ucda9\uccad\ub0a8\ub3c4", "\ucda9\uccad\ubd81\ub3c4", "\uac15\uc6d0\ub3c4", "\uacbd\uae30\ub3c4", "\uc81c\uc8fc\ub3c4", "\uc138\uc885"):
        if scope in context:
            scopes.add(scope)
    if len(scopes) == 1:
        return next(iter(scopes))
    if scopes:
        return None
    if re.search(
        r"(?:\uc870\uc0ac\ub300\uc0c1|\uc870\uc0ac\uccb4\uacc4\s*\ubc0f\s*\ubc29\ubc95|\uc870\uc0ac\ubc29\ubc95).{0,160}?\uc804\uad6d\s*[\d,]+\s*\uac1c\s*\ud45c\ubcf8\uc870\uc0ac\uad6c",
        text,
        re.DOTALL,
    ):
        return "national"
    return None