"""Build a review queue for incomplete required ClaimSchema slots."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.claim_registry_enrichment_queue import build_enrichment_queue


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    records = [
        json.loads(line)
        for line in args.registry.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    queue, summary = build_enrichment_queue(records)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    queue_path = args.output_dir / "slot_enrichment_queue.jsonl"
    summary_path = args.output_dir / "slot_enrichment_summary.json"
    queue_path.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in queue)
        + ("\n" if queue else ""),
        encoding="utf-8",
    )
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Queue: {queue_path}")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
