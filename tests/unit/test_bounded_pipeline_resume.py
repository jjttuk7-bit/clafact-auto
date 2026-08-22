from pathlib import Path

from tools.run_clafact_pipeline_bounded import load_checkpoint, write_checkpoint


BOUNDED_CLI = Path("tools/run_clafact_pipeline_bounded.py")
SOURCE_ROW = {"article_id": "A1", "claim": {"claim_id": "C1"}}
RUN_SIGNATURE = {"runner_version": "test-v1", "stored_slots_only": True}



def test_parent_checkpoint_round_trips_all_derived_rows(tmp_path) -> None:
    rows = [
        {"claim_id": "child-1", "terminal_status": "AUTO"},
        {"claim_id": "child-2", "terminal_status": "HOLD"},
    ]

    write_checkpoint(tmp_path, 7, rows, source_row=SOURCE_ROW, run_signature=RUN_SIGNATURE)

    assert load_checkpoint(tmp_path, 7, source_row=SOURCE_ROW, run_signature=RUN_SIGNATURE) == rows


def test_corrupt_checkpoint_is_not_treated_as_complete(tmp_path) -> None:
    checkpoint_dir = tmp_path / "checkpoints"
    checkpoint_dir.mkdir()
    (checkpoint_dir / "00007.jsonl").write_text("not-json\n", encoding="utf-8")

    assert load_checkpoint(tmp_path, 7, source_row=SOURCE_ROW, run_signature=RUN_SIGNATURE) is None


def test_bounded_runner_forwards_stored_slots_only_policy() -> None:
    source = BOUNDED_CLI.read_text(encoding="utf-8")

    assert 'parser.add_argument("--stored-slots-only", action="store_true")' in source
    assert 'command.append("--stored-slots-only")' in source


def test_checkpoint_is_invalid_when_input_row_changes(tmp_path) -> None:
    rows = [{"claim_id": "C1", "terminal_status": "AUTO"}]
    write_checkpoint(tmp_path, 7, rows, source_row=SOURCE_ROW, run_signature=RUN_SIGNATURE)

    changed = {"article_id": "A1", "claim": {"claim_id": "DIFFERENT"}}

    assert load_checkpoint(tmp_path, 7, source_row=changed, run_signature=RUN_SIGNATURE) is None


def test_checkpoint_is_invalid_when_execution_policy_changes(tmp_path) -> None:
    rows = [{"claim_id": "C1", "terminal_status": "AUTO"}]
    write_checkpoint(tmp_path, 7, rows, source_row=SOURCE_ROW, run_signature=RUN_SIGNATURE)

    changed = {**RUN_SIGNATURE, "stored_slots_only": False}

    assert load_checkpoint(
        tmp_path, 7, source_row=SOURCE_ROW, run_signature=changed
    ) is None
