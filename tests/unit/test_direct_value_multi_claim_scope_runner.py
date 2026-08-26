from pathlib import Path

from config.settings import Settings
from tools import run_direct_value_multi_claim_scope as runner


def test_grouping_ambiguity_is_not_parent_pass() -> None:
    status, reason = runner._grouping_parent_status([{
        "recovery_action": "MULTI_CLAIM_SPLIT",
        "terminal_status": "HUMAN_REVIEW",
        "reason_code": "GROUPING_AMBIGUOUS",
    }])
    assert status == "HUMAN_REVIEW"
    assert reason == "GROUPING_AMBIGUOUS"


def test_execution_signature_includes_runtime_model() -> None:
    first = runner._execution_signature("SOURCE", Settings(openai_model="model-a"))
    second = runner._execution_signature("SOURCE", Settings(openai_model="model-b"))
    assert first != second


def test_execution_signature_changes_with_semantic_data(tmp_path: Path, monkeypatch) -> None:
    semantic = tmp_path / "data/semantic_standard"
    semantic.mkdir(parents=True)
    standard = semantic / "standard.json"
    standard.write_text('{"version": 1}', encoding="utf-8")
    monkeypatch.setattr(runner, "PROJECT_ROOT", tmp_path)
    settings = Settings(openai_model="model-a")

    first = runner._execution_signature("SOURCE", settings)
    standard.write_text('{"version": 2}', encoding="utf-8")
    second = runner._execution_signature("SOURCE", settings)

    assert first != second
