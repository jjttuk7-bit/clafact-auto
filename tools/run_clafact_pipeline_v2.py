"""Run the slot-validated CLAFACT Registry pipeline through live KOSIS."""

from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.admission_recovery_batch_v2 import run_admission_recovery_batch_v2
import tools.run_clafact_pipeline as pipeline_cli


def main() -> None:
    pipeline_cli.run_admission_recovery_batch = run_admission_recovery_batch_v2
    pipeline_cli.main()


if __name__ == "__main__":
    main()
