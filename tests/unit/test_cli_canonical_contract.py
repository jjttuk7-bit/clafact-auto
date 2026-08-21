from pathlib import Path


CLI = Path("tools/run_clafact_pipeline.py")


def test_registry_cli_uses_the_canonical_record_runtime() -> None:
    source = CLI.read_text(encoding="utf-8")

    assert "from core.canonical_pipeline import build_canonical_pipeline" in source
    assert "runtime.verify_record(" in source
    assert "run_admission_recovery_batch_v3" not in source
    assert "build_run_report" in source
    assert "--stored-slots-only" in source
