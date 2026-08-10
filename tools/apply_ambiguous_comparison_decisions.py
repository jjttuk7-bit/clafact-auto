"""Apply explicit JSONL ambiguous-comparison review decisions."""
import json
from pathlib import Path
import sys

from core.ambiguous_comparison_review import apply_review_decisions


def _read(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def main(source: Path, decisions: Path, target: Path) -> None:
    records = apply_review_decisions(_read(source), _read(decisions))
    target.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records), encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
