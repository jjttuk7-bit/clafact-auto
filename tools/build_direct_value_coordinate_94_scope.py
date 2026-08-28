"""Freeze the 94 direct-value Claims stopped at the coordinate guard boundary."""

from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.direct_value_coordinate_94_scope import build_coordinate_94_scope


DEFAULT_INPUT = (
    PROJECT_ROOT
    / "deliverables"
    / "CLAFACT_AUTO_직접값176_전체좌표탐색_20260828"
    / "CLAFACT_AUTO_직접값176_단계별평가표.csv"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "artifacts"
    / "direct_value_coordinate_94_20260828"
    / "scope.json"
)


def build_scope_artifact(
    input_csv: Path,
    output_json: Path,
    *,
    expected_count: int = 94,
) -> dict[str, object]:
    with input_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    scope = build_coordinate_94_scope(rows, expected_count=expected_count)
    payload = scope.to_dict()
    payload.update({
        "scope_count": len(scope.records),
        "input_path": _manifest_path(input_csv),
        "input_sha256": sha256(input_csv.read_bytes()).hexdigest(),
    })
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def _manifest_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_csv", type=Path, nargs="?", default=DEFAULT_INPUT)
    parser.add_argument("output_json", type=Path, nargs="?", default=DEFAULT_OUTPUT)
    parser.add_argument("--expected-count", type=int, default=94)
    args = parser.parse_args()
    payload = build_scope_artifact(
        args.input_csv,
        args.output_json,
        expected_count=args.expected_count,
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
