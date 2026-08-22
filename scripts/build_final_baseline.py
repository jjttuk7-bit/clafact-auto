"""Create the immutable 1,542-record final-completion baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.baseline_registry import build_baseline, validate_baseline, write_baseline
from core.claim_registry_loader import load_claim_registry


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry_path", type=Path)
    parser.add_argument("output_path", type=Path)
    args = parser.parse_args()

    registry = load_claim_registry(args.registry_path)
    if registry.errors:
        raise SystemExit("REGISTRY_LOAD_ERRORS")
    baseline = build_baseline(registry.records)
    validation = validate_baseline(baseline, expected_count=len(registry.records))
    if not validation.is_valid:
        raise SystemExit("INVALID_BASELINE")
    write_baseline(args.output_path, baseline)
    print(
        json.dumps(
            {
                "record_count": validation.record_count,
                "unique_parent_count": validation.unique_parent_count,
                "output_path": str(args.output_path),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

