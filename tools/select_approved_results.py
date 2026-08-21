"""Select approved Structured Output rows by article id for bounded replay."""

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--article", action="append", required=True)
    args = parser.parse_args()
    selected = []
    for line in args.source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("article_id") in set(args.article):
            selected.append(row)
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in selected),
        encoding="utf-8",
    )
    print(json.dumps({"selected": len(selected), "destination": str(args.destination)}))


if __name__ == "__main__":
    main()
