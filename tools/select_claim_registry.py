"""Write an exact, bounded Claim Registry subset in requested ID order."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.claim_registry_loader import load_claim_registry


MAX_GROUP_SIZE = 20


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_registry", type=Path)
    parser.add_argument("output_registry", type=Path)
    parser.add_argument("--claim-id", dest="claim_ids", action="append", default=[])
    args = parser.parse_args()

    requested = list(dict.fromkeys(args.claim_ids))
    if not requested:
        parser.error("one or more explicit --claim-id values are required")
    if len(requested) != len(args.claim_ids):
        parser.error("duplicate --claim-id value")
    if len(requested) > MAX_GROUP_SIZE:
        parser.error(f"at most {MAX_GROUP_SIZE} --claim-id values are allowed")
    if args.output_registry.exists():
        parser.error("output already exists; choose a new output path")

    loaded = load_claim_registry(args.source_registry)
    if loaded.errors:
        parser.error(f"Registry contains {len(loaded.errors)} invalid row(s)")
    by_id = {record.claim.claim_id: record for record in loaded.records}
    missing = [claim_id for claim_id in requested if claim_id not in by_id]
    if missing:
        parser.error("Claim ID not found: " + ", ".join(missing))

    selected = [by_id[claim_id] for claim_id in requested]
    args.output_registry.parent.mkdir(parents=True, exist_ok=True)
    args.output_registry.write_text(
        "".join(record.model_dump_json() + "\n" for record in selected),
        encoding="utf-8",
    )
    print(json.dumps({"selected": len(selected), "output": str(args.output_registry)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
