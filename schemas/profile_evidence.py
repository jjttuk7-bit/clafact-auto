"""Immutable official-coordinate evidence required for verification profiles."""

from pydantic import BaseModel, ConfigDict, Field


class OfficialCoordinateEvidenceSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    org_id: str = Field(min_length=1)
    tbl_id: str = Field(min_length=1)
    itm_id: str = Field(min_length=1)
    prd_se: str = Field(min_length=1)
    dimension_codes: dict[str, str] = Field(min_length=1)


class ProfileEvidenceSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str = Field(min_length=1)
    official_coordinate: OfficialCoordinateEvidenceSchema
    sample_period: str = Field(min_length=1)
    sample_value: float
    unit: str = Field(min_length=1)
    snapshot_path: str = Field(min_length=1)
    snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

