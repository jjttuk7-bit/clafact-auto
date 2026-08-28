"""Write an audit-safe compact JSONL from the large live 94-Claim response."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.direct_value_coordinate_94_compaction import compact_coordinate_result


DEFAULT_INPUT = PROJECT_ROOT / "artifacts" / "direct_value_coordinate_94_20260828" / "live_run_after_common_rules" / "claim_verification_results.jsonl"
DEFAULT_OUTPUT = PROJECT_ROOT / "artifacts" / "direct_value_coordinate_94_20260828" / "claim_verification_results_compact.jsonl"


def compact_file(source: Path, destination: Path, *, expected_count: int = 94) -> dict[str, object]:
    rows = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    compact = [compact_coordinate_result(row) for row in rows]
    ids = [str(row.get("parent_claim_id") or row.get("claim_id") or "") for row in compact]
    if len(compact) != expected_count or len(set(ids)) != expected_count or any(not value for value in ids):
        raise ValueError("DIRECT_VALUE_94_COMPACT_COVERAGE_MISMATCH")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in compact), encoding="utf-8")
    return {
        "record_count": len(compact),
        "source_sha256": sha256(source.read_bytes()).hexdigest(),
        "compact_sha256": sha256(destination.read_bytes()).hexdigest(),
        "destination": str(destination),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(compact_file(args.source, args.output), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
