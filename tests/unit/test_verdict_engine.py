from core.verdict_engine import make_verdict


def test_match_within_tolerance() -> None:
    assert make_verdict("C1", 70.0, [70.01], 70.01, tolerance=0.02).verdict == "MATCH"


def test_mismatch_outside_tolerance() -> None:
    assert make_verdict("C1", 70.0, [71.0], 71.0, tolerance=0.02).verdict == "MISMATCH"


def test_missing_value_routes_hold() -> None:
    result = make_verdict("C1", 70.0, [], None)
    assert result.verdict == "UNDETERMINED"
    assert result.route_status == "HOLD"


def test_make_verdict_carries_pipeline_trace_versions() -> None:
    from core.pipeline_trace import PipelineTrace

    trace = PipelineTrace.for_claim(
        "C1",
        preprocess_version="preprocess-2",
        claim_schema_version="schema-3",
        semantic_standard_version="standard-4",
        kosis_catalog_version="catalog-5",
        matching_version="matching-6",
        calculation_version="calculation-7",
    ).pass_stage("CLAIM_PARSE", output_ref="C1")

    result = make_verdict("C1", 70.0, [70.0], 70.0, trace=trace)

    assert result.execution_trace == trace
    assert result.preprocess_version == "preprocess-2"
    assert result.claim_schema_version == "schema-3"
    assert result.semantic_standard_version == "standard-4"
    assert result.kosis_catalog_version == "catalog-5"
    assert result.matching_version == "matching-6"
    assert result.calculation_version == "calculation-7"

def test_make_verdict_always_records_verdict_stage() -> None:
    result = make_verdict('C1', 70.0, [70.0], 70.0)
    assert result.execution_trace is not None
    assert result.execution_trace.events[-1].stage == 'VERDICT'
