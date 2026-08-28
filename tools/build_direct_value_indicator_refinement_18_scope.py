"""Build the exact indicator-refinement 18-Claim audit and corrected direct-Claim run input."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import csv
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.claim_registry_loader import load_claim_registry
from core.direct_value_indicator_refinement_scope import build_indicator_refinement_scope


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger_csv", type=Path)
    parser.add_argument("registry_jsonl", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--expected-scope-count", type=int, default=18)
    parser.add_argument("--expected-run-count", type=int, default=6)
    args = parser.parse_args()

    with args.ledger_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        ledger = list(csv.DictReader(handle))
    loaded = load_claim_registry(args.registry_jsonl)
    if loaded.errors:
        raise ValueError(f"INDICATOR_REFINEMENT_REGISTRY_ERRORS:{len(loaded.errors)}")
    scope = build_indicator_refinement_scope(
        ledger, loaded.records,
        expected_scope_count=args.expected_scope_count,
        expected_run_count=args.expected_run_count,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    input_path = args.output_dir / "input_registry.jsonl"
    input_path.write_text(
        "".join(
            json.dumps(record.model_dump(mode="json"), ensure_ascii=False, sort_keys=True) + "\n"
            for record in scope.records
        ),
        encoding="utf-8",
    )
    manifest = {
        "scope_count": len(scope.decisions),
        "run_count": len(scope.records),
        "decision_counts": scope.decision_counts,
        "manifest_sha256": scope.manifest_sha256,
        "run_claim_ids": [record.claim.claim_id for record in scope.records],
        "decisions": [asdict(item) for item in scope.decisions],
        "input_registry": str(input_path.resolve()),
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({key: value for key, value in manifest.items() if key != "decisions"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
