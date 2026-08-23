"""Export canonical official verification JSONL as a Korean audit CSV."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.claim_registry_loader import load_claim_registry
from core.official_run_csv import write_official_run_csv


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--code-version", required=True)
    parser.add_argument("--data-version", required=True)
    args = parser.parse_args(argv)
    loaded = load_claim_registry(args.registry)
    if loaded.errors:
        parser.error(f"REGISTRY_ERRORS:{len(loaded.errors)}")
    results = _load_results(args.results)
    write_official_run_csv(
        loaded.records,
        results,
        args.output,
        code_version=args.code_version,
        data_version=args.data_version,
    )
    print(json.dumps({"rows": len(results), "output": str(args.output)}, ensure_ascii=False))
    return 0


def _load_results(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"INVALID_OFFICIAL_RESULT_ROW:{line_number}")
        rows.append(payload)
    return rows


if __name__ == "__main__":
    raise SystemExit(main())
