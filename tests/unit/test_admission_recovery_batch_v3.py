from core.admission_recovery_batch_v3 import run_admission_recovery_batch_v3


def test_v3_batch_entrypoint_is_callable() -> None:
    assert callable(run_admission_recovery_batch_v3)
