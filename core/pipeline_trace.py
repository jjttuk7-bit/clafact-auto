"""Factory helpers for the immutable pipeline execution trace."""

from __future__ import annotations

from schemas.pipeline_trace import PipelineTraceSchema


class PipelineTrace:
    """Create a versioned trace before deterministic pipeline stages run."""

    @staticmethod
    def for_claim(
        claim_id: str,
        *,
        preprocess_version: str,
        claim_schema_version: str,
        semantic_standard_version: str = "1.0",
        kosis_catalog_version: str = "1.0",
        matching_version: str = "1.0",
        calculation_version: str = "1.0",
    ) -> PipelineTraceSchema:
        return PipelineTraceSchema(
            claim_id=claim_id,
            preprocess_version=preprocess_version,
            claim_schema_version=claim_schema_version,
            semantic_standard_version=semantic_standard_version,
            kosis_catalog_version=kosis_catalog_version,
            matching_version=matching_version,
            calculation_version=calculation_version,
        )