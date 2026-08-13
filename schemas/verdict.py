"""Final auditable verification result contract."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from schemas.evidence import EvidenceCellSchema
from schemas.pipeline_trace import PipelineTraceSchema


class OfficialPublicationProvenanceSchema(BaseModel):
    """Official publication evidence used for the article-date safeguard."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["VERIFIED", "UNRESOLVED", "FETCH_FAILED"]
    published_at: date | None = None
    pub_period: str | None = None
    pub_date_text: str | None = None
    publication_method_url: str | None = None
    source_url: str
    retrieved_at: str
    content_hash: str

class OfficialValueProvenanceSchema(BaseModel):
    """Auditable source identity for one fetched official evidence value."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_key: str
    source: Literal["SNAPSHOT", "API", "NONE"]
    content_hash: str
    publication: OfficialPublicationProvenanceSchema | None = None


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