"""Build the exact 48-record Registry input from the reclassification ledger."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.claim_registry_loader import load_claim_registry
from core.direct_value_recovered_scope import build_recovered_direct_scope


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger_csv", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("registry_jsonl", type=Path, nargs="+")
    parser.add_argument("--expected-count", type=int, default=48)
    args = parser.parse_args()

    with args.ledger_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        ledger = list(csv.DictReader(handle))
    registry = []
    errors = []
    for path in args.registry_jsonl:
        loaded = load_claim_registry(path)
        registry.extend(loaded.records)
        errors.extend(loaded.errors)
    if errors:
        raise ValueError(f"RECOVERED_DIRECT_REGISTRY_LOAD_ERRORS:{len(errors)}")
    scope = build_recovered_direct_scope(
        ledger,
        registry,
        expected_count=args.expected_count,
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
        "input_count": len(scope.records),
        "claim_ids": list(scope.claim_ids),
        "manifest_sha256": scope.manifest_sha256,
        "input_registry": str(input_path.resolve()),
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
