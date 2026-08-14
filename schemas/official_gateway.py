"""Credential-free HTTP contract for the direct KOSIS Gateway."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from schemas.candidate import KosisCandidateSchema
from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema
from schemas.verdict import VerdictSchema


class GatewayVerifyRequest(BaseModel):
    """A structured Claim request; KOSIS credentials never cross this boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    claim: ClaimSchema
    article_date: date


class GatewayVerifyResponse(BaseModel):
    """Auditable verification output with safe, aggregate Catalog diagnostics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    concept: StandardConceptSchema
    candidates: list[KosisCandidateSchema] = Field(default_factory=list)
    verdict: VerdictSchema
    catalog_diagnostics: dict[str, int] = Field(default_factory=dict)
