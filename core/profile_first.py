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
    return ProfileFirstResolution(status="MATCHED", profile=profile)


def _has_complete_coordinate(profile: VerificationProfileSchema) -> bool:
    """Defend callers against profile objects constructed without validation."""
    return all((profile.org_id, profile.tbl_id, profile.itm_id))
