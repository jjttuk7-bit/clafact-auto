"""Write a reproducible CLAFACT-AUTO run manifest."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from core.run_manifest import build_run_manifest

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--input', action='append', required=True, metavar='NAME=PATH')
    parser.add_argument('--versions', required=True, type=Path)
    parser.add_argument('--reconciliation', required=True, type=Path)
    parser.add_argument('--code-revision', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    inputs = {name: Path(path) for name, path in (item.split('=', 1) for item in args.input)}
    manifest = build_run_manifest(run_id=args.run_id, inputs=inputs, versions=json.loads(args.versions.read_text(encoding='utf-8')), reconciliation=json.loads(args.reconciliation.read_text(encoding='utf-8')), code_revision=args.code_revision)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')

if __name__ == '__main__':
    main()
