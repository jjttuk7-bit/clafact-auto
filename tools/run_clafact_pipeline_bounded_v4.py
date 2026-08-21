"""Run target-aware CLAFACT workers with hard wall-clock isolation."""

from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import tools.run_clafact_pipeline_bounded as bounded_cli


def main() -> None:
    bounded_cli.WORKER_CLI = PROJECT_ROOT / "tools" / "run_clafact_pipeline_v4.py"
    bounded_cli.main()


if __name__ == "__main__":
    main()
