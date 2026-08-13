"""Final auditable verification result contract."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from schemas.evidence import EvidenceCellSchema
from schemas.pipeline_trace import PipelineTraceSchema


class OfficialValueProvenanceSchema(BaseModel):
    """Auditable source identity for one fetched official evidence value."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_key: str
    source: Literal["SNAPSHOT", "API", "NONE"]
    content_hash: str


class VerdictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    claim_value: float | None = None
    evidence_values: list[float] = Field(default_factory=list)
    calculated_value: float | None = None
    verdict: Literal["MATCH", "MISMATCH", "UNDETERMINED"]
    route_status: Literal["AUTO", "HOLD", "HUMAN_REVIEW"]
    reason_code: str
    explanation: str
    evidence_cells: list[EvidenceCellSchema] = Field(default_factory=list)
    official_value_provenance: list[OfficialValueProvenanceSchema] = Field(
        default_factory=list
    )
    execution_trace: PipelineTraceSchema | None = None
    dataset_version: str
    preprocess_version: str = "1.0"
    claim_schema_version: str = "1.0"
    semantic_standard_version: str
    kosis_catalog_version: str
    matching_version: str
    calculation_version: str