"""One Core Engine entrypoint for official KOSIS evidence resolution."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from core import dynamic_kosis_verifier
from core.dynamic_kosis_verifier import OfficialValueFetcher
from core.operational_error import run_operational_stage
from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema
from schemas.verdict import VerdictSchema

ConceptMapper = Callable[[ClaimSchema], StandardConceptSchema]
CatalogResolver = Callable[[ClaimSchema, StandardConceptSchema], list[KosisCandidateSchema]]


@dataclass(frozen=True, slots=True)
class OfficialEvidenceResolution:
    """Complete official-evidence data retained for UI and batch display."""

    concept: StandardConceptSchema
    candidates: list[KosisCandidateSchema]
    verdict: VerdictSchema


class OfficialEvidenceService:
    """Use one Core flow for Catalog, official evidence, and final Verdict."""

    def __init__(
        self,
        *,
        concept_mapper: ConceptMapper,
        catalog_resolver: CatalogResolver,
        official_fetcher: OfficialValueFetcher,
    ) -> None:
        self._concept_mapper = concept_mapper
        self._catalog_resolver = catalog_resolver
        self._official_fetcher = official_fetcher

    def resolve(
        self, claim: ClaimSchema, *, article_date: date
    ) -> OfficialEvidenceResolution:
        concept = self._concept_mapper(claim)
        candidates = (
            run_operational_stage(
                "KOSIS_CATALOG",
                lambda: self._catalog_resolver(claim, concept),
            )
            if concept.status == "MATCHED"
            else []
        )
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
        )