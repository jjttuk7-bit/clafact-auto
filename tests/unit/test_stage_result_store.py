import pytest

from core.stage_result_store import StageResultStore
from schemas.stage_result import StageResultSchema


def _result(*, attempt: int = 1) -> StageResultSchema:
    return StageResultSchema(
        parent_claim_id="P-001",
        child_claim_id="P-001-01",
        stage="CLAIM_SPLIT",
        status="PASS",
        reason_code=None,
        input_hash="a" * 64,
        output_ref="02_claim_lineage.jsonl#P-001-01",
        started_at="2026-08-22T10:00:00+09:00",
        finished_at="2026-08-22T10:00:01+09:00",
        code_version="abc123",
        data_version="baseline-v1",
        attempt=attempt,
    )


def test_stage_result_store_round_trips_jsonl(tmp_path) -> None:
    path = tmp_path / "03_stage_events.jsonl"
    store = StageResultStore(path)

    store.append(_result())

    assert store.load() == [_result()]


def test_stage_result_store_rejects_duplicate_stage_attempt(tmp_path) -> None:
    store = StageResultStore(tmp_path / "03_stage_events.jsonl")
    store.append(_result())

    with pytest.raises(ValueError, match="DUPLICATE_STAGE_RESULT"):
        store.append(_result())


def test_stage_result_store_allows_explicit_later_attempt(tmp_path) -> None:
    store = StageResultStore(tmp_path / "03_stage_events.jsonl")
    store.append(_result(attempt=1))
    store.append(_result(attempt=2))

    assert [event.attempt for event in store.load()] == [1, 2]

