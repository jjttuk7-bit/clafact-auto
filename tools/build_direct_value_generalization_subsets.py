"""Build leakage-safe Registry files for direct-value rule evaluation."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path
import sys
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.claim_registry_loader import load_claim_registry
from schemas.claim_registry import ClaimRegistryRecord


def select_registry_records(
    records: Iterable[ClaimRegistryRecord], claim_ids: Iterable[str]
) -> list[ClaimRegistryRecord]:
    by_id: dict[str, ClaimRegistryRecord] = {}
    for record in records:
        claim_id = record.claim.claim_id
        if claim_id in by_id:
            raise ValueError(f"GENERALIZATION_REGISTRY_DUPLICATE_CLAIM:{claim_id}")
        by_id[claim_id] = record
    selected: list[ClaimRegistryRecord] = []
    for claim_id in claim_ids:
        if claim_id not in by_id:
            raise ValueError(f"GENERALIZATION_REGISTRY_CLAIM_NOT_FOUND:{claim_id}")
        selected.append(by_id[claim_id])
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline_csv", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("registry", type=Path, nargs="+")
    args = parser.parse_args()
    rows = _read_csv(args.baseline_csv)
    loaded: list[ClaimRegistryRecord] = []
    for path in args.registry:
        result = load_claim_registry(path)
        if result.errors:
            raise ValueError(f"GENERALIZATION_REGISTRY_INVALID:{path}:{len(result.errors)}")
        loaded.extend(result.records)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {
        "baseline_csv": str(args.baseline_csv.resolve()),
        "baseline_sha256": sha256(args.baseline_csv.read_bytes()).hexdigest(),
        "sets": {},
    }
    for split in ("RULE_DISCOVERY", "INTERMEDIATE_VALIDATION", "FINAL_BLIND"):
        claim_ids = [
            str(row.get("자식Claim번호") or row.get("원본부모Claim번호") or "")
            for row in rows if row.get("사용집합") == split
        ]
        selected = select_registry_records(loaded, claim_ids)
        output = args.output_dir / f"{split.lower()}.jsonl"
        output.write_text(
            "".join(record.model_dump_json() + "\n" for record in selected),
            encoding="utf-8",
        )
        manifest["sets"][split] = {
            "claim_count": len(selected),
            "article_count": len({record.article_id for record in selected}),
            "reason_counts": dict(Counter(
                row.get("기준선사유", "") for row in rows if row.get("사용집합") == split
            )),
            "path": str(output.resolve()),
            "sha256": sha256(output.read_bytes()).hexdigest(),
        }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


if __name__ == "__main__":
    main()
