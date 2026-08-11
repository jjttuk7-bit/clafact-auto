"""Write a reproducible PROFILE_NOT_FOUND priority queue from E2E artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.profile_priority_queue import build_profile_priority_queue


def _load_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--e2e-results", required=True, type=Path)
    parser.add_argument("--derived-registry", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    queue = build_profile_priority_queue(
        _load_jsonl(args.e2e_results), _load_jsonl(args.derived_registry)
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(queue, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Priority groups: {len(queue)}")
    print(f"Output: {args.output}")


if __name__ == "__main__":
    main()
