"""Create auditable evidence coordinates from registered verification profiles."""

from dataclasses import dataclass
from typing import Literal

from core.unit_normalizer import compatible_units
from schemas.claim import ClaimSchema
from schemas.evidence import EvidenceCellSchema
from schemas.verification_profile import VerificationProfileSchema


EvidenceResolutionStatus = Literal["CONFIRMED", "HOLD"]


@dataclass(frozen=True)
class EvidenceResolution:
    """A profile-backed evidence cell or a safe reason to stop verification."""

    status: EvidenceResolutionStatus
    evidence_cell: EvidenceCellSchema | None = None
    reason_code: str | None = None


def resolve_profile_evidence(
    claim: ClaimSchema,
    profile: VerificationProfileSchema,
    *,
    period: str | None,
) -> EvidenceResolution:
    """Build one official coordinate without fetching or generating a KOSIS value."""
    if claim.parse_status != "AUTO_OK":
        return EvidenceResolution(status="HOLD", reason_code="CLAIM_NOT_AUTO_OK")
    if not period:
        return EvidenceResolution(status="HOLD", reason_code="EVIDENCE_PERIOD_MISSING")
    if not all((profile.org_id, profile.tbl_id, profile.itm_id, profile.prd_se, profile.unit)):
        return EvidenceResolution(
            status="HOLD", reason_code="PROFILE_COORDINATE_INCOMPLETE"
        )
    if claim.frequency is not None and _normalize_frequency(claim.frequency) != _normalize_frequency(profile.prd_se):
        return EvidenceResolution(
            status="HOLD", reason_code="EVIDENCE_FREQUENCY_MISMATCH"
        )
    if (
        claim.unit is not None
        and profile.calculation_type == "DIRECT_VALUE"
        and not compatible_units(claim.unit, profile.unit)
    ):
        return EvidenceResolution(status="HOLD", reason_code="EVIDENCE_UNIT_MISMATCH")

    cell = EvidenceCellSchema(
        org_id=profile.org_id,
        tbl_id=profile.tbl_id,
        itm_id=profile.itm_id,
        dimension_codes=profile.dimension_codes,
        prd_se=profile.prd_se,
        prd_de=period,
        unit=profile.unit,
        canonical_key=_canonical_key(profile, period),
        status="CONFIRMED",
    )
    return EvidenceResolution(status="CONFIRMED", evidence_cell=cell)


def _canonical_key(profile: VerificationProfileSchema, period: str) -> str:
    """Encode only deterministic registered coordinates in a stable order."""
    base = (
        f"ORG={profile.org_id}|TBL={profile.tbl_id}|ITM={profile.itm_id}"
        f"|PRD_SE={profile.prd_se}|PRD_DE={period}"
    )
    if not profile.dimension_codes:
        return base
    dimensions = ",".join(
        f"{key}:{value}" for key, value in sorted(profile.dimension_codes.items())
    )
    return f"{base}|DIMS={dimensions}"


def _normalize_frequency(value: str) -> str:
    """Map supported English and Korean frequency labels to KOSIS codes."""
    normalized = value.strip().casefold()
    return {"monthly": "M", "month": "M", "월": "M", "m": "M", "yearly": "Y", "annual": "Y", "년": "Y", "y": "Y"}.get(normalized, value)