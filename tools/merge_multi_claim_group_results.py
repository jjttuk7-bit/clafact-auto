"""Merge a bounded improvement checkpoint into a frozen multi-Claim baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.multi_claim_group_harness import (
    GoldClaimCase,
    load_gold_cases,
    write_multi_claim_evaluation_csv,
)


def merge_results(
    cases: list[GoldClaimCase],
    baseline: dict[str, dict[str, Any]],
    improved: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    combined = {**baseline, **improved}
    missing = [case.parent_claim_id for case in cases if case.parent_claim_id not in combined]
    if missing:
        raise ValueError(f"MISSING_MULTI_CLAIM_RESULT:{','.join(missing)}")
    return [combined[case.parent_claim_id] for case in cases]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--goldset", type=Path, required=True)
    parser.add_argument("--baseline-checkpoint", type=Path, required=True)
    parser.add_argument("--improved-checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--code-version", required=True)
    parser.add_argument("--data-version", required=True)
    args = parser.parse_args(argv)

    cases = load_gold_cases(args.goldset)
    baseline = _load_results(args.baseline_checkpoint)
    improved = _load_results(args.improved_checkpoint)
    results = merge_results(cases, baseline, improved)
    write_multi_claim_evaluation_csv(
        cases,
        results,
        args.output,
        code_version=args.code_version,
        data_version=args.data_version,
    )
    _write_jsonl(args.output.with_suffix(".jsonl"), results)
    print(
        json.dumps(
            {
                "parents": len(cases),
                "baseline_parents": len(baseline),
                "improved_parents": len(improved),
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


def _load_results(path: Path) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        claim_id = str(payload.get("claim_id") or "")
        result = payload.get("result")
        if not claim_id or not isinstance(result, dict):
            raise ValueError(f"INVALID_CHECKPOINT_ROW:{line_number}")
        results[claim_id] = result
    return results


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    temporary.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
