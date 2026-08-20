"""CLI for creating a reproducible HOLD review candidate set."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.hold_goldset import write_hold_goldset


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_results", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--seed", default="20260820")
    args = parser.parse_args()
    report = write_hold_goldset(args.input_results, args.output_dir, seed=args.seed)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
