"""Build the frozen single-target Registry for direct-value type 8 only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.direct_value_multi_claim_scope import load_direct_value_multi_claim_scope
from tools.run_direct_value_multi_claim_scope import _record_from_case


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_csv", type=Path)
    parser.add_argument("output_jsonl", type=Path)
    parser.add_argument("--expected-safe-parents", type=int, default=360)
    parser.add_argument("--expected-single-parents", type=int, default=133)
    parser.add_argument("--approved-external-limit", type=int, default=236)
    args = parser.parse_args()

    scope = load_direct_value_multi_claim_scope(
        args.source_csv,
        expected_parent_count=args.expected_safe_parents,
        approved_external_limit=args.approved_external_limit,
    )
    if len(scope.single_cases) != args.expected_single_parents:
        raise ValueError(
            "DIRECT_VALUE_SINGLE_COUNT_MISMATCH:"
            f"{len(scope.single_cases)}:{args.expected_single_parents}"
        )

    records = [_record_from_case(case) for case in scope.single_cases]
    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(
        json.dumps(record.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
        + "\n"
        for record in records
    )
    temporary = args.output_jsonl.with_suffix(args.output_jsonl.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(args.output_jsonl)
    print(
        json.dumps(
            {
                "safe_parent_count": len(scope.parents),
                "single_parent_count": len(records),
                "grouping_parent_count": len(scope.grouping_cases),
                "source_sha256": scope.source_sha256,
                "output": str(args.output_jsonl.resolve()),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
