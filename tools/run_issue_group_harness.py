"""Classify and execute bounded CLAFACT issue groups; never start a full run."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import Settings
from core.canonical_pipeline import create_claim_extractor
from core.claim_registry_loader import load_claim_registry
from core.issue_group_executor import ContextGroupExecutor
from core.issue_group_harness import (
    IssueGroup,
    build_issue_registry,
    record_group_run,
    run_group_slice,
    write_issue_ledgers,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command == "classify":
        rows = _load_jsonl(args.baseline_path)
        records = build_issue_registry(rows)
        summary = write_issue_ledgers(records, args.output_dir)
        print(
            json.dumps(
                {
                    "master_count": len(records),
                    "group_counts": {
                        group.value: values["전체수"]
                        for group, values in summary.items()
                    },
                    "output_dir": str(args.output_dir),
                },
                ensure_ascii=False,
            )
        )
        return 0
    if args.command == "record-results":
        group = IssueGroup(args.group)
        baseline_rows = _load_jsonl(args.baseline_path)
        issues = build_issue_registry(baseline_rows)
        if not (args.output_dir / "claim_issue_master.csv").is_file():
            write_issue_ledgers(issues, args.output_dir)
        saved_results = _load_jsonl(args.results_path)
        by_id = {
            str(result.get("claim_id") or ""): result
            for result in saved_results
        }
        if len(by_id) != len(saved_results):
            parser.error("DUPLICATE_SAVED_RESULT")

        def replay(issue, allowed_stages):
            result = by_id.get(issue.claim_id)
            if result is None:
                raise ValueError(f"SAVED_RESULT_NOT_FOUND:{issue.claim_id}")
            return result

        validated_results = run_group_slice(
            issues,
            group,
            replay,
            limit=len(saved_results),
            offset=args.offset,
        )
        comparisons = record_group_run(
            issues,
            group,
            validated_results,
            output_dir=args.output_dir,
            run_id=args.run_id,
            code_version=args.code_version,
            data_version=args.data_version or _file_hash(args.baseline_path),
        )
        print(
            json.dumps(
                {
                    "group": group.value,
                    "recorded": len(comparisons),
                    "outcome_counts": _counts(item.outcome for item in comparisons),
                    "run_id": args.run_id,
                    "network_used": False,
                },
                ensure_ascii=False,
            )
        )
        return 0
    if args.command == "run-group":
        group = IssueGroup(args.group)
        if group is not IssueGroup.CONTEXT:
            parser.error(f"GROUP_EXECUTOR_NOT_CONNECTED:{group.value}")
        baseline_rows = _load_jsonl(args.baseline_path)
        issues = build_issue_registry(baseline_rows)
        if not (args.output_dir / "claim_issue_master.csv").is_file():
            write_issue_ledgers(issues, args.output_dir)
        registry = load_claim_registry(args.registry_path)
        if registry.errors:
            parser.error(f"SOURCE_REGISTRY_ERRORS:{len(registry.errors)}")
        extractor = create_claim_extractor(Settings())
        executor = ContextGroupExecutor(registry.records, extractor=extractor)
        results = run_group_slice(
            issues,
            group,
            executor,
            limit=args.limit,
            offset=args.offset,
        )
        code_version = args.code_version
        data_version = args.data_version or _file_hash(args.baseline_path)
        comparisons = record_group_run(
            issues,
            group,
            results,
            output_dir=args.output_dir,
            run_id=args.run_id,
            code_version=code_version,
            data_version=data_version,
        )
        _write_jsonl(
            args.output_dir / "runs" / f"{args.run_id}.jsonl",
            results,
        )
        print(
            json.dumps(
                {
                    "group": group.value,
                    "selected": len(results),
                    "outcome_counts": _counts(item.outcome for item in comparisons),
                    "run_id": args.run_id,
                    "official_lookup_attempted": False,
                },
                ensure_ascii=False,
            )
        )
        return 0
    parser.error("COMMAND_REQUIRED")
    return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    classify = commands.add_parser("classify")
    classify.add_argument("baseline_path", type=Path)
    classify.add_argument("output_dir", type=Path)
    run_group = commands.add_parser("run-group")
    run_group.add_argument("baseline_path", type=Path)
    run_group.add_argument("registry_path", type=Path)
    run_group.add_argument("output_dir", type=Path)
    run_group.add_argument("--group", choices=[group.value for group in IssueGroup], required=True)
    run_group.add_argument("--limit", type=int, default=20)
    run_group.add_argument("--offset", type=int, default=0)
    run_group.add_argument("--run-id", required=True)
    run_group.add_argument("--code-version", default="issue-group-harness-v1")
    run_group.add_argument("--data-version")
    record_results = commands.add_parser("record-results")
    record_results.add_argument("baseline_path", type=Path)
    record_results.add_argument("results_path", type=Path)
    record_results.add_argument("output_dir", type=Path)
    record_results.add_argument(
        "--group", choices=[group.value for group in IssueGroup], required=True
    )
    record_results.add_argument("--offset", type=int, default=0)
    record_results.add_argument("--run-id", required=True)
    record_results.add_argument("--code-version", default="issue-group-harness-v1")
    record_results.add_argument("--data-version")
    return parser


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"INVALID_BASELINE_ROW:{line_number}")
        rows.append(payload)
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    temporary.replace(path)


def _file_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _counts(values: Sequence[str] | Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


if __name__ == "__main__":
    raise SystemExit(main())
