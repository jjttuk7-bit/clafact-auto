import pytest

from core.ambiguous_comparison_review import apply_review_decisions, build_review_queue


def _record(reason: str = "AMBIGUOUS_COMPARISON") -> dict[str, object]:
    return {"article_id": "A1", "sentence_id": "S1", "claim": {"source_sentence": "수출은 3% 감소했다.", "parse_status": "HOLD", "parse_reason": reason, "comparison": None, "calculation": None}}


def test_build_review_queue_selects_only_ambiguous_comparisons() -> None:
    queue = build_review_queue([_record(), _record("OTHER")])
    assert len(queue) == 1
    assert queue[0]["source_key"] == "A1:S1"


def test_apply_approved_decision_updates_only_new_result_stream() -> None:
    result = apply_review_decisions([_record()], [{"source_key": "A1:S1", "status": "APPROVED", "comparison": {"operator": "DECREASE"}, "calculation": "GROWTH_RATE"}])
    assert result[0]["claim"]["parse_status"] == "AUTO_OK"
    assert result[0]["claim"]["comparison"] == {"operator": "DECREASE"}


def test_apply_decision_rejects_unknown_source_key() -> None:
    with pytest.raises(ValueError, match="Unknown review source key"):
        apply_review_decisions([_record()], [{"source_key": "A9:S9", "status": "REJECTED"}])
