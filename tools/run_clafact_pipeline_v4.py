"""Run target-aware recovery with repeated-domain semantic standards."""

from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.admission_recovery_batch_v3 import run_admission_recovery_batch_v3
from core.official_engine_factory_v2 import build_official_evidence_service_v2
import tools.run_clafact_pipeline as pipeline_cli


OVERLAY_PATH = Path("data/semantic_standard/concept_overlay_v2.json")


def _build_service(paths, *, kosis_api_key, live_time_budget_seconds=45.0):
    return build_official_evidence_service_v2(
        paths,
        overlay_path=OVERLAY_PATH,
        kosis_api_key=kosis_api_key,
        live_time_budget_seconds=live_time_budget_seconds,
    )


def main() -> None:
    pipeline_cli.run_admission_recovery_batch = run_admission_recovery_batch_v3
    pipeline_cli.build_official_evidence_service = _build_service
    pipeline_cli.main()


if __name__ == "__main__":
    main()
