"""Build a JSONL queue for explicit ambiguous-comparison review."""
import json
from pathlib import Path
import sys

from core.ambiguous_comparison_review import build_review_queue


def main(source: Path, target: Path) -> None:
    records = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line]
    rows = build_review_queue(records)
    target.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
