from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.direct_value_coordinate_spec_registry import ledger_row_to_registry


DEFAULT_LEDGER = (
    PROJECT_ROOT
    / "deliverables"
    / "CLAFACT_AUTO_8번_직접값_최종마감_20260828"
    / "CLAFACT_AUTO_8번_직접값_230건_최종원장_20260828.csv"
)
DEFAULT_OUTPUT = PROJECT_ROOT / "artifacts" / "direct_value_type8_230_final_run"


def build_registry(
    ledger_path: Path,
    registry_path: Path,
    manifest_path: Path,
    *,
    expected_count: int = 230,
) -> dict[str, object]:
    with ledger_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != expected_count:
        raise ValueError(f"TYPE8_230_LEDGER_COUNT_MISMATCH:{len(rows)}:{expected_count}")
    records = []
    seen: set[str] = set()
    for row in rows:
        record = ledger_row_to_registry(row).model_copy(
            update={"source_ref": "direct_value_type8_230_final_run"}
        )
        claim_id = record.claim.claim_id
        if not claim_id or claim_id in seen:
            raise ValueError(f"TYPE8_230_CLAIM_ID_INVALID:{claim_id}")
        seen.add(claim_id)
        records.append(record)
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_text = "".join(
        json.dumps(record.model_dump(mode="json"), ensure_ascii=False, sort_keys=True) + "\n"
        for record in records
    )
    registry_path.write_text(registry_text, encoding="utf-8")
    result = {
        "record_count": len(records),
        "input": str(ledger_path.resolve()),
        "input_sha256": sha256(ledger_path.read_bytes()).hexdigest(),
        "registry": str(registry_path.resolve()),
        "registry_sha256": sha256(registry_path.read_bytes()).hexdigest(),
        "claim_id_sha256": sha256(
            json.dumps(sorted(seen), ensure_ascii=False).encode("utf-8")
        ).hexdigest(),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the fixed 230-Claim type-8 Registry.")
    parser.add_argument("ledger", type=Path, nargs="?", default=DEFAULT_LEDGER)
    parser.add_argument("output_dir", type=Path, nargs="?", default=DEFAULT_OUTPUT)
    parser.add_argument("--expected-count", type=int, default=230)
    args = parser.parse_args()
    result = build_registry(
        args.ledger,
        args.output_dir / "input_registry.jsonl",
        args.output_dir / "input_manifest.json",
        expected_count=args.expected_count,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
