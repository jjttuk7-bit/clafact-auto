"""Freeze only type-8 direct/threshold children from the multi-Claim Registry."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

from schemas.claim_registry import ClaimRegistryRecord


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_jsonl", type=Path)
    parser.add_argument("output_jsonl", type=Path)
    parser.add_argument("--expected-input", type=int, default=290)
    parser.add_argument("--expected-type8", type=int, default=197)
    args = parser.parse_args()

    source_rows = [
        json.loads(line)
        for line in args.source_jsonl.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(source_rows) != args.expected_input:
        raise ValueError(
            f"MULTI_CHILD_INPUT_COUNT_MISMATCH:{len(source_rows)}:{args.expected_input}"
        )

    output: list[ClaimRegistryRecord] = []
    link_counts: Counter[str] = Counter()
    for payload in source_rows:
        record = ClaimRegistryRecord.model_validate(payload)
        if record.claim.calculation not in {"DIRECT_VALUE", "THRESHOLD"}:
            continue
        enrichment = dict(record.slot_enrichment or {})
        lineage = enrichment.get("lineage_record")
        expression = str(
            lineage.get("target_expression")
            if isinstance(lineage, dict)
            else ""
        ).strip()
        source = record.claim.source_sentence
        occurrences = source.count(expression) if expression else 0
        if occurrences == 1:
            start = source.index(expression)
            enrichment.update({
                "target_link_status": "SOURCE_GROUNDED",
                "target_numeric_expression": expression,
                "target_numeric_start": start,
                "target_numeric_end": start + len(expression),
            })
        else:
            enrichment.update({
                "target_link_status": (
                    "TARGET_AMBIGUOUS_IN_SOURCE"
                    if occurrences > 1
                    else "TARGET_NOT_FOUND_IN_SOURCE"
                ),
                "target_numeric_expression": expression,
            })
        link_counts[str(enrichment["target_link_status"])] += 1
        output.append(record.model_copy(update={"slot_enrichment": enrichment}))

    if len(output) != args.expected_type8:
        raise ValueError(
            f"MULTI_CHILD_TYPE8_COUNT_MISMATCH:{len(output)}:{args.expected_type8}"
        )
    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output_jsonl.with_suffix(args.output_jsonl.suffix + ".tmp")
    temporary.write_text(
        "".join(
            json.dumps(row.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
            + "\n"
            for row in output
        ),
        encoding="utf-8",
    )
    temporary.replace(args.output_jsonl)
    print(json.dumps({
        "input_child_count": len(source_rows),
        "type8_child_count": len(output),
        "target_link_counts": dict(link_counts),
        "output": str(args.output_jsonl.resolve()),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
