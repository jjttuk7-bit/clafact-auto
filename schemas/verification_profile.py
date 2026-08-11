"""Strict, versioned official-coordinate profiles for claim verification."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class VerificationProfileSchema(BaseModel):
    """One exact official-value retrieval and calculation profile."""

    model_config = ConfigDict(extra="forbid")

    profile_id: str = Field(min_length=1)
    claim_key: str = Field(min_length=1)
    calculation_type: Literal[
        "DIRECT_VALUE",
        "DIFFERENCE",
        "GROWTH_RATE",
        "RATIO",
        "SHARE",
        "MULTIPLE",
        "RANK",
        "THRESHOLD",
    ]
    org_id: str = Field(min_length=1)
    tbl_id: str = Field(min_length=1)
    itm_id: str = Field(min_length=1)
    prd_se: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    dimension_codes: dict[str, str] = Field(default_factory=dict)
    frequency_constraint: str | None = None
    region_constraint: str | None = None
    population_constraint: str | None = None
    condition_constraint: dict[str, str] | None = None
    dimension_constraint: dict[str, str] | None = None
    dataset_version: str = Field(min_length=1)
    preprocess_version: str = Field(min_length=1)
    claim_schema_version: str = Field(min_length=1)
    semantic_standard_version: str = Field(min_length=1)
    kosis_catalog_version: str = Field(min_length=1)
    matching_version: str = Field(min_length=1)
    calculation_version: str = Field(min_length=1)
