"""Freeze coordinate/publication targets from the 230-row direct-value ledger."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.direct_value_coordinate_publication_scope import (
    FINAL_BLIND,
    INTERMEDIATE_VALIDATION,
    RULE_DISCOVERY,
    ScopeManifest,
    build_scope_manifest,
)


def build_scope_rows(
    ledger_rows: Iterable[dict[str, str]],
    registry_rows: Iterable[dict[str, Any]],
) -> tuple[ScopeManifest, dict[str, list[dict[str, Any]]]]:
    """Join the frozen ledger scope to exact Registry payloads."""

    manifest = build_scope_manifest(ledger_rows)
    registry_by_claim: dict[str, dict[str, Any]] = {}
    for row in registry_rows:
        claim = row.get("claim") if isinstance(row.get("claim"), dict) else {}
        claim_id = str(claim.get("claim_id") or "").strip()
        if not claim_id:
            continue
        if claim_id in registry_by_claim:
            raise ValueError(f"DIRECT_VALUE_SCOPE_REGISTRY_NOT_UNIQUE:{claim_id}")
        registry_by_claim[claim_id] = row

    subsets = {
        RULE_DISCOVERY: [],
        INTERMEDIATE_VALIDATION: [],
        FINAL_BLIND: [],
    }
    for item in manifest.records:
        row = registry_by_claim.get(item.claim_id)
        if row is None:
            raise ValueError(f"DIRECT_VALUE_SCOPE_REGISTRY_MISSING:{item.claim_id}")
        claim = row.get("claim") if isinstance(row.get("claim"), dict) else {}
        if str(claim.get("source_sentence") or "") != item.source_sentence:
            raise ValueError(f"DIRECT_VALUE_SCOPE_SOURCE_MISMATCH:{item.claim_id}")
        subsets[item.split_set].append(row)
    for rows in subsets.values():
        rows.sort(key=lambda row: str((row.get("claim") or {}).get("claim_id") or ""))
    return manifest, subsets


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger_csv", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("registry_jsonl", type=Path, nargs="+")
    args = parser.parse_args()

    ledger = _read_csv(args.ledger_csv)
    registry = [row for path in args.registry_jsonl for row in _read_jsonl(path)]
    manifest, subsets = build_scope_rows(ledger, registry)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        args.output_dir / "manifest.json",
        manifest.to_audit_dict(include_final_blind_source=False),
    )
    filenames = {
        RULE_DISCOVERY: "rule_discovery.jsonl",
        INTERMEDIATE_VALIDATION: "intermediate_validation.jsonl",
        FINAL_BLIND: "final_blind.jsonl",
    }
    for split_set, rows in subsets.items():
        _write_jsonl(args.output_dir / filenames[split_set], rows)
    print(
        json.dumps(
            {
                "target_count": len(manifest.records),
                "reason_counts": manifest.reason_counts,
                "split_counts": manifest.split_counts,
                "manifest_sha256": manifest.manifest_sha256,
            },
            ensure_ascii=False,
        )
    )


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
