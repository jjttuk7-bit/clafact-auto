"""One Core Engine entrypoint for official KOSIS evidence resolution."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

from core import dynamic_kosis_verifier
from core.dynamic_kosis_verifier import OfficialValueFetcher
from core.operational_error import run_operational_stage
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema
from schemas.verdict import VerdictSchema


@dataclass(frozen=True, slots=True)
class CatalogResolution:
    """Safe operational summary of one Catalog search."""

    candidates: list[KosisCandidateSchema]
    diagnostics: dict[str, int] = field(default_factory=dict)


ConceptMapper = Callable[[ClaimSchema], StandardConceptSchema]
CatalogResolver = Callable[[ClaimSchema, StandardConceptSchema], list[KosisCandidateSchema] | CatalogResolution]
CandidateSelector = Callable[
    [ClaimSchema, StandardConceptSchema, list[KosisCandidateSchema]],
    list[KosisCandidateSchema],
]


@dataclass(frozen=True, slots=True)
class OfficialEvidenceResolution:
    """Complete official-evidence data retained for UI and batch display."""

    concept: StandardConceptSchema
    candidates: list[KosisCandidateSchema]
    verdict: VerdictSchema
    catalog_diagnostics: dict[str, int] = field(default_factory=dict)


class OfficialEvidenceService:
    """Use one Core flow for Catalog, official evidence, and final Verdict."""

    def __init__(
        self,
        *,
        concept_mapper: ConceptMapper,
        catalog_resolver: CatalogResolver,
        official_fetcher: OfficialValueFetcher,
        candidate_selector: CandidateSelector | None = None,
    ) -> None:
        self._concept_mapper = concept_mapper
        self._catalog_resolver = catalog_resolver
        self._official_fetcher = official_fetcher
        self._candidate_selector = candidate_selector or (
            lambda _claim, _concept, candidates: candidates
        )

    def resolve(self, claim: ClaimSchema, *, article_date: date) -> OfficialEvidenceResolution:
        concept = self._concept_mapper(claim)
        catalog_result = (
            run_operational_stage("KOSIS_CATALOG", lambda: self._catalog_resolver(claim, concept))
            if concept.status == "MATCHED"
            else []
        )
        if isinstance(catalog_result, CatalogResolution):
            candidates = catalog_result.candidates
            catalog_diagnostics = dict(catalog_result.diagnostics)
        else:
            candidates = catalog_result
            catalog_diagnostics = {}
        # Explicit bindings are applied only after live Catalog and official
        # metadata hydration. They therefore narrow verified candidates; they
        # never replace either official lookup.
        candidates = self._candidate_selector(claim, concept, candidates)
        verdict = run_operational_stage(
            "VERIFICATION",
            lambda: dynamic_kosis_verifier.verify_claim_against_kosis(
                claim,
                concept,
                candidates,
                article_date=article_date,
                official_fetcher=self._official_fetcher,
            ),
        )
        return OfficialEvidenceResolution(
            concept=concept,
            candidates=candidates,
            verdict=verdict,
            catalog_diagnostics=catalog_diagnostics,
        )
