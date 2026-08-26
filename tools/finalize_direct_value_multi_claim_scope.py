"""Finalize direct-value multi-Claim primary and retry checkpoints."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.direct_value_multi_claim_results import (
    compile_multi_claim_results,
    write_multi_claim_deliverables,
)
from core.direct_value_multi_claim_scope import load_direct_value_multi_claim_scope


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_csv", type=Path)
    parser.add_argument("primary_checkpoint", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--retry-checkpoint", type=Path)
    parser.add_argument("--expected-parents", type=int, default=360)
    parser.add_argument("--approved-external-limit", type=int, default=236)
    parser.add_argument("--date-tag", default="20260826")
    args = parser.parse_args()

    scope = load_direct_value_multi_claim_scope(
        args.source_csv,
        expected_parent_count=args.expected_parents,
        approved_external_limit=args.approved_external_limit,
    )
    compiled = compile_multi_claim_results(
        scope,
        args.primary_checkpoint,
        args.retry_checkpoint,
    )
    outputs = write_multi_claim_deliverables(
        compiled,
        args.output_dir,
        date_tag=args.date_tag,
    )
    print(json.dumps({
        "report": compiled.report,
        "outputs": {key: str(path.resolve()) for key, path in outputs.items()},
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
