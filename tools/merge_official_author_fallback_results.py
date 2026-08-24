"""Replace an exact bounded Claim subset in a larger canonical result JSONL."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence


def replace_claim_rows(
    baseline: Sequence[dict[str, Any]],
    improved: Sequence[dict[str, Any]],
    *,
    expected_replacements: int,
) -> list[dict[str, Any]]:
    if len(improved) != expected_replacements:
        raise ValueError("REPLACEMENT_COUNT_MISMATCH")
    improved_ids = [str(row.get("claim_id") or "") for row in improved]
    if any(not claim_id for claim_id in improved_ids) or len(set(improved_ids)) != len(improved_ids):
        raise ValueError("REPLACEMENT_IDS_INVALID")
    baseline_ids = [str(row.get("claim_id") or "") for row in baseline]
    if any(not claim_id for claim_id in baseline_ids) or len(set(baseline_ids)) != len(baseline_ids):
        raise ValueError("BASELINE_IDS_INVALID")
    missing = sorted(set(improved_ids) - set(baseline_ids))
    if missing:
        raise ValueError("REPLACEMENT_ID_NOT_FOUND:" + ",".join(missing))
    replacement_by_id = dict(zip(improved_ids, improved, strict=True))
    return [replacement_by_id.get(claim_id, row) for claim_id, row in zip(baseline_ids, baseline, strict=True)]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--improved", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-replacements", type=int, default=5)
    args = parser.parse_args(argv)
    baseline = _read_jsonl(args.baseline)
    improved = _read_jsonl(args.improved)
    merged = replace_claim_rows(
        baseline,
        improved,
        expected_replacements=args.expected_replacements,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in merged),
        encoding="utf-8",
    )
    temporary.replace(args.output)
    print(json.dumps({
        "baseline_count": len(baseline),
        "replacement_count": len(improved),
        "output_count": len(merged),
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


if __name__ == "__main__":
    raise SystemExit(main())
