import pytest

from core.registry_stage_runner import (
    RegistryStageRunner,
    StageDefinition,
    StageOutcome,
)
from core.stage_result_store import StageResultStore


def test_stage_runner_resumes_valid_checkpoints_and_reruns_changed_stage(tmp_path) -> None:
    calls = {"parse": 0, "semantic": 0}

    def parse(payload: object) -> StageOutcome:
        calls["parse"] += 1
        return StageOutcome(status="PASS", output={"claim": payload})

    def semantic(payload: object) -> StageOutcome:
        calls["semantic"] += 1
        return StageOutcome(status="PASS", output={"concept": "고용", "prior": payload})

    store = StageResultStore(tmp_path / "03_stage_events.jsonl")
    runner = RegistryStageRunner(tmp_path / "checkpoints", store)
    stages_v1 = [
        StageDefinition("CLAIM_PARSE", parse, code_version="parse-v1", data_version="claim-v1"),
        StageDefinition("SEMANTIC_MAPPING", semantic, code_version="semantic-v1", data_version="standard-v1"),
    ]

    first = runner.run(
        parent_claim_id="P-001",
        child_claim_id="P-001-01",
        initial_input={"sentence": "취업자는 10만 명 증가했다."},
        stages=stages_v1,
    )
    second = runner.run(
        parent_claim_id="P-001",
        child_claim_id="P-001-01",
        initial_input={"sentence": "취업자는 10만 명 증가했다."},
        stages=stages_v1,
    )
    stages_v2 = [
        stages_v1[0],
        StageDefinition("SEMANTIC_MAPPING", semantic, code_version="semantic-v2", data_version="standard-v1"),
    ]
    third = runner.run(
        parent_claim_id="P-001",
        child_claim_id="P-001-01",
        initial_input={"sentence": "취업자는 10만 명 증가했다."},
        stages=stages_v2,
    )

    assert first.completed_stage_count == 2
    assert second.resumed_stage_count == 2
    assert third.resumed_stage_count == 1
    assert calls == {"parse": 1, "semantic": 2}
    assert [event.attempt for event in store.load()] == [1, 1, 2]


def test_stage_runner_stops_before_downstream_after_rework(tmp_path) -> None:
    downstream_called = False

    def needs_rework(payload: object) -> StageOutcome:
        return StageOutcome(
            status="REWORK",
            output=payload,
            reason_code="MISSING_REQUIRED_SLOTS:time",
        )

    def downstream(payload: object) -> StageOutcome:
        nonlocal downstream_called
        downstream_called = True
        return StageOutcome(status="PASS", output=payload)

    runner = RegistryStageRunner(
        tmp_path / "checkpoints",
        StageResultStore(tmp_path / "03_stage_events.jsonl"),
    )
    result = runner.run(
        parent_claim_id="P-001",
        child_claim_id="P-001-01",
        initial_input={"sentence": "지난달 증가했다."},
        stages=[
            StageDefinition("CLAIM_PARSE", needs_rework, code_version="v1", data_version="v1"),
            StageDefinition("SEMANTIC_MAPPING", downstream, code_version="v1", data_version="v1"),
        ],
    )

    assert result.terminal_status == "REWORK"
    assert result.reason_code == "MISSING_REQUIRED_SLOTS:time"
    assert downstream_called is False


def test_stage_runner_rejects_hold_without_an_official_attempt(tmp_path) -> None:
    runner = RegistryStageRunner(
        tmp_path / "checkpoints",
        StageResultStore(tmp_path / "03_stage_events.jsonl"),
    )

    with pytest.raises(ValueError, match="HOLD_REQUIRES_OFFICIAL_ATTEMPT"):
        runner.run(
            parent_claim_id="P-001",
            child_claim_id="P-001-01",
            initial_input={"claim": "test"},
            stages=[
                StageDefinition(
                    "CATALOG_SEARCH",
                    lambda payload: StageOutcome(
                        status="HOLD",
                        output=payload,
                        reason_code="KOSIS_CATALOG_UNAVAILABLE",
                        official_attempted=False,
                    ),
                    code_version="v1",
                    data_version="v1",
                    official_lookup=True,
                )
            ],
        )

