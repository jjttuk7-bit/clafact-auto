"""Presentation-ready, deterministic grouping of pipeline trace events."""
from schemas.pipeline_trace import PipelineTraceSchema

_BRANCHES = {
    '무슨 통계': {'PREPROCESS', 'SENTENCE_SPLIT', 'CLAIM_CANDIDATE_SELECTION', 'CLAIM_SPLIT', 'CLAIM_PARSE', 'SEMANTIC_MAPPING', 'CATALOG_SEARCH', 'HARD_GUARD', 'SEMANTIC_MATCH'},
    '어떤 데이터': {'EVIDENCE_CELL', 'OFFICIAL_VALUE_FETCH', 'OFFICIAL_AUTHOR_SEARCH', 'OFFICIAL_AUTHOR_FETCH'},
    '어떻게 검증': {'CALCULATION', 'VERDICT'},
}

def build_trace_summary(trace: PipelineTraceSchema) -> dict[str, list[dict[str, str | None]]]:
    summary = {branch: [] for branch in _BRANCHES}
    for event in trace.events:
        for branch, stages in _BRANCHES.items():
            if event.stage in stages:
                summary[branch].append(event.model_dump())
                break
    return summary
