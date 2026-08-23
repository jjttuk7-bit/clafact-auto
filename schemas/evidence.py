"""Evidence coordinate and deterministic calculation contracts."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class EvidenceCellSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    org_id: str
    tbl_id: str
    itm_id: str
    obj_id: str | None = None
    member_code: str | None = None
    dimension_members: dict[str, str] = Field(default_factory=dict)
    dimension_codes: dict[str, str] = Field(default_factory=dict)
    prd_se: str
    prd_de: str
    unit: str | None = None
    canonical_key: str
    status: Literal["CONFIRMED", "UNRESOLVED", "AMBIGUOUS"]


class CalculationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    calculation_type: Literal[
        "DIRECT_VALUE", "DIFFERENCE", "SUM_DIFFERENCE", "GROWTH_RATE",
        "RATIO", "SHARE", "MULTIPLE", "RANK", "THRESHOLD",
        "RECORD_HIGH", "RECORD_LOW",
    ]
    required_cells: list[EvidenceCellSchema] = Field(default_factory=list)
    operator: str | None = None
    tolerance: float | None = None
    literal_values: list[float] = Field(default_factory=list)
