"""Configured routing for official-author evidence providers.

KOSIS remains the primary path.  This registry only selects a configured
fallback adapter after the primary path has completed its real lookup attempt;
it does not retrieve values, generate verdicts, or inspect article sentences.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar


class OfficialAuthorSourceAdapter(Protocol):
    """Marker protocol for a dependency-injected official-author provider."""


AdapterT = TypeVar("AdapterT", bound=OfficialAuthorSourceAdapter)


@dataclass(frozen=True)
class OfficialAuthorSourceRegistration(Generic[AdapterT]):
    """A closed, configuration-owned route to one official provider."""

    source_authority: str
    statistical_domain: str
    indicator_search_terms: tuple[str, ...]
    adapter: AdapterT

    def __post_init__(self) -> None:
        if not self.source_authority.strip():
            raise ValueError("source_authority must not be empty")
        if not self.statistical_domain.strip():
            raise ValueError("statistical_domain must not be empty")
        if not self.indicator_search_terms:
            raise ValueError("indicator_search_terms must not be empty")
        if any(not term.strip() for term in self.indicator_search_terms):
            raise ValueError("indicator_search_terms must not contain empty terms")


class OfficialAuthorSourceRegistry:
    """In-memory allow-list of official-author fallback routes."""

    def __init__(
        self,
        *,
        registrations: tuple[OfficialAuthorSourceRegistration[OfficialAuthorSourceAdapter], ...],
    ) -> None:
        self._registrations = registrations

    def resolve(
        self,
        *,
        source_authority: str,
        statistical_domain: str,
        indicator_search_terms: tuple[str, ...],
    ) -> OfficialAuthorSourceRegistration[OfficialAuthorSourceAdapter] | None:
        """Return one configured route when all route dimensions agree.

        The lookup intentionally receives structured routing data only.  It
        accepts neither Claim IDs nor source sentences, preventing a specific
        article or Claim from changing provider selection.
        """

        requested_terms = _normalised_terms(indicator_search_terms)
        for registration in self._registrations:
            if _normalise(registration.source_authority) != _normalise(source_authority):
                continue
            if _normalise(registration.statistical_domain) != _normalise(statistical_domain):
                continue
            configured_terms = _normalised_terms(registration.indicator_search_terms)
            if configured_terms.issubset(requested_terms):
                return registration
        return None


def _normalise(value: str) -> str:
    return " ".join(value.casefold().split())


def _normalised_terms(terms: tuple[str, ...]) -> frozenset[str]:
    return frozenset(_normalise(term) for term in terms if _normalise(term))
