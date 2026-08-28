"""Build all 176 direct-value KOSIS query specifications and runnable Registry rows."""

from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.direct_value_coordinate_spec_bundle import build_coordinate_spec_bundle


DEFAULT_LEDGER = PROJECT_ROOT / "deliverables" / "CLAFACT_AUTO_8번_직접값_230건_지표구체화18재처리원장_20260828.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "artifacts" / "direct_value_coordinate_spec_176_20260828"


def build_artifacts(
    ledger_csv: Path,
    output_dir: Path,
    *,
    expected_count: int = 176,
) -> dict[str, object]:
    with ledger_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    bundle = build_coordinate_spec_bundle(rows, expected_count=expected_count)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(
        output_dir / "query_specs.jsonl",
        (spec.model_dump(mode="json") for spec in bundle.specs),
    )
    _write_jsonl(
        output_dir / "ready_registry.jsonl",
        (record.model_dump(mode="json") for record in bundle.ready_records),
    )
    _write_jsonl(
        output_dir / "preverification.jsonl",
        (spec.model_dump(mode="json") for spec in bundle.preverification_specs),
    )
    _write_json(output_dir / "scope.json", bundle.scope.to_dict())
    manifest = {
        "scope_count": len(bundle.scope.records),
        "query_spec_count": len(bundle.specs),
        "ready_count": len(bundle.ready_records),
        "preverification_count": len(bundle.preverification_specs),
        "readiness_counts": bundle.readiness_counts,
        "scope_reason_counts": bundle.scope.reason_counts,
        "split_counts": bundle.scope.split_counts,
        "scope_manifest_sha256": bundle.scope.manifest_sha256,
        "bundle_manifest_sha256": bundle.manifest_sha256,
        "input_ledger": _manifest_path(ledger_csv),
        "input_ledger_sha256": _file_sha256(ledger_csv),
        "code_manifest_sha256": _paths_sha256([
            PROJECT_ROOT / "core" / "direct_value_coordinate_spec_scope.py",
            PROJECT_ROOT / "core" / "direct_value_coordinate_spec_registry.py",
            PROJECT_ROOT / "core" / "direct_value_coordinate_spec_preparation.py",
            PROJECT_ROOT / "core" / "direct_value_coordinate_spec_bundle.py",
            PROJECT_ROOT / "core" / "kosis_query_spec_compiler.py",
            PROJECT_ROOT / "schemas" / "kosis_query_spec.py",
            PROJECT_ROOT / "core" / "direct_value_child_guard.py",
            PROJECT_ROOT / "core" / "hard_guard_impl.py",
            Path(__file__),
        ]),
        "data_manifest_sha256": _trees_sha256([
            PROJECT_ROOT / "config",
            PROJECT_ROOT / "data" / "semantic_standard",
            PROJECT_ROOT / "data" / "kosis_catalog",
        ]),
        "query_specs": _manifest_path(output_dir / "query_specs.jsonl"),
        "ready_registry": _manifest_path(output_dir / "ready_registry.jsonl"),
        "preverification": _manifest_path(output_dir / "preverification.jsonl"),
    }
    _write_json(output_dir / "manifest.json", manifest)
    return manifest


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: Iterable[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()

def _manifest_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _paths_sha256(paths: list[Path]) -> str:
    digest = sha256()
    for path in sorted(paths, key=lambda value: str(value)):
        digest.update(str(path.relative_to(PROJECT_ROOT) if path.is_relative_to(PROJECT_ROOT) else path).encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _trees_sha256(roots: list[Path]) -> str:
    paths = [
        path for root in roots if root.exists()
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".py", ".json", ".jsonl", ".csv", ".yaml", ".yml"}
    ]
    return _paths_sha256(paths) if paths else sha256(b"").hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger_csv", type=Path, nargs="?", default=DEFAULT_LEDGER)
    parser.add_argument("output_dir", type=Path, nargs="?", default=DEFAULT_OUTPUT)
    parser.add_argument("--expected-count", type=int, default=176)
    args = parser.parse_args()
    manifest = build_artifacts(
        args.ledger_csv,
        args.output_dir,
        expected_count=args.expected_count,
    )
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
