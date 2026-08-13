from pathlib import Path
from core.claim_admissibility import classify_admissibility


def test_classifies_missing_required_slots_as_structural_hold() -> None:
    result = classify_admissibility("MISSING_REQUIRED_SLOTS:time", "HOLD")
    assert result.route == "STRUCTURAL_HOLD"
    assert result.reason_code == "MISSING_REQUIRED_SLOT"


def test_classifies_relative_time_as_context_required() -> None:
    result = classify_admissibility("'지난달'의 기준 시점이 제공되지 않아 시간을 확정할 수 없음", "HOLD")
    assert result.route == "CONTEXT_REQUIRED"
    assert result.reason_code == "RELATIVE_TIME_UNRESOLVED"


def test_classifies_downstream_kosis_hold_as_verifiable() -> None:
    result = classify_admissibility("NO_EVIDENCE_COORDINATE_CANDIDATE", "HOLD")
    assert result.route == "VERIFIABLE"
    assert result.reason_code == "KOSIS_STAGE_REACHED"


def test_classifies_publication_transport_failure_as_reached_kosis_stage() -> None:
    result = classify_admissibility("PUBLICATION_FETCH_FAILED", "HOLD")
    assert result.route == "VERIFIABLE"
    assert result.reason_code == "KOSIS_STAGE_REACHED"
