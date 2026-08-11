"""Deterministic selection of registered verification profiles."""

from dataclasses import dataclass
from typing import Iterable, Literal

from schemas.claim import ClaimSchema
from schemas.concept import StandardConceptSchema
from schemas.verification_profile import VerificationProfileSchema


ProfileFirstStatus = Literal["MATCHED", "NOT_FOUND", "HOLD"]


@dataclass(frozen=True)
class ProfileFirstResolution:
    """A safe routing decision before catalog search and evidence retrieval."""

    status: ProfileFirstStatus
    profile: VerificationProfileSchema | None = None
    reason_code: str | None = None


def resolve_profile_first(
    claim: ClaimSchema,
    concept: StandardConceptSchema,
    profiles: Iterable[VerificationProfileSchema],
) -> ProfileFirstResolution:
    """Select exactly one profile or return a safe fallback/HOLD routing result."""
    if concept.status != "MATCHED":
        return ProfileFirstResolution(status="NOT_FOUND")

    matched_profiles = [
        profile for profile in profiles if profile.claim_key == concept.standard_key
    ]
    if not matched_profiles:
        return ProfileFirstResolution(status="NOT_FOUND")
    if len(matched_profiles) != 1:
        return ProfileFirstResolution(
            status="HOLD", reason_code="PROFILE_KEY_CONFLICT"
        )

    profile = matched_profiles[0]
    if not _has_complete_coordinate(profile):
        return ProfileFirstResolution(
            status="HOLD", reason_code="PROFILE_COORDINATE_INCOMPLETE"
        )
    if claim.calculation is not None and claim.calculation != profile.calculation_type:
        return ProfileFirstResolution(
            status="HOLD", reason_code="PROFILE_CALCULATION_CONFLICT"
        )
    conflict = _applicability_conflict(claim, profile)
    if conflict:
        return ProfileFirstResolution(status="HOLD", reason_code=conflict)
    return ProfileFirstResolution(status="MATCHED", profile=profile)


def _applicability_conflict(
    claim: ClaimSchema, profile: VerificationProfileSchema
) -> str | None:
    if profile.frequency_constraint is not None:
        if claim.frequency is None:
            return "PROFILE_FREQUENCY_UNRESOLVED"
        if _frequency_mismatch(claim.frequency, profile.frequency_constraint):
            return "PROFILE_FREQUENCY_CONFLICT"
    if profile.region_constraint is not None:
        if claim.region is None:
            return "PROFILE_REGION_UNRESOLVED"
        if _string_mismatch(claim.region, profile.region_constraint):
            return "PROFILE_REGION_CONFLICT"
    if profile.population_constraint is not None:
        if claim.population is None:
            return "PROFILE_POPULATION_UNRESOLVED"
        if _string_mismatch(claim.population, profile.population_constraint):
            return "PROFILE_POPULATION_CONFLICT"
    if profile.condition_constraint is not None:
        if claim.condition is None:
            return "PROFILE_CONDITION_UNRESOLVED"
        if claim.condition != profile.condition_constraint:
            return "PROFILE_CONDITION_CONFLICT"
    if profile.dimension_constraint is not None:
        if claim.dimension is None:
            return "PROFILE_DIMENSION_UNRESOLVED"
        if claim.dimension != profile.dimension_constraint:
            return "PROFILE_DIMENSION_CONFLICT"
    return None
def _frequency_mismatch(claim_value: str | None, profile_value: str | None) -> bool:
    if claim_value is None or profile_value is None:
        return False
    aliases = {"monthly": "M", "month": "M", "월": "M", "m": "M", "yearly": "Y", "annual": "Y", "년": "Y", "y": "Y"}
    return aliases.get(claim_value.strip().casefold(), claim_value) != aliases.get(profile_value.strip().casefold(), profile_value)


def _string_mismatch(claim_value: str | None, profile_value: str | None) -> bool:
    return claim_value is not None and profile_value is not None and claim_value.strip() != profile_value.strip()

def _has_complete_coordinate(profile: VerificationProfileSchema) -> bool:
    """Defend callers against profile objects constructed without validation."""
    return all((profile.org_id, profile.tbl_id, profile.itm_id))
